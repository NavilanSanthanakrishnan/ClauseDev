import json
import os
import re
import asyncio
import logging
from typing import Dict, Any, List, Tuple, Optional

from app.core.config import (
    BILLS_DATA_DIR,
    DEFAULT_JURISDICTION,
    PROMPTS_DIR,
    DEFAULT_MODEL,
    MAX_BILL_TOKENS,
    DEFAULT_TOKENIZER,
    LOADER_MAX_TOKENS_PER_BATCH,
    LOADER_MAX_RETRIES,
    LOADER_LLM_TIMEOUT_SECONDS,
)
from app.services.llm_client import LLMClient
from app.services.business_data_repository import business_data_repo
from app.utils import load_file, truncate_text, count_tokens, extract_json_from_text
from app.utils.bill_cleaning import clean_bill_text

logger = logging.getLogger(__name__)

def bill_text_to_sentences(bill_text: str) -> List[str]:
    return [sentence.strip() for sentence in bill_text.split("\n") if sentence.strip()]

def format_bill_with_sentences(bill_id: str, bill_text: str, cleaned_text: str = "") -> Dict[str, Any]:
    sentences = bill_text_to_sentences(bill_text)
    numbered_sentences = "\n".join([f"{i}: {sentence}" for i, sentence in enumerate(sentences)])
    return {
        "bill_id": bill_id,
        "sentences": sentences,
        "formatted_text": f"Bill ID: {bill_id}\n\nSentences:\n{numbered_sentences}\n\n{'=' * 60}",
        "cleaned_text": cleaned_text
    }

def resolve_sentence_indices(bill_data: Dict[str, Any], indices_result: Dict[str, Any]) -> Dict[str, Any]:
    resolved = {
        "Bill ID": indices_result.get("Bill ID"),
        "Bill Number": indices_result.get("Bill Number")
    }
    categories = [
        "Citations",
        "Exemptions",
        "Definitions",
        "Requirements",
        "Prohibitions",
        "Enforcement Mechanisms",
        "Findings and Declarations",
        "Other"
    ]
    sentences = bill_data["sentences"]

    for category in categories:
        indices = indices_result.get(category, [])
        resolved[category] = [
            sentences[idx]
            for idx in indices
            if isinstance(idx, int) and 0 <= idx < len(sentences)
        ]

    return resolved

def parse_categorized_payload(raw_content: str) -> List[Dict[str, Any]]:
    fence_match = re.search(r"```json\s+(.+?)\s+```", raw_content, re.DOTALL)
    if fence_match:
        raw_content = fence_match.group(1).strip()

    parsed = extract_json_from_text(raw_content)

    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []

def _keyword_belongs_to(category: str, sentence_lower: str) -> bool:
    keyword_map = {
        "Citations": ["section", "chapter", "division", "article", "title", "code", "section "],
        "Exemptions": ["exempt", "does not apply", "unless", "except", "infeasible"],
        "Definitions": [" means ", "for purposes of this", "definition"],
        "Requirements": [" shall ", " must ", "required", "install", "comply"],
        "Prohibitions": ["shall not", "may not", "prohibited", "no person shall"],
        "Enforcement Mechanisms": ["enforce", "penalt", "violation", "warning", "noncompliance"],
        "Findings and Declarations": ["whereas", "findings", "declaration", "intent"],
    }
    return any(keyword in sentence_lower for keyword in keyword_map.get(category, []))

def _fallback_categorize_bill(bill_data: Dict[str, Any]) -> Dict[str, Any]:
    categories = [
        "Citations",
        "Exemptions",
        "Definitions",
        "Requirements",
        "Prohibitions",
        "Enforcement Mechanisms",
        "Findings and Declarations",
        "Other",
    ]
    result: Dict[str, Any] = {
        "Bill ID": bill_data.get("bill_id"),
        "Bill Number": bill_data.get("bill_id"),
    }
    for category in categories:
        result[category] = []

    for sentence in bill_data.get("sentences", []):
        normalized = sentence.lower()
        matched_category = None
        for category in categories[:-1]:
            if _keyword_belongs_to(category, normalized):
                matched_category = category
                break
        result[matched_category or "Other"].append(sentence)

    return result

