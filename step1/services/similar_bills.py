from __future__ import annotations

import json
import re
import time
from collections import Counter, OrderedDict
from math import sqrt

from step1.config import get_settings
from step1.models import CandidateBill, LlmRerankResponse, SearchRequestOptions, SearchResult, UploadedBillProfile
from step1.services.bill_extraction import detect_file_type, extract_text_from_file
from step1.services.bill_profile import BillProfileExtractor
from step1.services.codex_client import CodexClient
from step1.services.database import Database
from step1.services.semantic_ranker import SemanticRanker


RERANK_SYSTEM_PROMPT = """You are a legislative bill similarity judge.

Return ONLY valid JSON.

Score each candidate based on:
- policy intent match
- legal mechanism match
- affected entities match
- enforcement and operational structure match
- whether the candidate would be genuinely useful as a precedent or analog
- whether the candidate is a targeted policy analog instead of a broad omnibus, trailer, or budget bill with incidental overlap

Do NOT overvalue exact word overlap.
Do NOT reward generic omnibus, trailer, or budget bills unless the actual mechanism and operational structure are genuinely close.

Expected JSON:
{
  "top_candidates": [
    {
      "candidate_id": "",
      "score": 0.0,
      "reason": "",
      "match_dimensions": []
    }
  ],
  "overall_notes": ""
}

Rules:
- `score` must be between 0 and 1.
- Pick the strongest matches only.
- `reason` should be brief and concrete.
- `match_dimensions` should contain short labels like `policy intent`, `enforcement`, `funding`, `regulated entities`, `reporting`, `liability`.
"""


GENERIC_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "based",
    "be",
    "by",
    "for",
    "following",
    "from",
    "if",
    "include",
    "including",
    "in",
    "into",
    "is",
    "it",
    "its",
    "not",
    "of",
    "on",
    "or",
    "solely",
    "that",
    "the",
    "their",
    "there",
    "these",
    "this",
    "to",
    "under",
    "was",
    "were",
    "with",
    "within",
}

GENERIC_BROAD_BILL_TERMS = (
    "budget act",
    "budget trailer",
    "trailer bill",
    "omnibus",
    "trailer budget",
)


def _normalize_text(text: str) -> str:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _important_tokens(text: str) -> list[str]:
    normalized = _normalize_text(text).lower()
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return [
        token
        for token in tokens
        if (
            len(token) >= 3
            or token in {"dds", "act"}
            or (len(token) == 3 and token.isdigit())
        )
        and token not in GENERIC_QUERY_STOPWORDS
    ]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    return list(OrderedDict.fromkeys(items))


def _extract_uploaded_bill_identifier(bill_text: str) -> str:
    patterns = [
        re.compile(r"\b(AB|SB|HB|HR|HJR|SJR)\s*(?:No\.)?\s*(\d{1,5})\b", re.IGNORECASE),
        re.compile(r"\b(assembly|senate|house)\s+bill\s+no\.?\s*(\d{1,5})\b", re.IGNORECASE),
    ]
    preview = bill_text[:4000]
    for pattern in patterns:
        match = pattern.search(preview)
        if not match:
            continue
        prefix = match.group(1).upper()
        if prefix in {"ASSEMBLY", "SENATE", "HOUSE"}:
            prefix = {"ASSEMBLY": "AB", "SENATE": "SB", "HOUSE": "HB"}[prefix]
        return f"{prefix} {match.group(2)}"
    return ""


class SimilarBillRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _preferred_state_code(self, profile: UploadedBillProfile) -> str:
        for hint in profile.jurisdiction_hints:
            normalized = (hint or "").strip().lower()
            if len(normalized) == 2 and normalized.isalpha():
                return normalized
        return ""

    def _query_phrases(self, profile: UploadedBillProfile) -> list[str]:
        raw_sources = [
            profile.title,
            profile.description,
            profile.summary,
            profile.policy_intent,
            *profile.search_phrases,
            *profile.policy_domain,
            *profile.legal_mechanisms,
            *profile.affected_entities,
            *profile.enforcement_mechanisms,
        ]

        normalized_sources = [_normalize_text(source) for source in raw_sources if _normalize_text(source)]
        token_counts: Counter[str] = Counter()
        for source in normalized_sources:
            token_counts.update(set(_important_tokens(source)))

        weighted_queries: dict[str, float] = {}
        source_queries: list[list[str]] = []

        def add_query(text: str, weight: float) -> None:
            normalized = _normalize_text(text)
            if len(normalized) < 4:
                return
            key = normalized.lower()
            if key not in weighted_queries or weight > weighted_queries[key]:
                weighted_queries[key] = weight

        signal_tokens = {
            "lanterman",
            "regional",
            "center",
            "centers",
            "foster",
            "child",
            "children",
            "developmental",
            "disability",
            "services",
            "assessment",
            "intake",
            "eligibility",
            "denial",
            "documentation",
            "reporting",
            "transparency",
            "records",
            "notice",
            "notices",
        }

        for source in normalized_sources:
            tokens = _important_tokens(source)
            local_queries: list[tuple[str, float]] = []
            if 1 < len(tokens) <= 6:
                weight = 2.5 + sum(token_counts[token] for token in set(tokens))
                local_queries.append((" ".join(tokens), weight))
            for size in (2, 3, 4):
                if len(tokens) < size:
                    continue
                for index in range(0, len(tokens) - size + 1):
                    window = tokens[index : index + size]
                    if not any(token_counts[token] > 1 for token in window):
                        continue
                    weight = size * 2 + sum(token_counts[token] for token in set(window))
                    if any(token in signal_tokens for token in window):
                        weight += 3
                    if "lanterman" in window:
                        weight += 4
                    local_queries.append((" ".join(window), weight))

            for query, weight in sorted(local_queries, key=lambda item: (-item[1], len(item[0]), item[0]))[:2]:
                add_query(query, weight)
            source_queries.append([query for query, _ in sorted(local_queries, key=lambda item: (-item[1], len(item[0]), item[0]))[:4]])

        for anchor in [
            profile.title,
            *profile.search_phrases,
            *profile.legal_mechanisms,
            *profile.affected_entities,
        ]:
            normalized = _normalize_text(anchor)
            token_count = len(_important_tokens(normalized))
            if 2 <= token_count <= 5:
                add_query(normalized, 10 + token_count)

        combined_source_text = " | ".join(normalized_sources).lower()
        for anchor_phrase in (
            "regional center",
            "regional centers",
            "developmental services",
            "developmental disability services",
            "foster child",
            "foster children",
            "missing documentation",
            "public reporting",
            "eligibility determination",
            "notices actions",
            "denials services",
            "public records",
            "intake transparency",
        ):
            if anchor_phrase in combined_source_text:
                add_query(anchor_phrase, 18.0)
        if "lanterman" in combined_source_text and "developmental services" in combined_source_text:
            add_query("lanterman developmental services", 22.0)
        if "regional center" in combined_source_text and "assessment" in combined_source_text:
            add_query("regional center assessment", 20.0)
        if "regional center" in combined_source_text and "reporting" in combined_source_text:
            add_query("regional center reporting", 19.0)
        if "foster child" in combined_source_text and "eligibility" in combined_source_text:
            add_query("foster child eligibility", 19.0)
        if "missing documentation" in combined_source_text and "assessment" in combined_source_text:
            add_query("missing documentation assessment", 19.0)

        ranked = [
            query
            for query, _ in sorted(
                weighted_queries.items(),
                key=lambda item: (-item[1], len(item[0]), item[0]),
            )
        ]
        selected: list[str] = []
        covered_signal_tokens: set[str] = set()
        for token in (
            "lanterman",
            "regional",
            "foster",
            "developmental",
            "intake",
            "assessment",
            "eligibility",
            "denial",
            "documentation",
            "transparency",
            "reporting",
        ):
            for query in ranked:
                query_tokens = set(_important_tokens(query))
                if token in query_tokens and query not in selected:
                    selected.append(query)
                    covered_signal_tokens.update(query_tokens & signal_tokens)
                    break

        for per_source_queries in source_queries:
            for query in per_source_queries:
                if query not in selected:
                    selected.append(query)
                if len(selected) >= 18:
                    break
            if len(selected) >= 18:
                break

        for query in ranked:
            if query not in selected:
                selected.append(query)
            if len(selected) >= 18:
                break

        return _dedupe_preserve_order(selected)[:18]

    def _primary_urls_by_bill(self, bill_ids: list[str]) -> dict[str, str]:
        if not bill_ids:
            return {}

        primary_urls: dict[str, str] = {}
        for query in (
            """
            SELECT DISTINCT ON (bill_id)
                bill_id,
                url
            FROM public.opencivicdata_billsource
            WHERE bill_id = ANY(%(bill_ids)s::varchar[])
              AND url IS NOT NULL
              AND url <> ''
            ORDER BY bill_id, url
            """,
            """
            SELECT DISTINCT ON (bv.bill_id)
                bv.bill_id,
                bvl.url
            FROM public.opencivicdata_billversion bv
            JOIN public.opencivicdata_billversionlink bvl
              ON bvl.version_id = bv.id
            WHERE bv.bill_id = ANY(%(bill_ids)s::varchar[])
              AND bvl.url IS NOT NULL
              AND bvl.url <> ''
            ORDER BY bv.bill_id, bv.date DESC NULLS LAST, bvl.url
            """,
            """
            SELECT DISTINCT ON (bd.bill_id)
                bd.bill_id,
                bdl.url
            FROM public.opencivicdata_billdocument bd
            JOIN public.opencivicdata_billdocumentlink bdl
              ON bdl.document_id = bd.id
            WHERE bd.bill_id = ANY(%(bill_ids)s::varchar[])
              AND bdl.url IS NOT NULL
              AND bdl.url <> ''
            ORDER BY bd.bill_id, bd.date DESC NULLS LAST, bdl.url
            """,
        ):
            rows = self.db.fetch_all(query, {"bill_ids": bill_ids})
            for row in rows:
                if row["bill_id"] not in primary_urls:
                    primary_urls[row["bill_id"]] = row["url"]
        return primary_urls

    def lexical_candidates(self, profile: UploadedBillProfile, options: SearchRequestOptions) -> list[CandidateBill]:
        phrases = self._query_phrases(profile)
        if not phrases:
            return []

        def collect_matches(state_code: str) -> dict[str, dict]:
            aggregated: dict[str, dict] = {}
            per_phrase_limit = 120
            for index, phrase in enumerate(phrases, start=1):
                phrase_rows = self.db.fetch_all(
                    """
                    WITH query AS (
                        SELECT websearch_to_tsquery(
                            'english',
                            regexp_replace(%(phrase)s, '[^[:alnum:]\\s-]', ' ', 'g')
                        ) AS q
                    )
                    SELECT
                        bill_id,
                        ts_rank_cd(search_vector, query.q) AS phrase_rank
                    FROM step1.bill_search_docs, query
                    WHERE bill_id IS NOT NULL
                      AND (%(state_code)s = '' OR state_code = %(state_code)s)
                      AND search_vector @@ query.q
                    ORDER BY phrase_rank DESC, bill_id
                    LIMIT %(per_phrase_limit)s
                    """,
                    {"phrase": phrase, "per_phrase_limit": per_phrase_limit, "state_code": state_code},
                )
                for row in phrase_rows:
                    bill_id = row["bill_id"]
                    if bill_id not in aggregated:
                        aggregated[bill_id] = {
                            "lexical_score": 0.0,
                            "matched_queries": [],
                        }
                    aggregated[bill_id]["lexical_score"] += float(row.get("phrase_rank") or 0.0) / sqrt(index)
                    aggregated[bill_id]["matched_queries"].append(phrase)
            return aggregated

        preferred_state_code = self._preferred_state_code(profile)
        aggregated = collect_matches(preferred_state_code)
        if preferred_state_code and options.include_cross_jurisdiction and len(aggregated) < 40:
            wider_matches = collect_matches("")
            for bill_id, match_data in wider_matches.items():
                if bill_id not in aggregated:
                    aggregated[bill_id] = match_data
                    continue
                aggregated[bill_id]["lexical_score"] = max(
                    aggregated[bill_id]["lexical_score"],
                    match_data["lexical_score"],
                )
                aggregated[bill_id]["matched_queries"] = list(
                    OrderedDict.fromkeys(aggregated[bill_id]["matched_queries"] + match_data["matched_queries"])
                )

        sorted_ids = [
            bill_id
            for bill_id, _ in sorted(
                aggregated.items(),
                key=lambda item: item[1]["lexical_score"],
                reverse=True,
            )[: get_settings().lexical_candidate_limit]
        ]

        if not sorted_ids:
            return []

        rows = self.db.fetch_all(
            """
            SELECT
                b.id AS bill_id,
                b.identifier,
                b.title,
                b.classification,
                b.subject AS subjects,
                j.id AS jurisdiction_id,
                j.name AS jurisdiction_name,
                j.classification AS jurisdiction_type,
                CASE
                    WHEN j.id LIKE '%%/state:%%' THEN lower(split_part(split_part(j.id, '/state:', 2), '/', 1))
                    ELSE NULL
                END AS state_code,
                s.identifier AS session_identifier,
                s.name AS session_name,
                s.classification AS session_classification,
                b.latest_action_date,
                b.latest_action_description,
                b.latest_passage_date,
                CASE
                    WHEN lower(b.latest_action_description) LIKE '%%chapter%%'
                      OR lower(b.latest_action_description) LIKE '%%signed%%'
                      OR lower(b.latest_action_description) LIKE '%%became law%%'
                      OR lower(b.latest_action_description) LIKE '%%approved by governor%%'
                    THEN 'enacted'
                    WHEN lower(b.latest_action_description) LIKE '%%veto%%'
                    THEN 'vetoed'
                    WHEN lower(b.latest_action_description) LIKE '%%failed%%'
                      OR lower(b.latest_action_description) LIKE '%%died%%'
                      OR lower(b.latest_action_description) LIKE '%%dead%%'
                      OR lower(b.latest_action_description) LIKE '%%indefinitely postponed%%'
                      OR lower(b.latest_action_description) LIKE '%%defeated%%'
                      OR lower(b.latest_action_description) LIKE '%%rejected%%'
                      OR lower(b.latest_action_description) LIKE '%%withdrawn%%'
                    THEN 'failed_or_dead'
                    WHEN b.latest_passage_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                    THEN 'passed_not_enacted'
                    ELSE 'other_or_in_progress'
                END AS derived_status,
                COALESCE(bsd.all_titles, '') AS searchable_titles,
                b.latest_action_date AS sort_latest_action_date
            FROM public.opencivicdata_bill b
            JOIN public.opencivicdata_legislativesession s
              ON s.id = b.legislative_session_id
            JOIN public.opencivicdata_jurisdiction j
              ON j.id = s.jurisdiction_id
            LEFT JOIN step1.bill_search_docs bsd
              ON bsd.bill_id = b.id
            WHERE b.id = ANY(%(bill_ids)s::varchar[])
              AND 'bill' = ANY(b.classification)
              AND (%(jurisdiction_filter)s = '' OR j.id = %(jurisdiction_filter)s)
              AND (
                    %(status_filter)s = ''
                    OR (
                        CASE
                            WHEN lower(b.latest_action_description) LIKE '%%chapter%%'
                              OR lower(b.latest_action_description) LIKE '%%signed%%'
                              OR lower(b.latest_action_description) LIKE '%%became law%%'
                              OR lower(b.latest_action_description) LIKE '%%approved by governor%%'
                            THEN 'enacted'
                            WHEN lower(b.latest_action_description) LIKE '%%veto%%'
                            THEN 'vetoed'
                            WHEN lower(b.latest_action_description) LIKE '%%failed%%'
                              OR lower(b.latest_action_description) LIKE '%%died%%'
                              OR lower(b.latest_action_description) LIKE '%%dead%%'
                              OR lower(b.latest_action_description) LIKE '%%indefinitely postponed%%'
                              OR lower(b.latest_action_description) LIKE '%%defeated%%'
                              OR lower(b.latest_action_description) LIKE '%%rejected%%'
                              OR lower(b.latest_action_description) LIKE '%%withdrawn%%'
                            THEN 'failed_or_dead'
                            WHEN b.latest_passage_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                            THEN 'passed_not_enacted'
                            ELSE 'other_or_in_progress'
                        END
                    ) = %(status_filter)s
                  )
              AND (
                    %(include_failed)s
                    OR (
                        lower(b.latest_action_description) NOT LIKE '%%failed%%'
                        AND lower(b.latest_action_description) NOT LIKE '%%died%%'
                        AND lower(b.latest_action_description) NOT LIKE '%%dead%%'
                        AND lower(b.latest_action_description) NOT LIKE '%%defeated%%'
                    )
                  )
              AND (
                    %(include_enacted)s
                    OR (
                        lower(b.latest_action_description) NOT LIKE '%%chapter%%'
                        AND lower(b.latest_action_description) NOT LIKE '%%signed%%'
                        AND lower(b.latest_action_description) NOT LIKE '%%became law%%'
                    )
                  )
              AND (
                    %(include_in_progress)s
                    OR (
                        (
                            CASE
                                WHEN lower(b.latest_action_description) LIKE '%%chapter%%'
                                  OR lower(b.latest_action_description) LIKE '%%signed%%'
                                  OR lower(b.latest_action_description) LIKE '%%became law%%'
                                  OR lower(b.latest_action_description) LIKE '%%approved by governor%%'
                                THEN 'enacted'
                                WHEN lower(b.latest_action_description) LIKE '%%veto%%'
                                THEN 'vetoed'
                                WHEN lower(b.latest_action_description) LIKE '%%failed%%'
                                  OR lower(b.latest_action_description) LIKE '%%died%%'
                                  OR lower(b.latest_action_description) LIKE '%%dead%%'
                                  OR lower(b.latest_action_description) LIKE '%%indefinitely postponed%%'
                                  OR lower(b.latest_action_description) LIKE '%%defeated%%'
                                  OR lower(b.latest_action_description) LIKE '%%rejected%%'
                                  OR lower(b.latest_action_description) LIKE '%%withdrawn%%'
                                THEN 'failed_or_dead'
                                WHEN b.latest_passage_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                                THEN 'passed_not_enacted'
                                ELSE 'other_or_in_progress'
                            END
                        ) <> 'other_or_in_progress'
                    )
                  )
            ORDER BY b.latest_action_date DESC NULLS LAST
            """,
            {
                "bill_ids": sorted_ids,
                "jurisdiction_filter": options.jurisdiction_filter or "",
                "status_filter": options.status_filter or "",
                "include_failed": options.include_failed,
                "include_enacted": options.include_enacted,
                "include_in_progress": options.include_in_progress,
            },
        )
        primary_urls = self._primary_urls_by_bill(sorted_ids)
        candidates: list[CandidateBill] = []
        for row in rows:
            match_data = aggregated.get(row["bill_id"], {"lexical_score": 0.0, "matched_queries": []})
            candidates.append(
                CandidateBill(
                    bill_id=row["bill_id"],
                    identifier=row["identifier"],
                    title=row["title"],
                    classification=row.get("classification") or [],
                    subjects=row.get("subjects") or [],
                    jurisdiction_id=row["jurisdiction_id"],
                    jurisdiction_name=row["jurisdiction_name"],
                    jurisdiction_type=row["jurisdiction_type"],
                    state_code=row.get("state_code"),
                    session_identifier=row["session_identifier"],
                    session_name=row["session_name"],
                    session_classification=row["session_classification"],
                    latest_action_date=row.get("latest_action_date"),
                    latest_action_description=row["latest_action_description"],
                    latest_passage_date=row.get("latest_passage_date"),
                    derived_status=row["derived_status"],
                    primary_bill_url=primary_urls.get(row["bill_id"]),
                    searchable_titles=row.get("searchable_titles") or "",
                    matched_queries=list(OrderedDict.fromkeys(match_data["matched_queries"])),
                    lexical_score=float(match_data["lexical_score"]),
                )
            )
        return sorted(candidates, key=lambda item: item.lexical_score, reverse=True)

    def hydrate_candidate_texts(self, candidates: list[CandidateBill]) -> list[CandidateBill]:
        if not candidates:
            return candidates
        ids = [candidate.bill_id for candidate in candidates]
        rows = self.db.fetch_all(
            """
            SELECT DISTINCT ON (bill_id)
                bill_id,
                LEFT(raw_text, %(char_limit)s) AS raw_text
            FROM public.opencivicdata_searchablebill
            WHERE bill_id = ANY(%(bill_ids)s::varchar[])
              AND is_error = false
            ORDER BY bill_id, created_at DESC, char_length(raw_text) DESC
            """,
            {"bill_ids": ids, "char_limit": get_settings().raw_text_char_limit},
        )
        text_map = {row["bill_id"]: row.get("raw_text") or "" for row in rows}
        for candidate in candidates:
            candidate.raw_text = text_map.get(candidate.bill_id, "")
        return candidates


