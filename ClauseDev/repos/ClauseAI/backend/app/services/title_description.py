import os
import asyncio
from typing import Dict, Any, Optional

from app.core.config import (
    PROMPTS_DIR,
    SAMPLES_DIR,
    DEFAULT_MODEL,
    MAX_BILL_TOKENS,
    DEFAULT_TOKENIZER
)
from app.utils import load_file, load_prompt_template, truncate_text, extract_json_from_text
from app.services.llm_client import LLMClient

async def generate_title_desc_summary(
    bill_text: str,
    example_bill: Optional[str] = None,
    example_title: Optional[str] = None,
    example_description: Optional[str] = None,
    example_summary: Optional[str] = None
) -> Dict[str, Any]:
    if not example_bill:
        example_bill_path = os.path.join(SAMPLES_DIR, "title_description/sample_bill.txt")
        example_bill = load_file(example_bill_path)
    
    if not example_title:
        example_title_path = os.path.join(SAMPLES_DIR, "title_description/sample_title.txt")
        example_title = load_file(example_title_path)
    
    if not example_description:
        example_desc_path = os.path.join(SAMPLES_DIR, "title_description/sample_desc.txt")
        example_description = load_file(example_desc_path)
    
    if not example_summary:
        example_summary_path = os.path.join(SAMPLES_DIR, "title_description/sample_summary.txt")
        example_summary = load_file(example_summary_path)
    
    truncated_bill_text = truncate_text(
        bill_text,
        max_tokens=MAX_BILL_TOKENS,
        tokenizer_name=DEFAULT_TOKENIZER
    )
    
    system_prompt_path = os.path.join(PROMPTS_DIR, "title_description_system_prompt.txt")
    system_prompt = load_file(system_prompt_path)
    
    user_prompt_path = os.path.join(PROMPTS_DIR, "title_description_user_prompt.txt")
    user_prompt = load_prompt_template(user_prompt_path, {
        "example_bill": example_bill,
        "example_title": example_title,
        "example_description": example_description,
        "example_summary": example_summary,
        "truncated_bill_text": truncated_bill_text
    })
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    client = LLMClient()
    response = await asyncio.to_thread(client.chat, messages=messages, model=DEFAULT_MODEL)
    
    try:
        parsed = extract_json_from_text(response.get("content", ""))
        if not isinstance(parsed, dict):
            raise ValueError("Response is not a JSON object")

        return {
            "Title": parsed.get("Title", parsed.get("title", "")) or "",
            "Description": parsed.get("Description", parsed.get("description", "")) or "",
            "Summary": parsed.get("Summary", parsed.get("summary", "")) or ""
        }
    
    except ValueError:
        return {
            "Title": "",
            "Description": "",
            "Summary": "",
            "Error": "Failed to parse JSON from response",
            "Raw_Response": response.get("content", "")
        }
