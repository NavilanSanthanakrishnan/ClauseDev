from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from step1.config import get_settings
from step1.models import CandidateBill, WorkflowSourceBill, WorkflowSourceSection
from step1.services.database import Database

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency for structured bill fallbacks
    yaml = None


def _load_bill_parser() -> Any | None:
    settings = get_settings()
    scripts_dir = Path(settings.repo_root) / "scripts"
    if not scripts_dir.is_dir():
        return None
    scripts_dir_str = str(scripts_dir)
    if scripts_dir_str not in sys.path:
        sys.path.append(scripts_dir_str)
    try:
        from bill_text_parser import parse_bill_structure

        return parse_bill_structure
    except Exception:
        return None


def _shorten(text: str, limit: int) -> str:
    normalized = (text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


class WorkflowContextService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.settings = get_settings()
        self.parse_bill_structure = _load_bill_parser()
        self._clauseai_columns: set[str] | None = None

    def prepare_source_bills(self, candidates: list[CandidateBill]) -> list[WorkflowSourceBill]:
        selected = self._select_candidates(candidates)
        clauseai_rows = self._fetch_clauseai_rows([candidate.bill_id for candidate in selected])
        source_bills: list[WorkflowSourceBill] = []
        for candidate in selected:
            row = clauseai_rows.get(candidate.bill_id, {})
            structured_payload = self._structured_payload(row)
            sections = self._sections_from_payload(structured_payload)
            full_text = (
                row.get("full_bill_text")
                or (structured_payload.get("bill") or {}).get("clean_text", "")
                or candidate.raw_text
                or candidate.excerpt
            )
            source_bills.append(
                WorkflowSourceBill(
                    bill_id=candidate.bill_id,
                    identifier=candidate.identifier,
                    title=row.get("title") or candidate.title,
                    jurisdiction_name=row.get("jurisdiction_name") or candidate.jurisdiction_name,
                    session_identifier=candidate.session_identifier,
                    derived_status=candidate.derived_status,
                    primary_bill_url=candidate.primary_bill_url or row.get("full_text_url"),
                    match_reason=candidate.match_reason,
                    summary=self._summary(candidate, row, sections),
                    excerpt=_shorten(candidate.excerpt or candidate.raw_text or full_text, 700),
                    full_text=_shorten(full_text, self.settings.max_source_bill_chars_for_llm),
                    sections=sections[:8],
                )
            )
        return source_bills

    def _select_candidates(self, candidates: list[CandidateBill]) -> list[CandidateBill]:
        passed = [candidate for candidate in candidates if candidate.derived_status in {"enacted", "passed_not_enacted"}]
        failed = [candidate for candidate in candidates if candidate.derived_status in {"failed_or_dead", "vetoed"}]
        other = [
            candidate
            for candidate in candidates
            if candidate.derived_status not in {"enacted", "passed_not_enacted", "failed_or_dead", "vetoed"}
        ]
        ordered = [*passed[:4], *failed[:2]]
        seen = {candidate.bill_id for candidate in ordered}
        for bucket in (passed[4:], failed[2:], other):
            for candidate in bucket:
                if candidate.bill_id in seen:
                    continue
                ordered.append(candidate)
                seen.add(candidate.bill_id)
                if len(ordered) >= self.settings.max_source_bills_for_workflow:
                    return ordered
        return ordered[: self.settings.max_source_bills_for_workflow]

    def _fetch_clauseai_rows(self, bill_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not bill_ids:
            return {}
        columns = self._available_clauseai_columns()
        if not columns:
            return {}
        selected_columns = [
            "openstates_bill_id",
            "title",
            "description_or_summary",
            "full_bill_text",
            "full_text_url",
            "jurisdiction_name",
            "final_status",
        ]
        if "clean_json_full_bill_text" in columns:
            selected_columns.append("clean_json_full_bill_text")
        if "clean_yaml_full_bill_text" in columns:
            selected_columns.append("clean_yaml_full_bill_text")
        rows = self.db.fetch_all(
            f"""
            SELECT {", ".join(selected_columns)}
            FROM public.clauseai_bill_table
            WHERE openstates_bill_id = ANY(%(bill_ids)s::text[])
            """,
            {"bill_ids": bill_ids},
        )
        return {row["openstates_bill_id"]: row for row in rows}

    def _available_clauseai_columns(self) -> set[str]:
        if self._clauseai_columns is not None:
            return self._clauseai_columns
        exists_row = self.db.fetch_one(
            """
            SELECT to_regclass('public.clauseai_bill_table') AS relation_name
            """
        )
        if not exists_row or not exists_row.get("relation_name"):
            self._clauseai_columns = set()
            return self._clauseai_columns
        rows = self.db.fetch_all(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'clauseai_bill_table'
            """
        )
        self._clauseai_columns = {row["column_name"] for row in rows}
        return self._clauseai_columns

    def _structured_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        if not row:
            return {}
        if row.get("clean_json_full_bill_text"):
            payload = row["clean_json_full_bill_text"]
            if isinstance(payload, dict):
                return payload
            try:
                return json.loads(payload)
            except Exception:
                pass
        if row.get("clean_yaml_full_bill_text") and yaml is not None:
            try:
                parsed = yaml.safe_load(row["clean_yaml_full_bill_text"])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        if self.parse_bill_structure and row.get("full_bill_text"):
            try:
                parsed = self.parse_bill_structure(row["full_bill_text"])
                return {"bill": {"sections": parsed.get("sections", []), "clean_text": parsed.get("clean_text", "")}}
            except Exception:
                return {}
        return {}

    def _sections_from_payload(self, payload: dict[str, Any]) -> list[WorkflowSourceSection]:
        bill = payload.get("bill")
        if not isinstance(bill, dict):
            return []
        raw_sections = bill.get("sections")
        if not isinstance(raw_sections, list):
            return []
        sections: list[WorkflowSourceSection] = []
        for section in raw_sections:
            if not isinstance(section, dict):
                continue
            sections.append(
                WorkflowSourceSection(
                    label=str(section.get("label") or ""),
                    heading=str(section.get("heading") or ""),
                    text=_shorten(str(section.get("text") or ""), 700),
                )
            )
        return sections

    def _summary(
        self,
        candidate: CandidateBill,
        row: dict[str, Any],
        sections: list[WorkflowSourceSection],
    ) -> str:
        summary_parts: list[str] = []
        if candidate.derived_status:
            summary_parts.append(f"Status: {candidate.derived_status}.")
        if candidate.match_reason:
            summary_parts.append(candidate.match_reason.strip())
        row_summary = (row.get("description_or_summary") or "").strip()
        if row_summary:
            summary_parts.append(_shorten(row_summary, 450))
        elif sections:
            preview = "; ".join(
                section.heading or f"Section {section.label}"
                for section in sections[:3]
                if section.heading or section.label
            )
            if preview:
                summary_parts.append(f"Key sections: {preview}.")
        return " ".join(part for part in summary_parts if part).strip()