async def extract_categorized_sentences(
    bill_data_list: List[Dict[str, Any]],
    system_prompt: str,
    prompt_template: str,
    max_retries: int = LOADER_MAX_RETRIES
) -> List[Dict[str, Any]]:
    formatted_bills_text = "\n" + "=" * 60 + "\n\n" + "\n\n".join(
        [bill_data["formatted_text"] for bill_data in bill_data_list]
    )
    prompt = prompt_template.replace("{new_bill_sentences}", formatted_bills_text)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    client = LLMClient()
    for retry in range(max_retries):
        try:
            logger.info(
                "Extracting categorized sentences",
                extra={
                    "event": "loader_extract_attempt",
                    "attempt": retry + 1,
                    "max_retries": max_retries,
                    "batch_size": len(bill_data_list),
                },
            )
            response = await asyncio.wait_for(
                asyncio.to_thread(client.chat, messages=messages, model=DEFAULT_MODEL),
                timeout=LOADER_LLM_TIMEOUT_SECONDS,
            )
            parsed_indices = parse_categorized_payload(response["content"])
            if not parsed_indices:
                if retry < max_retries - 1:
                    logger.warning(
                        "Failed to parse categorized sentence payload; retrying",
                        extra={"event": "loader_parse_retry", "attempt": retry + 1},
                    )
                    continue
                logger.error(
                    "Failed to parse categorized sentence payload after retries",
                    extra={"event": "loader_parse_failed", "attempts": max_retries},
                )
                return [_fallback_categorize_bill(bill_data) for bill_data in bill_data_list]

            resolved_results = []
            for idx, indices_result in enumerate(parsed_indices):
                if idx < len(bill_data_list) and isinstance(indices_result, dict):
                    resolved_results.append(resolve_sentence_indices(bill_data_list[idx], indices_result))
                else:
                    resolved_results.append(indices_result)
            return resolved_results
        except Exception as error:
            if retry == max_retries - 1:
                logger.exception(
                    "Categorized sentence extraction failed",
                    extra={"event": "loader_extract_failed", "attempts": max_retries},
                )
                return [_fallback_categorize_bill(bill_data) for bill_data in bill_data_list]

    return [_fallback_categorize_bill(bill_data) for bill_data in bill_data_list]

def build_loaded_bill_result(
    bill_meta: Dict[str, Any],
    match: Dict[str, Any],
    categorized_sentences: Dict[str, Any],
    bill_text: str = ""
) -> Dict[str, Any]:
    return {
        "Bill_ID": str(match["Bill_ID"]),
        "Bill_Number": match.get("Bill_Number") or bill_meta.get("Bill Number"),
        "Bill_Title": match.get("Bill_Title") or bill_meta.get("Bill Title", ""),
        "Bill_Description": match.get("Bill_Description") or bill_meta.get("Bill Description", ""),
        "Bill_URL": match.get("Bill_URL") or bill_meta.get("Bill URL"),
        "Date_Presented": match.get("Date_Presented") or bill_meta.get("Date Presented"),
        "Date_Passed": match.get("Date_Passed") or bill_meta.get("Date Passed"),
        "Votes": match.get("Votes") or bill_meta.get("Votes"),
        "Stage_Passed": match.get("Stage_Passed") if match.get("Stage_Passed") is not None else bill_meta.get("Stage Passed"),
        "Bill_Text": bill_text,
        "Categorized_Sentences": categorized_sentences,
        "Passed": match.get("Passed", False)
    }

def build_token_batches(
    matches: List[Dict[str, Any]],
    jurisdiction: str
) -> List[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
    batches: List[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]] = []
    current_bill_batch: List[Dict[str, Any]] = []
    current_meta_batch: List[Dict[str, Any]] = []
    current_tokens = 0

    for match in matches:
        bill_id = match["Bill_ID"]
        bill_path = os.path.join(BILLS_DATA_DIR, jurisdiction, f"cleaned_bills/{bill_id}.txt")
        try:
            bill_text = business_data_repo.read_text(bill_path)
        except FileNotFoundError:
            continue

        cleaned_bill_text = clean_bill_text(bill_text, aggressive=True)
        truncated_text = truncate_text(cleaned_bill_text, MAX_BILL_TOKENS, DEFAULT_TOKENIZER)
        bill_data = format_bill_with_sentences(
            bill_id,
            truncated_text,
            cleaned_text=truncated_text
        )
        token_count = count_tokens(bill_data["formatted_text"], DEFAULT_TOKENIZER)

        if current_bill_batch and current_tokens + token_count > LOADER_MAX_TOKENS_PER_BATCH:
            batches.append((current_bill_batch, current_meta_batch))
            current_bill_batch = []
            current_meta_batch = []
            current_tokens = 0

        current_bill_batch.append(bill_data)
        current_meta_batch.append(match)
        current_tokens += token_count

    if current_bill_batch:
        batches.append((current_bill_batch, current_meta_batch))

    return batches

def get_batch_progress(start: int, end: int, batch_index: int, total_batches: int) -> int:
    if total_batches <= 0:
        return end
    return start + int(((batch_index + 1) / total_batches) * (end - start))

def append_preview_items(
    preview_accumulator: List[Dict[str, Any]],
    batch_meta: List[Dict[str, Any]],
    categorized_batch: List[Dict[str, Any]]
) -> None:
    for idx, categorized_item in enumerate(categorized_batch):
        if idx >= len(batch_meta):
            continue
        preview_item = dict(categorized_item) if isinstance(categorized_item, dict) else {"value": categorized_item}
        preview_item["Bill_ID"] = str(batch_meta[idx].get("Bill_ID"))
        preview_item["Bill_Number"] = batch_meta[idx].get("Bill_Number")
        preview_item["Bill_Title"] = batch_meta[idx].get("Bill_Title")
        preview_item["Bill_Description"] = batch_meta[idx].get("Bill_Description")
        preview_item["Bill_URL"] = batch_meta[idx].get("Bill_URL")
        preview_item["Passed"] = batch_meta[idx].get("Passed", False)
        preview_accumulator.append(preview_item)

