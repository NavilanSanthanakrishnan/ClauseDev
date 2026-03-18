from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from clauseai_backend.core.config import settings
from clauseai_backend.db.session import ReferenceDatabases
from clauseai_backend.services.codex_auth import CodexAuthError, codex_auth_available
from clauseai_backend.services.openai_compat_client import openai_compat_available, openai_compat_chat_json
from clauseai_backend.services.codex_client import CodexClient
from clauseai_backend.services.prompt_loader import load_prompt
from clauseai_backend.services.reference_search import search_bills, search_laws


@dataclass
class AnalysisResult:
    markdown: str
    payload: dict[str, Any]
    suggestions: list[dict[str, Any]]


def build_similar_bills_analysis(
    db: ReferenceDatabases,
    *,
    title: str,
    summary: str,
    keywords: list[str],
    draft_text: str,
    limit: int = 8,
) -> AnalysisResult:
    items = _load_similar_bill_context(db, title=title, summary=summary, keywords=keywords, limit=limit)
    model_payload = _run_model_json(
        "similar_bills_analysis_system_prompt.txt",
        {
            "title": title,
            "summary": summary,
            "keywords": keywords,
            "draft_text": _truncate(draft_text),
            "candidate_bills": items[: settings.max_reference_items_for_model],
        },
    )
    if model_payload:
        result = _analysis_result_from_model(
            model_payload,
            default_markdown=_fallback_similar_markdown(title, items),
            default_payload={"items": items},
        )
        if not result.suggestions:
            result.suggestions = _similar_guidance(items)
        return result

    status_counts = Counter((item.get("derived_status") or "unknown") for item in items)
    markdown = _fallback_similar_markdown(title, items)
    suggestions = _similar_guidance(items)
    return AnalysisResult(
        markdown=markdown,
        payload={
            "items": items,
            "summary": {
                "overall_assessment": f"Found {len(items)} candidate bills.",
                "working_patterns": [f"{status_counts.get('enacted', 0)} enacted patterns surfaced."],
                "risk_patterns": [f"{status_counts.get('failed_or_dead', 0)} failed/dead patterns surfaced."],
            },
        },
        suggestions=suggestions,
    )


def build_legal_analysis(
    db: ReferenceDatabases,
    *,
    title: str,
    summary: str,
    keywords: list[str],
    draft_text: str,
    limit: int = 6,
) -> AnalysisResult:
    items = _load_legal_context(db, title=title, summary=summary, keywords=keywords, limit=limit)
    model_payload = _run_model_json(
        "legal_conflict_analysis_system_prompt.txt",
        {
            "title": title,
            "summary": summary,
            "keywords": keywords,
            "draft_text": _truncate(draft_text),
            "candidate_laws": items[: settings.max_reference_items_for_model],
        },
    )
    if model_payload:
        result = _analysis_result_from_model(
            model_payload,
            default_markdown=_fallback_legal_markdown(title, items),
            default_payload={"items": items},
        )
        if not result.suggestions:
            result.suggestions = _legal_guidance(items)
        return result

    markdown = _fallback_legal_markdown(title, items)
    suggestions = _legal_guidance(items)
    return AnalysisResult(
        markdown=markdown,
        payload={"items": items, "risk_summary": {"overall_risk": "MEDIUM", "headline": "Review statute overlap carefully."}},
        suggestions=suggestions,
    )


def build_stakeholder_analysis(
    *,
    title: str,
    summary: str,
    keywords: list[str],
    draft_text: str,
) -> AnalysisResult:
    stakeholders = infer_stakeholders(" ".join([title, summary, *keywords, draft_text]))
    model_payload = _run_model_json(
        "stakeholder_analysis_system_prompt.txt",
        {
            "title": title,
            "summary": summary,
            "keywords": keywords,
            "draft_text": _truncate(draft_text),
            "candidate_stakeholders": stakeholders[: settings.max_reference_items_for_model],
        },
    )
    if model_payload:
        result = _analysis_result_from_model(
            model_payload,
            default_markdown=_fallback_stakeholder_markdown(stakeholders),
            default_payload={"items": stakeholders},
        )
        if not result.suggestions:
            result.suggestions = _stakeholder_guidance(stakeholders)
        return result

    markdown = _fallback_stakeholder_markdown(stakeholders)
    suggestions = _stakeholder_guidance(stakeholders)
    return AnalysisResult(markdown=markdown, payload={"items": stakeholders}, suggestions=suggestions)


