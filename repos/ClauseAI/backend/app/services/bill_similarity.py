import os
import re
import numpy as np
import warnings
import logging
from typing import List, Dict, Any
from rapidfuzz import fuzz
from difflib import SequenceMatcher
from nltk.stem import SnowballStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

from app.core.config import (
    BILLS_DATA_DIR,
    DEFAULT_JURISDICTION,
    SIMILARITY_STAGE1_LIMIT,
    SIMILARITY_STAGE2_LIMIT,
    SIMILARITY_CHUNK_SIZE,
    SIMILARITY_MAX_CHUNKS,
    LEGAL_NOISE_WORDS
)
from app.utils.bill_cleaning import clean_bill_text
from app.services.business_data_repository import business_data_repo

warnings.filterwarnings('ignore')
logging.getLogger("transformers").setLevel(logging.ERROR)
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
logger = logging.getLogger(__name__)

class BillSimilarityEngine:
    def __init__(self, jurisdiction: str = DEFAULT_JURISDICTION):
        self.jurisdiction = jurisdiction
        self.main_path = os.path.join(BILLS_DATA_DIR, jurisdiction)

        json_path = os.path.join(self.main_path, "master.json")
        self.bills = business_data_repo.read_json(json_path)

        self.titles = [b["Bill Title"] for b in self.bills]
        self.descriptions = [b["Bill Description"] for b in self.bills]
        self.data = list(zip(self.titles, self.descriptions))
        
        self.stemmer = SnowballStemmer("english")
        self.legal_noise = LEGAL_NOISE_WORDS
        self.cleaned_corpus = [self.clean(t, d) for t, d in self.data]
        
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 3),
            max_df=0.72,
            min_df=2,
            sublinear_tf=True,
            norm="l2"
        )
        self.tfidf = self.vectorizer.fit_transform(self.cleaned_corpus)
        
        self.semantic_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            local_files_only=True
        )
        self.tokenizer = AutoTokenizer.from_pretrained(
            "sentence-transformers/all-MiniLM-L6-v2",
            local_files_only=True
        )
    
    def clean(self, title: str, desc: str) -> str:
        text = (title + " " + title + " " + title + " " + desc).lower()
        text = re.sub(r"an act to (add|amend|repeal).*?(relating to|relative to)", " ", text)
        text = re.sub(r"(section|article|chapter|part|division|title|subdivision)\s+\d+[\d.,-]*", " ", text)
        text = re.sub(r"[a-z]+\s+(and|&)\s+[a-z]+\s+code", " ", text)
        text = re.sub(r"(commencing with|pursuant to|relating to|relative to)", " ", text)
        text = re.sub(r"[^a-z\s]", " ", text)
        tokens = [self.stemmer.stem(w) for w in text.split() if w not in self.legal_noise and len(w) > 2]
        return " ".join(tokens)
    
    def find_top_matches(self, user_title: str, user_desc: str, limit: int) -> List[Dict[str, Any]]:
        query = self.clean(user_title, user_desc)
        q_vec = self.vectorizer.transform([query])
        cosine_scores = cosine_similarity(q_vec, self.tfidf).flatten()
        
        top_idx = np.argpartition(cosine_scores, -limit)[-limit:]
        top_idx = top_idx[np.argsort(cosine_scores[top_idx])[::-1]]
        
        results = []
        for i in top_idx:
            tfidf_score = cosine_scores[i]
            fuzzy_score = fuzz.token_set_ratio(query, self.cleaned_corpus[i]) / 100
            seq_score = SequenceMatcher(None, query, self.cleaned_corpus[i]).ratio()
            final = tfidf_score * 0.60 + fuzzy_score * 0.30 + seq_score * 0.10
            
            results.append(self.bills[i].copy())
            results[-1]["Score"] = round(final, 4)
        
        return sorted(results, key=lambda x: x["Score"], reverse=True)
    
    def chunk_text(self, text: str, chunk_size: int, max_chunks: int) -> List[str]:
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        chunks = []
        
        for i in range(0, len(tokens), chunk_size):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens, skip_special_tokens=True)
            chunks.append(chunk_text)
            if len(chunks) >= max_chunks:
                break
        
        return chunks
    
    def compute_weighted_score(self, chunk_scores: np.ndarray) -> float:
        if len(chunk_scores) == 0:
            return 0.0
        
        sorted_scores = np.sort(chunk_scores)[::-1]
        n = len(sorted_scores)
        mid_point = n // 2
        top_half = sorted_scores[:mid_point] if mid_point > 0 else sorted_scores
        
        if len(top_half) == 0:
            return 0.0
        
        n_top = len(top_half)
        weights = np.zeros(n_top)
        peak_idx = max(1, n_top // 6)
        
        for i in range(n_top):
            weights[i] = np.exp(-((i - peak_idx) ** 2) / (2 * (n_top / 6) ** 2))
        
        weights = weights / weights.sum()
        return np.sum(top_half * weights)
    
    def semantic_rerank(
        self,
        stage1_results: List[Dict[str, Any]],
        user_summary: str,
        top_k: int,
        chunk_size: int,
        max_chunks: int
    ) -> List[Dict[str, Any]]:
        summary_tokens = self.tokenizer.encode(
            user_summary,
            add_special_tokens=True,
            max_length=384,
            truncation=True
        )
        user_summary_truncated = self.tokenizer.decode(summary_tokens, skip_special_tokens=True)
        query_embedding = self.semantic_model.encode(user_summary_truncated, convert_to_tensor=False)
        
        stage2_results = []
        
        for result in stage1_results:
            bill_id = result["Bill ID"]
            bill_path = os.path.join(self.main_path, f"cleaned_bills/{bill_id}.txt")

            try:
                bill_text = business_data_repo.read_text(bill_path)
            except FileNotFoundError:
                continue

            cleaned_bill_text = clean_bill_text(bill_text, aggressive=True)
            
            chunks = self.chunk_text(cleaned_bill_text, chunk_size=chunk_size, max_chunks=max_chunks)
            
            if not chunks:
                continue
            
            chunk_embeddings = self.semantic_model.encode(chunks, convert_to_tensor=False)
            chunk_scores = cosine_similarity([query_embedding], chunk_embeddings).flatten()
            semantic_score = self.compute_weighted_score(chunk_scores)
            
            stage1_score = result["Score"]
            combined_score = 0.8 * semantic_score + 0.2 * stage1_score
            
            stage2_results.append({
                "Bill ID": result["Bill ID"],
                "Bill Number": result.get("Bill Number"),
                "Bill Title": result["Bill Title"],
                "Bill Description": result["Bill Description"],
                "Bill URL": result.get("Bill URL"),
                "Date Presented": result.get("Date Presented"),
                "Date Passed": result.get("Date Passed"),
                "Votes": result.get("Votes"),
                "Stage Passed": result.get("Stage Passed"),
                "Bill Text": cleaned_bill_text,
                "Passed": (result["Stage Passed"] >= 3),
                "Score": round(combined_score, 4)
            })
        
        return sorted(stage2_results, key=lambda x: x["Score"], reverse=True)[:top_k]
    
    def run_full_workflow(
        self,
        user_title: str,
        user_desc: str,
        user_summary: str,
        stage1_limit: int = SIMILARITY_STAGE1_LIMIT,
        stage2_limit: int = SIMILARITY_STAGE2_LIMIT,
        chunk_size: int = SIMILARITY_CHUNK_SIZE,
        max_chunks: int = SIMILARITY_MAX_CHUNKS
    ) -> List[Dict[str, Any]]:
        stage1_matches = self.find_top_matches(user_title, user_desc, limit=stage1_limit)
        final_matches = self.semantic_rerank(
            stage1_matches,
            user_summary,
            top_k=stage2_limit,
            chunk_size=chunk_size,
            max_chunks=max_chunks
        )
        return final_matches

async def find_similar_bills(
    title: str,
    description: str,
    summary: str,
    jurisdiction: str = DEFAULT_JURISDICTION
) -> List[Dict[str, Any]]:
    logger.info(
        "Bill similarity workflow started",
        extra={"event": "bill_similarity_started", "jurisdiction": jurisdiction},
    )
    engine = BillSimilarityEngine(jurisdiction=jurisdiction)
    
    results = engine.run_full_workflow(
        user_title=title,
        user_desc=description,
        user_summary=summary
    )
    
    passed_fail = {"Passed": 0, "Failed": 0}
    for res in results:
        if res["Passed"]:
            passed_fail["Passed"] += 1
        else:
            passed_fail["Failed"] += 1
    
    get_each_side = min(passed_fail["Passed"], passed_fail["Failed"])
    each_gotten = {"Passed": 0, "Failed": 0}
    
    balanced_results = []
    for res in results:
        if res["Passed"] and each_gotten["Passed"] < get_each_side:
            bill_id = res["Bill ID"]
            balanced_results.append({
                "Bill_Text": res.get("Bill Text") or f"Bill Text - {bill_id}",
                "Bill_ID": bill_id,
                "Bill_Number": res.get("Bill Number"),
                "Bill_Title": res.get("Bill Title"),
                "Bill_Description": res.get("Bill Description"),
                "Bill_URL": res.get("Bill URL"),
                "Date_Presented": res.get("Date Presented"),
                "Date_Passed": res.get("Date Passed"),
                "Votes": res.get("Votes"),
                "Stage_Passed": res.get("Stage Passed"),
                "Score": res["Score"],
                "Passed": res["Passed"]
            })
            each_gotten["Passed"] += 1
        elif not res["Passed"] and each_gotten["Failed"] < get_each_side:
            bill_id = res["Bill ID"]
            balanced_results.append({
                "Bill_Text": res.get("Bill Text") or f"Bill Text - {bill_id}",
                "Bill_ID": bill_id,
                "Bill_Number": res.get("Bill Number"),
                "Bill_Title": res.get("Bill Title"),
                "Bill_Description": res.get("Bill Description"),
                "Bill_URL": res.get("Bill URL"),
                "Date_Presented": res.get("Date Presented"),
                "Date_Passed": res.get("Date Passed"),
                "Votes": res.get("Votes"),
                "Stage_Passed": res.get("Stage Passed"),
                "Score": res["Score"],
                "Passed": res["Passed"]
            })
            each_gotten["Failed"] += 1
        
        if each_gotten["Passed"] >= get_each_side and each_gotten["Failed"] >= get_each_side:
            break

    logger.info(
        "Bill similarity workflow completed",
        extra={
            "event": "bill_similarity_completed",
            "raw_matches": len(results),
            "balanced_matches": len(balanced_results),
        },
    )
    return balanced_results