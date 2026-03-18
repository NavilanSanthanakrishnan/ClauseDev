from collections.abc import Sequence
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from clauseai_backend.db.session import ReferenceDatabases
from clauseai_backend.models.chat import ChatThread
from clauseai_backend.models.projects import AnalysisArtifact, BillDraft, ProjectMetadata, Suggestion
from clauseai_backend.services.codex_auth import CodexAuthError, codex_auth_available
from clauseai_backend.services.openai_compat_client import openai_compat_available, openai_compat_chat_json
from clauseai_backend.services.codex_client import CodexClient
from clauseai_backend.services.prompt_loader import load_prompt
from clauseai_backend.services.reference_search import search_bills, search_laws


def build_assistant_reply(
    *,
    user_db: Session,
    reference_db: ReferenceDatabases,
    thread: ChatThread,
    user_message: str,
) -> tuple[str, list[dict[str, object]]]:
    normalized = " ".join(user_message.strip().split())
    bill_hits = search_bills(reference_db, normalized, limit=3)
    law_hits = search_laws(reference_db, normalized, limit=3)
    context_lines: list[str] = []
    citations: list[dict[str, object]] = []

    if thread.project_id:
        draft = user_db.scalar(select(BillDraft).where(BillDraft.project_id == thread.project_id))
        metadata = user_db.get(ProjectMetadata, thread.project_id)
        suggestions = _latest_suggestions(user_db, thread.project_id)
        artifacts = _latest_artifacts(user_db, thread.project_id)

        if metadata:
            context_lines.append(
                f"Project metadata: {metadata.title} | {metadata.summary} | keywords: {', '.join(metadata.keywords[:5])}"
            )
        if draft and draft.current_text.strip():
            context_lines.append(f"Current draft snapshot: {_trim(draft.current_text, 320)}")
        if suggestions:
            context_lines.append(
                "Open suggestions: "
                + "; ".join(f"{item.stage_name}: {item.title}" for item in suggestions[:4])
            )
        if artifacts:
            context_lines.append(
                "Available reports: "
                + "; ".join(f"{item.stage_name} report ready" for item in artifacts[:3])
            )

    if bill_hits:
        context_lines.append(
            "Relevant bills: " + "; ".join(f"{item.get('identifier')}: {item.get('title')}" for item in bill_hits)
        )
        citations.extend(
            {
                "kind": "bill",
                "identifier": item.get("identifier"),
                "title": item.get("title"),
                "jurisdiction_name": item.get("jurisdiction_name"),
            }
            for item in bill_hits
        )

    if law_hits:
        context_lines.append(
            "Relevant laws: " + "; ".join(f"{item.get('citation')}: {item.get('heading')}" for item in law_hits)
        )
        citations.extend(
            {
                "kind": "law",
                "citation": item.get("citation"),
                "heading": item.get("heading"),
                "jurisdiction": item.get("jurisdiction"),
            }
            for item in law_hits
        )

    if not context_lines:
        context_lines.append(
            "No direct corpus match was available yet. Continue by refining the ask, generating the stage reports, or attaching the question to a specific bill project."
        )

    _sys = load_prompt("research_chat_system_prompt.txt")
    _usr = json.dumps(
        {"question": normalized, "project_context": context_lines,
         "bill_hits": bill_hits, "law_hits": law_hits},
        indent=2,
    )
    _pl: dict | None = None
    if openai_compat_available():
        _pl = openai_compat_chat_json(system_prompt=_sys, user_prompt=_usr)
    if _pl is None and codex_auth_available():
        try:
            _pl = CodexClient().chat_json(system_prompt=_sys, user_prompt=_usr)
        except (RuntimeError, ValueError, CodexAuthError):
            pass
    if _pl is not None:
        answer = str(_pl.get("answer") or "").strip()
        if answer:
            extra_citations = _pl.get("citations")
            if isinstance(extra_citations, list):
                citations.extend(item for item in extra_citations if isinstance(item, dict))
            return answer, citations

    response = (
        f"Research response for: {normalized}\n\n"
        + "\n".join(f"- {line}" for line in context_lines)
        + "\n\nNext move: narrow the request to similar bills, legal conflicts, stakeholder opposition, or a concrete edit in the drafting workspace."
    )
    return response, citations


def _latest_suggestions(db: Session, project_id: str) -> Sequence[Suggestion]:
    return (
        db.execute(select(Suggestion).where(Suggestion.project_id == project_id).order_by(Suggestion.created_at.desc()))
        .scalars()
        .all()
    )


def _latest_artifacts(db: Session, project_id: str) -> Sequence[AnalysisArtifact]:
    return (
        db.execute(
            select(AnalysisArtifact).where(AnalysisArtifact.project_id == project_id).order_by(AnalysisArtifact.updated_at.desc())
        )
        .scalars()
        .all()
    )


def _trim(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"
