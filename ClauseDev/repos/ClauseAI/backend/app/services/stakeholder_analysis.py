import os
import logging
import asyncio
import json
from typing import Dict, Any, Optional

from app.core.config import (
    PROMPTS_DIR,
    DEFAULT_MODEL,
    STAKEHOLDER_ANALYSIS_MAX_ITERATIONS,
    STAKEHOLDER_ANALYSIS_MIN_INTERVAL,
    MAX_BILL_TOKENS,
    DEFAULT_TOKENIZER,
)
from app.utils import (
    load_file,
    load_prompt_template,
    truncate_text,
    get_stakeholder_analysis_tools,
)
from app.utils.tool_helpers import AgenticLoopConfig, run_agentic_loop
from app.services.llm_client import LLMClient
from app.services.tools.web_search_tools import multi_web_search_ddg
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

def _is_valid_industry_entry(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    required_fields = ["industry", "likely_position", "lobbying_power"]
    return all(is_non_empty_string(item.get(field)) for field in required_fields)

def _coerce_stakeholder_report_payload(payload: Any) -> Dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    expected_keys = {"analysis", "report", "summary", "stakeholder_analysis", "strategic_recommendations"}
    if not any(key in payload for key in expected_keys):
        return None
    if "stakeholder_analysis" not in payload or "strategic_recommendations" not in payload:
        return None

    stakeholder_analysis = payload.get("stakeholder_analysis", {})
    if not isinstance(stakeholder_analysis, dict):
        stakeholder_analysis = {}

    affected_industries = stakeholder_analysis.get("affected_industries", [])
    if not isinstance(affected_industries, list):
        affected_industries = []
    valid_industries = [item for item in affected_industries if _is_valid_industry_entry(item)]

    strategic_recommendations = payload.get("strategic_recommendations", {})
    if not isinstance(strategic_recommendations, dict):
        strategic_recommendations = {}

    analysis_text = payload.get("analysis") or payload.get("report") or payload.get("summary")

    return {
        "analysis": analysis_text if is_non_empty_string(analysis_text) else "",
        "stakeholder_analysis": {**stakeholder_analysis, "affected_industries": valid_industries},
        "language_optimizations": [],
        "strategic_recommendations": strategic_recommendations,
    }

def _extract_best_stakeholder_report_payload(raw_text: str) -> Dict[str, Any] | None:
    candidates = iter_json_dict_candidates(raw_text)
    coerced_candidates = [candidate for candidate in (_coerce_stakeholder_report_payload(item) for item in candidates) if candidate is not None]
    if not coerced_candidates:
        return None
    return max(
        coerced_candidates,
        key=lambda payload: len(payload.get("stakeholder_analysis", {}).get("affected_industries", [])),
    )

def _default_stakeholder_report_payload(parse_warning: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "analysis": "",
        "stakeholder_analysis": {"affected_industries": []},
        "language_optimizations": [],
        "strategic_recommendations": {},
    }
    if parse_warning:
        payload["parse_warning"] = parse_warning
    return payload

_STAKEHOLDER_REPORT_RETRY_PROMPT = (
    "Return ONLY valid JSON now. Do NOT include tool tags or prose. "
    "Top-level keys must be analysis, stakeholder_analysis, strategic_recommendations. "
    "Do not include language_optimizations in this report phase."
)

_STAKEHOLDER_FIXES_RETRY_PROMPT = (
    "Return ONLY valid JSON with top-level key improvements as an array. "
    "Each improvement must include a valid hunk-only change string with @@ header and + or - patch lines. "
    "Do not include markdown, prose, tool tags, or file headers."
)

def _fallback_stakeholder_payload() -> Dict[str, Any]:
    return {
        "phase": "report",
        "analysis": (
            "Fallback stakeholder analysis generated because model output was unavailable. "
            "Review likely support/opposition and sequence outreach before rollout."
        ),
        "structured_data": {
            "stakeholder_analysis": {
                "affected_industries": [
                    {
                        "industry": "Commercial property developers",
                        "likely_position": "MODERATE_OPPOSITION",
                        "lobbying_power": "HIGH",
                        "estimated_entities_affected": "Large statewide developer base",
                        "key_concerns": [
                            "Upfront capital costs",
                            "Construction timeline impacts",
                            "Permit and grid interconnection uncertainty",
                        ],
                    },
                    {
                        "industry": "EV charging providers",
                        "likely_position": "SUPPORT",
                        "lobbying_power": "MEDIUM",
                        "estimated_entities_affected": "Regional infrastructure vendors",
                        "key_concerns": [
                            "Standardized deployment requirements",
                            "Interoperability expectations",
                        ],
                    },
                ]
            },
            "language_optimizations": [],
            "strategic_recommendations": {
                "priority_actions": [
                    "Phase compliance dates",
                    "Publish technical guidance early",
                    "Pair penalties with technical assistance",
                ]
            },
        },
        "metadata": {
            "iterations": 0,
            "reasoning_steps": 0,
            "web_searches_performed": 0,
            "search_queries": [],
        },
        "warning": "Fallback stakeholder analysis was used.",
    }

def collect_search_queries(tool_name: str, tool_args: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    if tool_name == "multi_web_search_ddg":
        if "search_queries" not in metadata:
            metadata["search_queries"] = []
        metadata["search_queries"].extend(tool_args.get("queries", []))

async def run_stakeholder_report_phase(bill_text: str, streaming_state: Any = None) -> Dict[str, Any]:
    logger.info("Stakeholder report phase started", extra={"event": "stakeholder_report_phase_started"})
    truncated_bill = truncate_text(bill_text, MAX_BILL_TOKENS, DEFAULT_TOKENIZER)

    system_prompt_path = os.path.join(PROMPTS_DIR, "stakeholder_analysis_report_system_prompt.txt")
    system_prompt = load_file(system_prompt_path)

    user_prompt_path = os.path.join(PROMPTS_DIR, "stakeholder_analysis_report_user_prompt.txt")
    user_prompt = load_prompt_template(user_prompt_path, {"bill_text": truncated_bill})

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    final_prompt = (
        "Return ONLY valid JSON with keys: analysis, stakeholder_analysis, strategic_recommendations. "
        "Do not include language_optimizations in this report phase."
    )

    config = AgenticLoopConfig(
        max_iterations=STAKEHOLDER_ANALYSIS_MAX_ITERATIONS,
        min_interval=STAKEHOLDER_ANALYSIS_MIN_INTERVAL,
        tools=get_stakeholder_analysis_tools(),
        tool_functions={"multi_web_search_ddg": multi_web_search_ddg},
        final_prompt=final_prompt,
        use_async_tools=True,
    )

    client = LLMClient()

    if streaming_state:
        streaming_state.update(
            operation="Starting stakeholder report",
            progress=10,
            partial_data={
                "phase": "report",
                "analysis": "",
                "structured_data": {
                    "stakeholder_analysis": {"affected_industries": []},
                    "language_optimizations": [],
                    "strategic_recommendations": {},
                },
            },
        )

    try:
        result = await run_agentic_loop(
            initial_messages=messages,
            config=config,
            client=client,
            model=DEFAULT_MODEL,
            metadata_collector=collect_search_queries,
            streaming_state=streaming_state,
        )
    except Exception:
        logger.exception(
            "Stakeholder report phase failed; using fallback payload",
            extra={"event": "stakeholder_report_fallback_exception"},
        )
        payload = _fallback_stakeholder_payload()
        if streaming_state:
            streaming_state.update(
                operation="Preparing stakeholder report output",
                progress=95,
                partial_data=payload,
            )
        return payload

    search_queries = result.metadata.get("search_queries", [])

    structured_data = _extract_best_stakeholder_report_payload(result.analysis)
    parse_failed = structured_data is None

    analysis_text = result.analysis
    if parse_failed:
        logger.warning(
            "Stakeholder report payload invalid; attempting forced final JSON",
            extra={"event": "stakeholder_report_forced_json_attempt"},
        )
        repaired_payload, repaired_raw = await force_json_retry(
            result.messages, _STAKEHOLDER_REPORT_RETRY_PROMPT,
            _extract_best_stakeholder_report_payload, sanitize_analysis_text,
        )
        if repaired_payload is not None:
            structured_data = repaired_payload
            analysis_text = repaired_raw
            parse_failed = False
            logger.info(
                "Stakeholder report forced JSON recovery succeeded",
                extra={"event": "stakeholder_report_forced_json_succeeded"},
            )
        else:
            logger.error(
                "Stakeholder report forced JSON recovery failed",
                extra={"event": "stakeholder_report_forced_json_failed"},
            )

    if parse_failed:
        structured_data = _default_stakeholder_report_payload(
            "Failed to parse structured JSON from LLM output; returning empty report fields."
        )
        analysis_text = sanitize_analysis_text(result.analysis, structured_data)
    else:
        analysis_text = structured_data.get("analysis") or sanitize_analysis_text(analysis_text, structured_data)

    payload = {
        "phase": "report",
        "analysis": analysis_text if isinstance(analysis_text, str) else "",
        "structured_data": {
            "stakeholder_analysis": structured_data.get("stakeholder_analysis", {"affected_industries": []}),
            "language_optimizations": [],
            "strategic_recommendations": structured_data.get("strategic_recommendations", {}),
        },
        "metadata": {
            "iterations": result.iterations,
            "reasoning_steps": len(result.reasoning_history),
            "web_searches_performed": len(search_queries),
            "search_queries": search_queries,
        },
    }

    if parse_failed:
        payload["warning"] = "Failed to parse structured report JSON from LLM output"

    if streaming_state:
        streaming_state.update(
            operation="Preparing stakeholder report output",
            progress=95,
            partial_data=payload,
        )

    logger.info(
        "Stakeholder report phase completed",
        extra={
            "event": "stakeholder_report_phase_completed",
            "iterations": result.iterations,
            "web_searches_performed": len(search_queries),
            "affected_industries_count": len(payload["structured_data"]["stakeholder_analysis"].get("affected_industries", [])),
            "parse_failed": parse_failed,
        },
    )
    return payload

async def run_stakeholder_fixes_phase(
    bill_text: str,
    report_context: Dict[str, Any],
    streaming_state: Any = None,
) -> Dict[str, Any]:
    logger.info("Stakeholder fixes phase started", extra={"event": "stakeholder_fixes_phase_started"})

    err = validate_report_context_for_fixes(report_context)
    if err:
        return {"Error": err}

    truncated_bill = truncate_text(bill_text, MAX_BILL_TOKENS, DEFAULT_TOKENIZER)

    system_prompt_path = os.path.join(PROMPTS_DIR, "stakeholder_analysis_fixes_system_prompt.txt")
    system_prompt = load_file(system_prompt_path)

    user_prompt_path = os.path.join(PROMPTS_DIR, "stakeholder_analysis_fixes_user_prompt.txt")
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
            operation="Generating stakeholder fixes",
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
            "Stakeholder fixes phase failed; using fallback improvements",
            extra={"event": "stakeholder_fixes_fallback_exception"},
        )
        fallback_improvements = build_fallback_improvements(bill_text, domain="stakeholder")
        payload = build_fixes_classification_payload(fallback_improvements, [])
        payload["warning"] = "Generated fallback stakeholder fixes because model output was unavailable."
    if payload["validation_summary"]["invalid"] > 0:
        logger.warning(
            "Stakeholder fixes primary payload invalid; attempting forced final JSON",
            extra={"event": "stakeholder_fixes_forced_json_attempt"},
        )
        repaired_payload, _ = await force_json_retry(
            messages,
            _STAKEHOLDER_FIXES_RETRY_PROMPT,
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
            operation="Preparing stakeholder fixes output",
            progress=95,
            partial_data=response_payload,
        )

    logger.info(
        "Stakeholder fixes phase completed",
        extra={
            "event": "stakeholder_fixes_phase_completed",
            "improvements_count": len(response_payload["improvements"]),
            "invalid_improvements_count": response_payload["validation_summary"]["invalid"],
        },
    )
    return response_payload


async def analyze_stakeholders(
    bill_text: str,
    phase: str = "report",
    report_context: Optional[Dict[str, Any]] = None,
    streaming_state: Any = None,
) -> Dict[str, Any]:
    normalized = normalize_phase(phase)

    if normalized == "report":
        return await run_stakeholder_report_phase(bill_text=bill_text, streaming_state=streaming_state)

    if normalized == "fixes":
        err = validate_report_context_for_fixes(report_context)
        if err:
            return {"Error": err}
        return await run_stakeholder_fixes_phase(
            bill_text=bill_text,
            report_context=report_context,
            streaming_state=streaming_state,
        )

    return {"Error": f"Invalid phase '{phase}'. Expected 'report' or 'fixes'."}
