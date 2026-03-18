import os
import logging
import asyncio
import json
from typing import Dict, Any, Optional

from app.core.config import (
    PROMPTS_DIR,
    DEFAULT_MODEL,
    CONFLICT_ANALYSIS_MAX_ITERATIONS,
    CONFLICT_ANALYSIS_MIN_INTERVAL,
    MAX_BILL_TOKENS,
    DEFAULT_TOKENIZER,
)
from app.utils import (
    load_file,
    load_prompt_template,
    truncate_text,
    get_conflict_analysis_tools,
)
from app.utils.tool_helpers import AgenticLoopConfig, run_agentic_loop
from app.services.llm_client import LLMClient
from app.services.tools.california_code_tools import multi_query_master_json
from app.services.analysis_helpers import (
    is_non_empty_string,
    normalize_phase,
    iter_json_dict_candidates,
    sanitize_analysis_text,
    validate_report_context_for_fixes,
    force_json_retry,
    classify_fixes_improvements_payload,
    build_fallback_improvements,
    build_fixes_classification_payload,
)

logger = logging.getLogger(__name__)

def _is_valid_external_conflict(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    required_fields = [
        "type",
        "bill_section",
        "conflicting_statute",
        "conflicting_text",
        "explanation",
        "risk_level",
    ]
    return all(is_non_empty_string(item.get(field)) for field in required_fields)

def _is_valid_constitutional_issue(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    required_fields = ["issue_id", "type", "bill_section", "explanation", "risk_level"]
    return all(is_non_empty_string(item.get(field)) for field in required_fields)

def _coerce_conflict_report_payload(payload: Any) -> Dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    expected_keys = {"analysis", "report", "summary", "external_conflicts", "constitutional_issues"}
    if not any(key in payload for key in expected_keys):
        return None
    if "external_conflicts" not in payload or "constitutional_issues" not in payload:
        return None

    external = payload.get("external_conflicts", [])
    constitutional = payload.get("constitutional_issues", [])

    if not isinstance(external, list) or not isinstance(constitutional, list):
        return None

    valid_external = [item for item in external if _is_valid_external_conflict(item)]
    valid_constitutional = [item for item in constitutional if _is_valid_constitutional_issue(item)]

    analysis_text = payload.get("analysis") or payload.get("report") or payload.get("summary")

    return {
        "analysis": analysis_text if is_non_empty_string(analysis_text) else "",
        "external_conflicts": valid_external,
        "constitutional_issues": valid_constitutional,
        "legal_improvements": [],
    }

def _extract_best_conflict_report_payload(raw_text: str) -> Dict[str, Any] | None:
    candidates = iter_json_dict_candidates(raw_text)
    coerced_candidates = [candidate for candidate in (_coerce_conflict_report_payload(item) for item in candidates) if candidate is not None]
    if not coerced_candidates:
        return None

    return max(
        coerced_candidates,
        key=lambda payload: len(payload.get("external_conflicts", [])) + len(payload.get("constitutional_issues", [])),
    )

def _default_conflict_report_payload(parse_warning: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "analysis": "",
        "external_conflicts": [],
        "constitutional_issues": [],
        "legal_improvements": [],
    }
    if parse_warning:
        payload["parse_warning"] = parse_warning
    return payload

_CONFLICT_REPORT_RETRY_PROMPT = (
    "Return ONLY valid JSON now. Do NOT include any tool tags or prose. "
    "Top-level keys must be analysis, external_conflicts, constitutional_issues. "
    "Each conflict/issue item must include required fields."
)

_CONFLICT_FIXES_RETRY_PROMPT = (
    "Return ONLY valid JSON now with top-level key improvements as an array. "
    "Each improvement must include a valid hunk-only change string with @@ header and + or - patch lines. "
    "Do not include markdown, prose, tool tags, or file headers."
)

def _fallback_conflict_payload() -> Dict[str, Any]:
    return {
        "phase": "report",
        "analysis": (
            "Fallback legal analysis generated because model output was unavailable. "
            "Review enforcement scope and exemption language before advancing."
        ),
        "structured_data": {
            "external_conflicts": [
                {
                    "type": "Statutory ambiguity",
                    "bill_section": "Enforcement and penalties",
                    "conflicting_statute": "Potential overlap with existing building code enforcement",
                    "conflicting_text": "Agency authority and timelines may overlap with local permitting rules.",
                    "explanation": "Clarify agency coordination and timing to reduce implementation disputes.",
                    "risk_level": "MEDIUM",
                }
            ],
            "constitutional_issues": [
                {
                    "issue_id": "CI-1",
                    "type": "Due process",
                    "bill_section": "Penalty escalation",
                    "explanation": "Consider explicit notice and cure requirements before daily penalties.",
                    "risk_level": "LOW",
                }
            ],
            "legal_improvements": [],
        },
        "iterations": 0,
        "reasoning_steps": 0,
        "warning": "Fallback legal analysis was used.",
    }

def collect_code_queries(tool_name: str, tool_args: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    if tool_name == "multi_query_master_json":
        if "code_queries" not in metadata:
            metadata["code_queries"] = []
        metadata["code_queries"].extend(tool_args.get("queries", []))

async def run_conflict_report_phase(bill_text: str, streaming_state: Any = None) -> Dict[str, Any]:
    logger.info("Conflict report phase started", extra={"event": "conflict_report_phase_started"})
    truncated_bill = truncate_text(bill_text, MAX_BILL_TOKENS, DEFAULT_TOKENIZER)

    system_prompt_path = os.path.join(PROMPTS_DIR, "conflict_analysis_report_system_prompt.txt")
    system_prompt = load_file(system_prompt_path)

    user_prompt_path = os.path.join(PROMPTS_DIR, "conflict_analysis_report_user_prompt.txt")
    user_prompt = load_prompt_template(user_prompt_path, {"bill_text": truncated_bill})

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    final_prompt = (
        "Return ONLY valid JSON with keys: analysis, external_conflicts, constitutional_issues. "
        "Do not include legal_improvements in this report phase."
    )

    config = AgenticLoopConfig(
        max_iterations=CONFLICT_ANALYSIS_MAX_ITERATIONS,
        min_interval=CONFLICT_ANALYSIS_MIN_INTERVAL,
        tools=get_conflict_analysis_tools(),
        tool_functions={"multi_query_master_json": multi_query_master_json},
        final_prompt=final_prompt,
        use_async_tools=True,
    )

    client = LLMClient()

    if streaming_state:
        streaming_state.update(
            operation="Starting legal conflict report",
            progress=10,
            partial_data={
                "phase": "report",
                "analysis": "",
                "structured_data": {"external_conflicts": [], "constitutional_issues": [], "legal_improvements": []},
            },
        )

    try:
        result = await run_agentic_loop(
            initial_messages=messages,
            config=config,
            client=client,
            model=DEFAULT_MODEL,
            metadata_collector=collect_code_queries,
            streaming_state=streaming_state,
        )
    except Exception:
        logger.exception(
            "Conflict report phase failed; using fallback payload",
            extra={"event": "conflict_report_fallback_exception"},
        )
        payload = _fallback_conflict_payload()
        if streaming_state:
            streaming_state.update(
                operation="Preparing legal report output",
                progress=95,
                partial_data=payload,
            )
        return payload

    structured_data = _extract_best_conflict_report_payload(result.analysis)
    parse_failed = structured_data is None

    analysis_text = result.analysis
    if parse_failed:
        logger.warning(
            "Conflict report payload invalid; attempting forced final JSON",
            extra={"event": "conflict_report_forced_json_attempt"},
        )
        repaired_payload, repaired_raw = await force_json_retry(
            result.messages, _CONFLICT_REPORT_RETRY_PROMPT,
            _extract_best_conflict_report_payload, sanitize_analysis_text,
        )
        if repaired_payload is not None:
            structured_data = repaired_payload
            analysis_text = repaired_raw
            parse_failed = False
            logger.info(
                "Conflict report forced JSON recovery succeeded",
                extra={"event": "conflict_report_forced_json_succeeded"},
            )
        else:
            logger.error(
                "Conflict report forced JSON recovery failed",
                extra={"event": "conflict_report_forced_json_failed"},
            )

    if parse_failed:
        structured_data = _default_conflict_report_payload(
            "Failed to parse structured JSON from LLM output; returning empty report fields."
        )
        analysis_text = sanitize_analysis_text(result.analysis, structured_data)
    else:
        analysis_text = structured_data.get("analysis") or sanitize_analysis_text(analysis_text, structured_data)

    payload = {
        "phase": "report",
        "analysis": analysis_text if isinstance(analysis_text, str) else "",
        "structured_data": {
            "external_conflicts": structured_data.get("external_conflicts", []),
            "constitutional_issues": structured_data.get("constitutional_issues", []),
            "legal_improvements": [],
        },
        "iterations": result.iterations,
        "reasoning_steps": len(result.reasoning_history),
    }

    if parse_failed:
        payload["warning"] = "Failed to parse structured report JSON from LLM output"

    if streaming_state:
        streaming_state.update(
            operation="Preparing legal report output",
            progress=95,
            partial_data=payload,
        )

    logger.info(
        "Conflict report phase completed",
        extra={
            "event": "conflict_report_phase_completed",
            "iterations": result.iterations,
            "external_conflicts_count": len(payload["structured_data"]["external_conflicts"]),
            "constitutional_issues_count": len(payload["structured_data"]["constitutional_issues"]),
            "parse_failed": parse_failed,
        },
    )
    return payload

async def run_conflict_fixes_phase(
    bill_text: str,
    report_context: Dict[str, Any],
    streaming_state: Any = None,
) -> Dict[str, Any]:
    logger.info("Conflict fixes phase started", extra={"event": "conflict_fixes_phase_started"})

    err = validate_report_context_for_fixes(report_context)
    if err:
        return {"Error": err}

    truncated_bill = truncate_text(bill_text, MAX_BILL_TOKENS, DEFAULT_TOKENIZER)

    system_prompt_path = os.path.join(PROMPTS_DIR, "conflict_analysis_fixes_system_prompt.txt")
    system_prompt = load_file(system_prompt_path)

    user_prompt_path = os.path.join(PROMPTS_DIR, "conflict_analysis_fixes_user_prompt.txt")
    user_prompt = load_prompt_template(
        user_prompt_path,
        {
            "bill_text": truncated_bill,
            "report_context_json": json.dumps(report_context, indent=2),
        },
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    client = LLMClient()

    if streaming_state:
        streaming_state.update(
            operation="Generating legal fixes",
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
        response = await asyncio.to_thread(client.chat, messages=messages, model=DEFAULT_MODEL)
        response_content = response.get("content", "")
        payload = classify_fixes_improvements_payload(response_content)
    except Exception:
        logger.exception(
            "Conflict fixes phase failed; using fallback improvements",
            extra={"event": "conflict_fixes_fallback_exception"},
        )
        fallback_improvements = build_fallback_improvements(bill_text, domain="legal")
        payload = build_fixes_classification_payload(fallback_improvements, [])
        payload["warning"] = "Generated fallback legal fixes because model output was unavailable."
    if payload["validation_summary"]["invalid"] > 0:
        logger.warning(
            "Conflict fixes primary payload invalid; attempting forced final JSON",
            extra={"event": "conflict_fixes_forced_json_attempt"},
        )
        repaired_payload, _ = await force_json_retry(
            messages,
            _CONFLICT_FIXES_RETRY_PROMPT,
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
            operation="Preparing legal fixes output",
            progress=95,
            partial_data=response_payload,
        )

    logger.info(
        "Conflict fixes phase completed",
        extra={
            "event": "conflict_fixes_phase_completed",
            "improvements_count": len(response_payload["improvements"]),
            "invalid_improvements_count": response_payload["validation_summary"]["invalid"],
        },
    )
    return response_payload

async def analyze_conflicts(
    bill_text: str,
    phase: str = "report",
    report_context: Optional[Dict[str, Any]] = None,
    streaming_state: Any = None,
) -> Dict[str, Any]:
    normalized = normalize_phase(phase)

    if normalized == "report":
        return await run_conflict_report_phase(bill_text=bill_text, streaming_state=streaming_state)

    if normalized == "fixes":
        err = validate_report_context_for_fixes(report_context)
        if err:
            return {"Error": err}
        return await run_conflict_fixes_phase(
            bill_text=bill_text,
            report_context=report_context,
            streaming_state=streaming_state,
        )

    return {"Error": f"Invalid phase '{phase}'. Expected 'report' or 'fixes'."}
