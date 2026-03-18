from __future__ import annotations

from typing import Any

from clause_backend.repositories import app_state
from clause_backend.schemas import LawSearchFilters, SearchFilters
from clause_backend.services.agentic_law_search import agentic_law_search
from clause_backend.services.agentic_search import agentic_search
from clause_backend.services.gemini import generate_json, gemini_available


def _project_query_text(project: dict[str, Any]) -> str:
    parts = [project["title"], project["policy_goal"], project.get("summary", ""), project.get("bill_text", "")]
    return "\n".join(part for part in parts if part).strip()


def _stakeholder_fallback(project: dict[str, Any]) -> dict[str, Any]:
    goal = project["policy_goal"]
    return {
        "supporters": [
            f"Mission-aligned advocacy groups around: {goal}",
            "Issue specialists who benefit from faster compliance or clearer standards",
        ],
        "opponents": [
            "Trade groups exposed to new compliance burden",
            "Organizations concerned about enforcement scope or implementation cost",
        ],
        "agencies": ["Primary implementing agency", "Budget or oversight office"],
        "notes": ["Clarify carve-outs early", "Add reporting or phase-in language if implementation is heavy"],
    }


def analyze_stakeholders(project: dict[str, Any]) -> dict[str, Any]:
    if gemini_available():
        payload = generate_json(
            f"""
You are analyzing stakeholders for a legislative bill workspace.
Return JSON only with keys:
- supporters
- opponents
- agencies
- notes

Title: {project['title']}
Policy goal: {project['policy_goal']}
Summary: {project.get('summary', '')}
Draft text:
{project.get('bill_text', '')[:3000]}
            """.strip()
        )
        if isinstance(payload, dict):
            return payload
    return _stakeholder_fallback(project)


def refresh_project_insights(project: dict[str, Any]) -> dict[str, Any]:
    query = _project_query_text(project)
    bill_filters = SearchFilters(limit=4, jurisdiction=project.get("jurisdiction") or None)
    law_filters = LawSearchFilters(limit=4, jurisdiction=project.get("jurisdiction") or None)

    similar_bills = agentic_search(f"Find me similar bills to this draft:\n{query[:1800]}", bill_filters)
    conflicting_laws = agentic_law_search(
        f"Which laws contradict or constrain this bill draft?\n{query[:2500]}",
        law_filters,
    )
    stakeholders = analyze_stakeholders(project)
    drafting_focus = {
        "next_actions": [
            "Tighten the scope section before committee review.",
            "Use the similar bills list to borrow carve-outs or phase-in language.",
            "Resolve any law conflicts before circulating externally.",
        ],
        "current_stage": project.get("stage", "Research"),
    }

    payload = {
        "similar_bills": similar_bills.model_dump(),
        "conflicting_laws": conflicting_laws.model_dump(),
        "stakeholders": stakeholders,
        "drafting_focus": drafting_focus,
    }
    for key, value in payload.items():
        app_state.upsert_project_insight(project["project_id"], key, value)
    return payload


def _tool_result(tool_name: str, payload: Any) -> dict[str, Any]:
    return {"tool": tool_name, "payload": payload}


def agent_chat(project: dict[str, Any], user_message: str) -> dict[str, Any]:
    query = _project_query_text(project)
    tool_trace: list[dict[str, Any]] = []

    bill_hits = agentic_search(
        f"{user_message}\n\nProject context:\n{query[:1800]}",
        SearchFilters(limit=3, jurisdiction=project.get("jurisdiction") or None),
    )
    tool_trace.append(_tool_result("search_similar_bills", bill_hits.model_dump()))

    law_hits = agentic_law_search(
        f"{user_message}\n\nProject draft:\n{query[:2500]}",
        LawSearchFilters(limit=3, jurisdiction=project.get("jurisdiction") or None),
    )
    tool_trace.append(_tool_result("search_conflicting_laws", law_hits.model_dump()))

    stakeholders = analyze_stakeholders(project)
    tool_trace.append(_tool_result("analyze_stakeholders", stakeholders))

    if gemini_available():
        response = generate_json(
            f"""
You are Clause, an on-site legislative drafting agent working in a bill workspace.
Return JSON only with keys:
- reply
- suggested_stage
- suggested_status
- revision_excerpt

User request:
{user_message}

Project:
Title: {project['title']}
Goal: {project['policy_goal']}
Draft:
{project.get('bill_text', '')[:3500]}

Available evidence:
Similar bills: {bill_hits.model_dump_json(indent=2)}
Conflicting laws: {law_hits.model_dump_json(indent=2)}
Stakeholders: {stakeholders}
            """.strip()
        )
    else:
        response = None

    if not isinstance(response, dict):
        response = {
            "reply": (
                "I reviewed similar bills, likely legal conflicts, and stakeholder pressure. "
                "Start by tightening scope, then borrow successful carve-outs from the similar bills list."
            ),
            "suggested_stage": "Review",
            "suggested_status": "Needs revision",
            "revision_excerpt": project.get("bill_text", "")[:400],
        }

    assistant_message = app_state.add_project_message(project["project_id"], "assistant", str(response["reply"]), tool_trace)
    return {
        "message": assistant_message,
        "tool_trace": tool_trace,
        "suggested_stage": response.get("suggested_stage"),
        "suggested_status": response.get("suggested_status"),
        "revision_excerpt": response.get("revision_excerpt"),
    }