class FinalReranker:
    def __init__(self) -> None:
        self.client = CodexClient()

    def rerank(self, profile: UploadedBillProfile, candidates: list[CandidateBill]) -> LlmRerankResponse:
        if not candidates:
            return LlmRerankResponse(top_candidates=[], overall_notes="")

        payload = {
            "uploaded_bill": profile.model_dump(),
            "candidates": [
                {
                    "candidate_id": candidate.bill_id,
                    "identifier": candidate.identifier,
                    "title": candidate.title,
                    "jurisdiction": candidate.jurisdiction_name,
                    "state_code": candidate.state_code,
                    "session": candidate.session_identifier,
                    "status": candidate.derived_status,
                    "latest_action_date": candidate.latest_action_date,
                    "latest_action_description": candidate.latest_action_description,
                    "subjects": candidate.subjects,
                    "matched_queries": candidate.matched_queries,
                    "excerpt": candidate.excerpt[:900],
                }
                for candidate in candidates
            ],
        }
        try:
            response = self.client.chat_json(
                system_prompt=RERANK_SYSTEM_PROMPT,
                user_prompt=f"Rank these candidates.\n\n{json.dumps(payload, ensure_ascii=False)}",
            )
            parsed = LlmRerankResponse.model_validate(response)
            if parsed.top_candidates:
                return parsed
        except Exception:
            pass

        return LlmRerankResponse(
            top_candidates=[
                {
                    "candidate_id": candidate.bill_id,
                    "score": candidate.semantic_score,
                    "reason": "Fallback to semantic similarity score.",
                    "match_dimensions": ["semantic fallback"],
                }
                for candidate in candidates
            ],
            overall_notes="Codex rerank unavailable; used semantic fallback.",
        )


