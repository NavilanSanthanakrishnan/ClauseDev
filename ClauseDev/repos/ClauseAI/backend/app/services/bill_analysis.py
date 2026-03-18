import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional

from app.core.config import (
    PROMPTS_DIR,
    DEFAULT_MODEL,
    DEFAULT_JURISDICTION,
)
from app.utils import load_file, load_prompt_template, extract_json_from_text
from app.services.llm_client import LLMClient
from app.services.analysis_helpers import (
    is_non_empty_string,
    normalize_phase,
    classify_fixes_improvements_payload,
    build_fallback_improvements,
    build_fixes_classification_payload,
    force_json_retry,
)

logger = logging.getLogger(__name__)

_BILL_FIXES_RETRY_PROMPT = (
    "Return ONLY valid JSON with top-level key improvements as an array. "
    "Each improvement must include a valid hunk-only change string with @@ header and + or - patch lines. "
    "Do not include markdown, prose, or file headers."
)

def _extract_report_payload(raw_text: str) -> Dict[str, Any] | None:
    parsed = extract_json_from_text(raw_text)
    if not isinstance(parsed, dict):
        return None

    report = parsed.get("report")
    if not is_non_empty_string(report):
        return None

    return {
        "report": report.strip(),
    }

def _build_fallback_report(
    policy_area: str,
    passed_count: int,
    failed_count: int,
) -> str:
    area = policy_area or "the proposed policy area"
    return (
        "## Bill Analysis Summary (Fallback)\n\n"
        f"- Policy area: {area}\n"
        f"- Similar bills reviewed: {passed_count + failed_count} "
        f"({passed_count} passed / {failed_count} failed)\n"
        "- Key recommendation: clarify implementation timelines, exemptions, and enforcement language.\n"
        "- Next step: apply generated fixes and re-run legal/stakeholder analysis.\n"
    )