async def process_match_group(
    matches: List[Dict[str, Any]],
    group_label: str,
    progress_start: int,
    progress_end: int,
    jurisdiction: str,
    system_prompt: str,
    prompt_template: str,
    bill_lookup: Dict[str, Dict[str, Any]],
    preview_accumulator: List[Dict[str, Any]],
    user_bill_preview: Optional[Dict[str, Any]] = None,
    streaming_state: Any = None
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    batches = await asyncio.to_thread(build_token_batches, matches, jurisdiction)
    logger.info(
        "Processing match group",
        extra={
            "event": "loader_group_processing",
            "group_label": group_label,
            "input_matches": len(matches),
            "batches": len(batches),
        },
    )

    for batch_index, (bill_batch, meta_batch) in enumerate(batches):
        if streaming_state:
            batch_progress = get_batch_progress(progress_start, progress_end, batch_index, len(batches))
            streaming_state.update(
                operation=f"Processing {group_label} bills batch {batch_index + 1}/{len(batches)}",
                progress=batch_progress
            )

        categorized_batch = await extract_categorized_sentences(
            bill_batch,
            system_prompt,
            prompt_template
        )

        append_preview_items(preview_accumulator, meta_batch, categorized_batch)
        if streaming_state:
            streaming_state.update(
                partial_data={
                    "user_bill": user_bill_preview,
                    "similar_bills": preview_accumulator
                }
            )

        for idx, categorized in enumerate(categorized_batch):
            if idx >= len(meta_batch):
                continue
            match = meta_batch[idx]
            bill_meta = bill_lookup.get(str(match["Bill_ID"]), {})
            results.append(
                build_loaded_bill_result(
                    bill_meta,
                    match,
                    categorized,
                    bill_text=bill_batch[idx].get("cleaned_text", "")
                )
            )

    return results

async def load_similar_bills(
    similarity_matches: List[Dict[str, Any]],
    user_bill_text: str,
    user_bill_metadata: Dict[str, Any] = None,
    jurisdiction: str = DEFAULT_JURISDICTION,
    streaming_state: Any = None
) -> Dict[str, Any]:
    logger.info(
        "Starting similar bills loading",
        extra={"event": "loader_started", "match_count": len(similarity_matches), "jurisdiction": jurisdiction},
    )
    system_prompt = load_file(os.path.join(PROMPTS_DIR, "similar_bills_loader_system_prompt.txt"))
    prompt_template = load_file(os.path.join(PROMPTS_DIR, "similar_bills_loader_user_prompt.txt"))

    master_data = business_data_repo.read_json(os.path.join(BILLS_DATA_DIR, jurisdiction, "master.json"))
    bill_lookup = {str(bill["Bill ID"]): bill for bill in master_data}

    if streaming_state:
        streaming_state.update(operation="Processing user bill", progress=10)

    cleaned_user_bill_text = clean_bill_text(user_bill_text, aggressive=True)
    user_bill_data = await asyncio.to_thread(
        lambda: format_bill_with_sentences(
            "USER_BILL",
            truncate_text(cleaned_user_bill_text, MAX_BILL_TOKENS, DEFAULT_TOKENIZER)
        )
    )
    user_bill_categorized = await extract_categorized_sentences(
        [user_bill_data],
        system_prompt,
        prompt_template
    )
    user_bill_result = user_bill_categorized[0] if user_bill_categorized else {"Error": "Failed to process user bill"}
    if user_bill_metadata:
        user_bill_result.update(user_bill_metadata)
    if streaming_state:
        streaming_state.update(
            operation="User bill categorized; loading similar bills",
            progress=18,
            partial_data={
                "user_bill": user_bill_result,
                "similar_bills": []
            }
        )

    passed_matches = [match for match in similarity_matches if match.get("Passed", False)]
    failed_matches = [match for match in similarity_matches if not match.get("Passed", False)]
    preview_accumulator: List[Dict[str, Any]] = []

    passed_bills = await process_match_group(
        matches=passed_matches,
        group_label="passed",
        progress_start=20,
        progress_end=70,
        jurisdiction=jurisdiction,
        system_prompt=system_prompt,
        prompt_template=prompt_template,
        bill_lookup=bill_lookup,
        preview_accumulator=preview_accumulator,
        user_bill_preview=user_bill_result,
        streaming_state=streaming_state
    )
    failed_bills = await process_match_group(
        matches=failed_matches,
        group_label="failed",
        progress_start=70,
        progress_end=95,
        jurisdiction=jurisdiction,
        system_prompt=system_prompt,
        prompt_template=prompt_template,
        bill_lookup=bill_lookup,
        preview_accumulator=preview_accumulator,
        user_bill_preview=user_bill_result,
        streaming_state=streaming_state
    )

    if streaming_state:
        streaming_state.update(operation="Finalizing similar bills output", progress=98)

    return {
        "User_Bill": user_bill_result,
        "Passed_Bills": passed_bills,
        "Failed_Bills": failed_bills
    }