def infer_stakeholders(text: str) -> list[dict[str, str]]:
    lowered = text.lower()
    candidates: list[dict[str, str]] = []
    if any(keyword in lowered for keyword in ["labor", "worker", "wage", "employment"]):
        candidates.extend(
            [
                {"name": "Labor unions", "stance": "supportive with conditions", "priority": "high", "reason": "Worker protection language can align with union priorities but enforcement details matter."},
                {"name": "Employer associations", "stance": "likely opposed", "priority": "high", "reason": "Broad compliance obligations or new wage standards increase cost exposure."},
            ]
        )
    if any(keyword in lowered for keyword in ["housing", "rent", "tenant", "landlord"]):
        candidates.extend(
            [
                {"name": "Tenant advocacy groups", "stance": "supportive", "priority": "high", "reason": "Tenant protections and affordability measures are generally aligned."},
                {"name": "Property owner associations", "stance": "likely opposed", "priority": "high", "reason": "Scope and compliance cost may be seen as too broad."},
            ]
        )
    if any(keyword in lowered for keyword in ["environment", "energy", "electric", "climate", "utility"]):
        candidates.extend(
            [
                {"name": "Environmental nonprofits", "stance": "supportive", "priority": "medium", "reason": "Decarbonization and infrastructure modernization align with mission."},
                {"name": "Utility operators", "stance": "mixed", "priority": "high", "reason": "Support depends on implementation timeline and cost recovery language."},
            ]
        )
    if any(keyword in lowered for keyword in ["health", "medical", "medicaid", "hospital"]):
        candidates.extend(
            [
                {"name": "Hospital systems", "stance": "mixed to opposed", "priority": "high", "reason": "Mandated operational changes can trigger cost and staffing concerns."},
                {"name": "Patient advocacy organizations", "stance": "supportive", "priority": "medium", "reason": "Consumer protection or access improvements are usually favorable."},
            ]
        )
    if not candidates:
        candidates = [
            {"name": "Relevant state agency", "stance": "mixed", "priority": "high", "reason": "Implementation feasibility depends on timelines and authority."},
            {"name": "Regulated entities", "stance": "likely opposed", "priority": "high", "reason": "Broad obligations without clear carve-outs tend to draw opposition."},
        ]
    return candidates


def _load_similar_bill_context(db: ReferenceDatabases, *, title: str, summary: str, keywords: list[str], limit: int) -> list[dict[str, Any]]:
    query_text = " ".join([title, summary, *keywords]).strip() or title
    try:
        return search_bills(db, query_text, limit=limit)
    except SQLAlchemyError:
        return []


def _load_legal_context(db: ReferenceDatabases, *, title: str, summary: str, keywords: list[str], limit: int) -> list[dict[str, Any]]:
    query_text = " ".join([title, summary, *keywords]).strip() or title
    try:
        return search_laws(db, query_text, limit=limit)
    except SQLAlchemyError:
        return []


def _run_model_json(prompt_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    system_prompt = load_prompt(prompt_name)
    user_prompt = json.dumps(payload, indent=2)
    if openai_compat_available():
        result = openai_compat_chat_json(system_prompt=system_prompt, user_prompt=user_prompt)
        if result is not None:
            return result
    if not codex_auth_available():
        return None
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(CodexClient().chat_json, system_prompt=system_prompt, user_prompt=user_prompt)
            return future.result(timeout=min(settings.codex_timeout_seconds, 20.0))
    except FutureTimeoutError:
        return None
    except (RuntimeError, ValueError, CodexAuthError):
        return None


def _analysis_result_from_model(
    payload: dict[str, Any],
    *,
    default_markdown: str,
    default_payload: dict[str, Any],
) -> AnalysisResult:
    suggestions = _normalize_suggestions(payload.get("suggestions"))
    markdown = _sanitize_report_markdown(str(payload.get("report") or default_markdown), suggestions)
    merged_payload = dict(default_payload)
    merged_payload.update({key: value for key, value in payload.items() if key not in {"report", "suggestions"}})
    return AnalysisResult(markdown=markdown, payload=merged_payload, suggestions=suggestions)


def _normalize_suggestions(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        items.append(
            {
                "title": str(entry.get("title") or "Untitled suggestion"),
                "rationale": str(entry.get("rationale") or ""),
                "before_text": "",
                "after_text": "",
                "source_refs": list(entry.get("source_refs") or []),
            }
        )
    return items


def _sanitize_report_markdown(markdown: str, suggestions: list[dict[str, Any]]) -> str:
    cleaned = markdown.strip()
    cleaned = re.sub(
        r"(?ims)^##\s*(recommended fixes|recommended changes|suggested fixes|specific fixes|drafting fixes)\b.*?(?=^##\s|\Z)",
        "",
        cleaned,
    ).strip()
    if not suggestions:
        return cleaned
    lowered = cleaned.lower()
    if "## general drafting guidance" in lowered or "## drafting guidance" in lowered:
        return cleaned

    guidance_lines = ["## General Drafting Guidance", ""]
    for item in suggestions:
        title = str(item.get("title") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        if not title and not rationale:
            continue
        if rationale:
            guidance_lines.append(f"- **{title}**: {rationale}" if title else f"- {rationale}")
        else:
            guidance_lines.append(f"- **{title}**")
    if guidance_lines[-1] == "":
        guidance_lines.pop()
    return f"{cleaned}\n\n" + "\n".join(guidance_lines)


def _similar_guidance(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "title": "Phase implementation and enforcement thoughtfully",
            "rationale": "Use the precedent set to decide whether phased compliance, delayed enforcement, or grid-readiness milestones would make the bill easier to implement without weakening the policy goal.",
            "before_text": "",
            "after_text": "",
            "source_refs": items[:2],
        },
        {
            "title": "Tighten scope and definitions",
            "rationale": "Use the precedent set to evaluate whether the regulated entities, thresholds, and exemptions should be defined more precisely before the editor proposes bill text.",
            "before_text": "",
            "after_text": "",
            "source_refs": items[2:4],
        },
    ]


def _legal_guidance(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "title": "Add procedural and conflict-avoidance safeguards",
            "rationale": "Use the legal analysis to decide whether the bill needs a savings clause, clearer administrative process, or a more explicit coordination mechanism before the editor writes any new language.",
            "before_text": "",
            "after_text": "",
            "source_refs": items[:2],
        }
    ]


def _stakeholder_guidance(stakeholders: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "title": "Reduce opposition with implementation and consultation planning",
            "rationale": "Use the stakeholder analysis to decide whether the bill needs consultation, sequencing, carve-outs, or compliance support before the editor proposes draft language.",
            "before_text": "",
            "after_text": "",
            "source_refs": stakeholders[:2],
        }
    ]