async def run_bill_report_phase(
    user_bill: Dict[str, Any],
    user_bill_raw_text: str,
    passed_bills: list,
    failed_bills: list,
    policy_area: str,
    jurisdiction: str = DEFAULT_JURISDICTION,
    streaming_state: Optional[Any] = None,
) -> Dict[str, Any]:
    logger.info(
        "Bill report phase started",
        extra={
            "event": "bill_report_phase_started",
            "passed_count": len(passed_bills),
            "failed_count": len(failed_bills),
            "jurisdiction": jurisdiction,
        },
    )

    system_prompt_path = os.path.join(PROMPTS_DIR, "bill_analysis_report_system_prompt.txt")
    system_prompt = load_file(system_prompt_path)

    user_prompt_path = os.path.join(PROMPTS_DIR, "bill_analysis_report_user_prompt.txt")
    user_prompt = load_prompt_template(
        user_prompt_path,
        {
            "num_passed": len(passed_bills),
            "num_failed": len(failed_bills),
            "policy_area": policy_area,
            "user_bill_json": json.dumps(user_bill, indent=4),
            "user_jurisdiction": jurisdiction,
            "passed_bills_json": json.dumps(passed_bills, indent=4),
            "failed_bills_json": json.dumps(failed_bills, indent=4),
            "user_bill_raw_text": user_bill_raw_text,
        },
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    client = LLMClient()

    if streaming_state:
        streaming_state.update(
            operation="Generating bill analysis report",
            progress=30,
            partial_data={"phase": "report", "report": ""},
        )

    try:
        response = await asyncio.to_thread(
            client.chat,
            messages=messages,
            model=DEFAULT_MODEL,
        )
        response_content = response.get("content", "")
        payload = _extract_report_payload(response_content)
    except Exception as error:
        logger.exception(
            "Bill report phase failed; using fallback report",
            extra={"event": "bill_report_fallback_exception"},
        )
        response_content = str(error)
        payload = None

    if not payload:
        logger.warning(
            "Bill report phase JSON parsing failed; using fallback report",
            extra={"event": "bill_report_parse_fallback"},
        )
        payload = {
            "report": _build_fallback_report(
                policy_area=policy_area,
                passed_count=len(passed_bills),
                failed_count=len(failed_bills),
            )
        }

    if streaming_state:
        streaming_state.update(
            operation="Bill report phase complete",
            progress=95,
            partial_data={"phase": "report", "report": payload["report"]},
        )

    logger.info("Bill report phase completed", extra={"event": "bill_report_phase_completed"})
    return {
        "phase": "report",
        "report": payload["report"],
    }

async def run_bill_fixes_phase(
    user_bill: Dict[str, Any],
    user_bill_raw_text: str,
    passed_bills: list,
    failed_bills: list,
    policy_area: str,
    report_context: Dict[str, Any],
    jurisdiction: str = DEFAULT_JURISDICTION,
    streaming_state: Optional[Any] = None,
) -> Dict[str, Any]:
    report_text = report_context.get("report") if isinstance(report_context, dict) else None
    if not is_non_empty_string(report_text):
        return {"Error": "Missing report_context.report for fixes phase"}

    logger.info(
        "Bill fixes phase started",
        extra={
            "event": "bill_fixes_phase_started",
            "passed_count": len(passed_bills),
            "failed_count": len(failed_bills),
            "jurisdiction": jurisdiction,
        },
    )

    system_prompt_path = os.path.join(PROMPTS_DIR, "bill_analysis_fixes_system_prompt.txt")
    system_prompt = load_file(system_prompt_path)

    user_prompt_path = os.path.join(PROMPTS_DIR, "bill_analysis_fixes_user_prompt.txt")
    user_prompt = load_prompt_template(
        user_prompt_path,
        {
            "policy_area": policy_area,
            "user_bill_json": json.dumps(user_bill, indent=4),
            "user_jurisdiction": jurisdiction,
            "passed_bills_json": json.dumps(passed_bills, indent=4),
            "failed_bills_json": json.dumps(failed_bills, indent=4),
            "user_bill_raw_text": user_bill_raw_text,
            "report_text": report_text,
        },
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    client = LLMClient()

    if streaming_state:
        streaming_state.update(
            operation="Generating bill fixes",
            progress=30,
            partial_data={
                "phase": "fixes",
                "improvements": [],
                "valid_improvement_indices": [],
                "invalid_improvements": [],
                "validation_summary": {"total": 0, "valid": 0, "invalid": 0},
            },
        )

    try:
        response = await asyncio.to_thread(
            client.chat,
            messages=messages,
            model=DEFAULT_MODEL,
        )
        response_content = response.get("content", "")
        payload = classify_fixes_improvements_payload(response_content)
    except Exception:
        logger.exception(
            "Bill fixes phase failed; using fallback improvements",
            extra={"event": "bill_fixes_fallback_exception"},
        )
        fallback_improvements = build_fallback_improvements(user_bill_raw_text, domain="bill")
        payload = build_fixes_classification_payload(fallback_improvements, [])
        payload["warning"] = "Generated fallback fixes because model output was unavailable."

    if payload["validation_summary"]["invalid"] > 0:
        logger.warning(
            "Bill fixes primary payload has invalid patches; attempting forced final JSON",
            extra={"event": "bill_fixes_forced_json_attempt"},
        )
        repaired_payload, _ = await force_json_retry(
            messages,
            _BILL_FIXES_RETRY_PROMPT,
            classify_fixes_improvements_payload,
        )
        if (
            isinstance(repaired_payload, dict)
            and (
                repaired_payload.get("validation_summary", {}).get("valid", 0)
                > payload.get("validation_summary", {}).get("valid", 0)
                or (
                    repaired_payload.get("validation_summary", {}).get("valid", 0)
                    == payload.get("validation_summary", {}).get("valid", 0)
                    and repaired_payload.get("validation_summary", {}).get("invalid", 0)
                    < payload.get("validation_summary", {}).get("invalid", 0)
                )
            )
        ):
            payload = repaired_payload

    response_payload = {
        "phase": "fixes",
        "improvements": payload["improvements"],
        "valid_improvement_indices": payload["valid_improvement_indices"],
        "invalid_improvements": payload["invalid_improvements"],
        "validation_summary": payload["validation_summary"],
    }
    if payload.get("warning"):
        response_payload["warning"] = payload["warning"]

    if streaming_state:
        streaming_state.update(
            operation="Bill fixes phase complete",
            progress=95,
            partial_data=response_payload,
        )

    logger.info(
        "Bill fixes phase completed",
        extra={
            "event": "bill_fixes_phase_completed",
            "improvements_count": len(response_payload["improvements"]),
            "invalid_improvements_count": response_payload["validation_summary"]["invalid"],
        },
    )
    return response_payload

async def analyze_bill(
    user_bill: Dict[str, Any],
    user_bill_raw_text: str,
    passed_bills: list,
    failed_bills: list,
    policy_area: str,
    jurisdiction: str = DEFAULT_JURISDICTION,
    phase: str = "report",
    report_context: Optional[Dict[str, Any]] = None,
    streaming_state: Optional[Any] = None,
) -> Dict[str, Any]:
    normalized = normalize_phase(phase)

    if normalized == "report":
        return await run_bill_report_phase(
            user_bill=user_bill,
            user_bill_raw_text=user_bill_raw_text,
            passed_bills=passed_bills,
            failed_bills=failed_bills,
            policy_area=policy_area,
            jurisdiction=jurisdiction,
            streaming_state=streaming_state,
        )

    if normalized == "fixes":
        if not isinstance(report_context, dict) or not is_non_empty_string(report_context.get("report")):
            return {"Error": "Missing report_context.report for fixes phase"}
        return await run_bill_fixes_phase(
            user_bill=user_bill,
            user_bill_raw_text=user_bill_raw_text,
            passed_bills=passed_bills,
            failed_bills=failed_bills,
            policy_area=policy_area,
            report_context=report_context,
            jurisdiction=jurisdiction,
            streaming_state=streaming_state,
        )

    return {"Error": f"Invalid phase '{phase}'. Expected 'report' or 'fixes'."}
