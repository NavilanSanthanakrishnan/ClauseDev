from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from step1.config import get_settings
from step1.models import StakeholderReport, WorkflowSession, WorkflowSourceBill


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return slug or "bill"


class WorkflowStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = self.settings.upload_dir / "workflow_sessions"
        self.root.mkdir(parents=True, exist_ok=True)

    def create_session_dir(self) -> str:
        session_id = uuid4().hex
        self.session_dir(session_id).mkdir(parents=True, exist_ok=False)
        self.context_dir(session_id).mkdir(parents=True, exist_ok=True)
        self.source_bills_dir(session_id).mkdir(parents=True, exist_ok=True)
        return session_id

    def session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def metadata_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "session.json"

    def draft_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "current_draft.txt"

    def original_draft_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "original_draft.txt"

    def context_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "context"

    def source_bills_dir(self, session_id: str) -> Path:
        return self.context_dir(session_id) / "source_bills"

    def profile_path(self, session_id: str) -> Path:
        return self.context_dir(session_id) / "bill_profile.json"

    def results_path(self, session_id: str) -> Path:
        return self.context_dir(session_id) / "search_results.json"

    def source_index_path(self, session_id: str) -> Path:
        return self.context_dir(session_id) / "source_bills.json"

    def similar_bill_summaries_path(self, session_id: str) -> Path:
        return self.context_dir(session_id) / "similar_bill_summaries.md"

    def operator_brief_path(self, session_id: str) -> Path:
        return self.context_dir(session_id) / "operator_brief.md"

    def stakeholder_report_json_path(self, session_id: str) -> Path:
        return self.context_dir(session_id) / "stakeholder_report.json"

    def stakeholder_report_md_path(self, session_id: str) -> Path:
        return self.context_dir(session_id) / "stakeholder_report.md"

    def save(self, session: WorkflowSession) -> WorkflowSession:
        payload = session.model_dump()
        payload.pop("current_draft_text", None)
        self.metadata_path(session.session_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.draft_path(session.session_id).write_text(session.current_draft_text, encoding="utf-8")
        if not self.original_draft_path(session.session_id).exists():
            self.original_draft_path(session.session_id).write_text(session.current_draft_text, encoding="utf-8")
        return session

    def load(self, session_id: str) -> WorkflowSession:
        metadata_path = self.metadata_path(session_id)
        if not metadata_path.is_file():
            raise FileNotFoundError(f"Workflow session not found: {session_id}")
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        payload["current_draft_text"] = self.draft_path(session_id).read_text(encoding="utf-8")
        payload["stakeholder_report"] = self.load_stakeholder_report(session_id).model_dump()
        return WorkflowSession.model_validate(payload)

    def touch(self, session: WorkflowSession) -> WorkflowSession:
        session.updated_at = utc_now_iso()
        return self.save(session)

    def write_context_bundle(self, session: WorkflowSession) -> None:
        self.profile_path(session.session_id).write_text(
            json.dumps(session.profile.model_dump(), indent=2),
            encoding="utf-8",
        )
        self.results_path(session.session_id).write_text(
            json.dumps([result.model_dump() for result in session.results], indent=2),
            encoding="utf-8",
        )
        self.source_index_path(session.session_id).write_text(
            json.dumps([source.model_dump() for source in session.source_bills], indent=2),
            encoding="utf-8",
        )
        self.similar_bill_summaries_path(session.session_id).write_text(
            self._similar_bill_summaries(session.source_bills),
            encoding="utf-8",
        )
        self.operator_brief_path(session.session_id).write_text(
            self._operator_brief(session),
            encoding="utf-8",
        )
        self.stakeholder_report_json_path(session.session_id).write_text(
            json.dumps(session.stakeholder_report.model_dump(), indent=2),
            encoding="utf-8",
        )
        self.stakeholder_report_md_path(session.session_id).write_text(
            self._stakeholder_report_stub(),
            encoding="utf-8",
        )
        for path in self.source_bills_dir(session.session_id).glob("*.md"):
            path.unlink(missing_ok=True)
        for index, source_bill in enumerate(session.source_bills, start=1):
            slug = _safe_slug(f"{index:02d}-{source_bill.identifier}")
            path = self.source_bills_dir(session.session_id) / f"{slug}.md"
            path.write_text(self._source_bill_markdown(source_bill), encoding="utf-8")

    def load_stakeholder_report(self, session_id: str) -> StakeholderReport:
        path = self.stakeholder_report_json_path(session_id)
        if not path.is_file():
            return StakeholderReport()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return StakeholderReport(status="in_progress")
        try:
            return StakeholderReport.model_validate(payload)
        except Exception:
            return StakeholderReport(status="in_progress")

    def _operator_brief(self, session: WorkflowSession) -> str:
        passed = [bill for bill in session.source_bills if bill.derived_status in {"enacted", "passed_not_enacted"}]
        failed = [bill for bill in session.source_bills if bill.derived_status not in {"enacted", "passed_not_enacted"}]
        passed_lines = [
            f"- {bill.identifier}: {bill.title}"
            for bill in passed
        ] or ["- None"]
        failed_lines = [
            f"- {bill.identifier}: {bill.title} ({bill.derived_status})"
            for bill in failed
        ] or ["- None"]
        warnings = "\n".join(f"- {warning}" for warning in session.warnings) or "- None"
        return "\n".join(
            [
                "# ClauseAI Operator Brief",
                "",
                "## Working file",
                "- In Step 3 and Step 4, edit only `current_draft.txt`.",
                "- In Step 5, you may also update `context/stakeholder_report.json` and `context/stakeholder_report.md`.",
                "- Read `current_draft.txt` in full before the first edit.",
                "- After every accepted patch, reread the full file before planning the next change.",
                "- Do not create or edit any other files.",
                "- `context/similar_bill_summaries.md` contains the short Step 4 bill summaries prepared from the structured corpus.",
                "- Prefer omission over over-editing.",
                "- If a change is debatable, stylistic, or only marginally better, do not propose it.",
                "",
                "## Step 3",
                "- Cleanup only what is necessary: numbering, headings, punctuation, formatting, obvious cross-references, and malformed text.",
                "- Do not modernize tone, rewrite policy substance, or smooth language that is already legally workable.",
                "- Prefer no change over speculative change.",
                "",
                "## Step 4",
                "- Strengthen only where passed source bills show clearly better language.",
                "- Passed bills are preferred source language. Failed bills are warning signals, not templates.",
                "- Do not go overboard. Make the smallest effective edit.",
                "- Do not import source-bill language just because it is cleaner or more detailed.",
                "- Only propose a Step 4 edit when it clearly fixes ambiguity, implementation mechanics, or legal operability in the user bill.",
                "",
                "## Step 5",
                "- After Step 4, perform stakeholder investigation with web search before drafting Step 5 bill edits.",
                "- Save the structured report to `context/stakeholder_report.json` and a short readable summary to `context/stakeholder_report.md` before proposing any Step 5 draft change.",
                "- Include estimated affected entities, SME impacts, distributional impacts, political viability, implementation feasibility, key stakeholder actors, evidence sources, and 6 to 8 targeted improvements only if justified.",
                "- Use Step 5 bill edits only to reduce opposition, improve fairness, and improve implementation feasibility while preserving policy intent.",
                "- Each Step 5 draft edit should map back to one targeted improvement in the stakeholder report.",
                "- Do not add concessions, carveouts, or implementation layers unless the stakeholder analysis shows a concrete and meaningful reason.",
                "- If the stakeholder analysis supports zero additional edits, stop after writing the report.",
                "",
                "## Source bills to prefer",
                *passed_lines,
                "",
                "## Source bills to treat as warnings",
                *failed_lines,
                "",
                "## Session warnings",
                warnings,
            ]
        ).strip() + "\n"

    def _similar_bill_summaries(self, source_bills: list[WorkflowSourceBill]) -> str:
        if not source_bills:
            return "# Similar Bill Summaries\n\nNo similar bills have been staged yet.\n"
        lines = ["# Similar Bill Summaries", ""]
        for bill in source_bills:
            session = bill.session_identifier or "unknown session"
            summary = bill.summary or bill.excerpt or "No summary available."
            lines.append(
                f"- Bill {bill.identifier} {bill.jurisdiction_name} {session} Summary: {summary}"
            )
        return "\n".join(lines).strip() + "\n"

    def _source_bill_markdown(self, source_bill: WorkflowSourceBill) -> str:
        section_blocks = []
        for section in source_bill.sections:
            heading = section.heading or f"Section {section.label or '?'}"
            section_blocks.append(f"### {heading}\n\n{section.text.strip()}\n")
        joined_sections = "\n".join(section_blocks).strip()
        return "\n".join(
            [
                f"# {source_bill.identifier} - {source_bill.title}",
                "",
                f"- Jurisdiction: {source_bill.jurisdiction_name}",
                f"- Status: {source_bill.derived_status or 'unknown'}",
                "",
                "## Summary",
                source_bill.summary or "No summary available.",
                "",
                "## Excerpt",
                source_bill.excerpt or "No excerpt available.",
                "",
                "## Full text excerpt",
                source_bill.full_text or "No full text available.",
                "",
                "## Key sections",
                joined_sections or "No structured sections available.",
                "",
            ]
        )

    def _stakeholder_report_stub(self) -> str:
        return "\n".join(
            [
                "# Stakeholder Report",
                "",
                "Status: not started",
                "",
                "## Summary",
                "",
                "Pending Step 5 stakeholder analysis.",
                "",
                "## Required contents",
                "",
                "- Estimated affected entities",
                "- SME impact test",
                "- Distributional impacts",
                "- Political viability",
                "- Implementation feasibility",
                "- Beneficiaries versus cost bearers",
                "- Key stakeholder actors",
                "- Evidence sources",
                "- Targeted improvements tied to potential bill edits",
                "",
            ]
        )