def _fallback_similar_markdown(title: str, items: list[dict[str, Any]]) -> str:
    status_counts = Counter((item.get("derived_status") or "unknown") for item in items)
    top_titles = [str(item.get("title") or "") for item in items[:3] if item.get("title")]
    return (
        "# Similar Bills Report\n\n"
        f"Found **{len(items)}** candidate precedent bills for **{title}**.\n\n"
        f"- Enacted / passed patterns: {status_counts.get('enacted', 0) + status_counts.get('passed_not_enacted', 0)}\n"
        f"- Failed / dead patterns: {status_counts.get('failed_or_dead', 0)}\n"
        f"- Notable precedent titles: {', '.join(top_titles) if top_titles else 'No strong matches yet'}\n\n"
        "## Observations\n\n"
        "- Bills with clearer phased implementation windows are more legible to reviewers.\n"
        "- Narrower definitions generally produce fewer downstream conflicts.\n"
        "- Comparative edits should remain traceable to specific precedent bills.\n"
        "\n## General Drafting Guidance\n\n"
        "- Use the precedent set to decide whether implementation should phase in over time.\n"
        "- Recheck whether the bill's definitions and thresholds are tighter than they are now.\n"
        "- Leave the actual legislative wording work to the Draft Editor so each change can be reviewed.\n"
    )


def _fallback_legal_markdown(title: str, items: list[dict[str, Any]]) -> str:
    issue_lines = "\n".join(
        f"- `{item.get('citation')}` · {item.get('heading') or item.get('hierarchy_path')}" for item in items
    ) or "- No direct statute candidates surfaced yet."
    return (
        "# Legal Conflict Report\n\n"
        f"Draft under review: **{title}**.\n\n"
        "## Candidate statutory conflicts\n\n"
        f"{issue_lines}\n\n"
        "## Risk framing\n\n"
        "- Check for threshold mismatches, agency authority conflicts, and codification overlap.\n"
        "- Confirm whether the bill authorizes conduct existing law restricts or vice versa.\n"
        "\n## General Drafting Guidance\n\n"
        "- Decide whether the bill needs clearer savings-clause, appeal, or variance mechanics.\n"
        "- Keep upstream analysis focused on risk framing; let the Draft Editor propose the actual statutory text.\n"
    )


def _fallback_stakeholder_markdown(stakeholders: list[dict[str, str]]) -> str:
    lines = "\n".join(f"- **{item['name']}** · {item['stance']} · {item['reason']}" for item in stakeholders)
    return (
        "# Stakeholder Analysis Report\n\n"
        "## Likely affected groups\n\n"
        f"{lines}\n\n"
        "## Drafting posture\n\n"
        "- Reduce unnecessary opposition by narrowing scope and sequencing implementation.\n"
        "- Preserve policy intent while making compliance pathways explicit.\n"
        "\n## General Drafting Guidance\n\n"
        "- Use the stakeholder feedback to decide what sequencing, consultation, or carve-out language the editor should explore.\n"
        "- Keep these as drafting directions only; the Draft Editor should generate the concrete bill edits.\n"
    )


def _truncate(text: str) -> str:
    compact = text.strip()
    return compact[: settings.max_draft_chars_for_model]