class SimilarBillService:
    def __init__(self, db: Database) -> None:
        self.settings = get_settings()
        self.repository = SimilarBillRepository(db)
        self.profile_extractor = BillProfileExtractor()
        self.semantic_ranker = SemanticRanker()
        self.final_reranker = FinalReranker()

    def search(self, *, filename: str, payload: bytes, options: SearchRequestOptions | None = None) -> SearchResult:
        options = options or SearchRequestOptions(final_result_limit=self.settings.final_result_limit)
        file_type = detect_file_type(filename)
        timings: dict[str, float] = {}
        warnings: list[str] = []

        started = time.perf_counter()
        bill_text = extract_text_from_file(file_type, payload)
        uploaded_identifier = _extract_uploaded_bill_identifier(bill_text)
        timings["extract"] = round(time.perf_counter() - started, 3)

        started = time.perf_counter()
        profile = self.profile_extractor.extract(bill_text)
        timings["profile"] = round(time.perf_counter() - started, 3)

        started = time.perf_counter()
        lexical_candidates = self.repository.lexical_candidates(profile, options)
        if uploaded_identifier:
            preview_text = _normalize_text(bill_text[:4000]).lower()
            lexical_candidates = [
                candidate
                for candidate in lexical_candidates
                if not (
                    candidate.identifier.upper() == uploaded_identifier.upper()
                    and _normalize_text(candidate.title).lower() in preview_text
                )
            ]
        timings["lexical"] = round(time.perf_counter() - started, 3)

        if not lexical_candidates:
            warnings.append("No lexical candidates were found in the OpenStates corpus.")
            return SearchResult(
                filename=filename,
                file_type=file_type,
                extracted_text_preview=bill_text[:1500],
                extracted_text_length=len(bill_text),
                profile=profile,
                results=[],
                timings=timings,
                warnings=warnings,
            )

        semantic_candidates = lexical_candidates[: self.settings.semantic_input_limit]
        self.repository.hydrate_candidate_texts(semantic_candidates)

        started = time.perf_counter()
        reranked = self.semantic_ranker.rerank(profile, semantic_candidates)
        timings["semantic"] = round(time.perf_counter() - started, 3)

        llm_input = reranked[: self.settings.llm_rerank_input_limit]
        started = time.perf_counter()
        llm_response = self.final_reranker.rerank(profile, llm_input)
        timings["llm_rerank"] = round(time.perf_counter() - started, 3)

        score_map = {item.candidate_id: item for item in llm_response.top_candidates}
        final_pool = llm_input if llm_input else reranked
        for candidate in final_pool:
            llm_item = score_map.get(candidate.bill_id)
            if llm_item:
                candidate.llm_score = llm_item.score
                candidate.match_reason = llm_item.reason
                candidate.match_dimensions = llm_item.match_dimensions
                candidate.final_score = round(candidate.semantic_score * 0.35 + candidate.llm_score * 0.65, 4)
            else:
                candidate.final_score = round(candidate.semantic_score, 4)
                candidate.match_reason = candidate.match_reason or "Fallback to semantic similarity score."
                candidate.match_dimensions = candidate.match_dimensions or ["semantic fallback"]

        results = sorted(final_pool, key=lambda item: item.final_score, reverse=True)[: options.final_result_limit]
        return SearchResult(
            filename=filename,
            file_type=file_type,
            extracted_text_preview=bill_text[:1500],
            extracted_text_length=len(bill_text),
            profile=profile,
            results=results,
            timings=timings,
            warnings=warnings,
        )
