from __future__ import annotations

from dataclasses import dataclass
import re

from step4.models import ConflictFinding, UploadedBillProfile
from step4.services.database import Database


CODE_NAME_TO_ABBREV = {
    "government code": "GOV",
    "health and safety code": "HSC",
    "labor code": "LAB",
    "penal code": "PEN",
    "public resources code": "PRC",
    "welfare and institutions code": "WIC",
}

ADDITION_TARGET_RE = re.compile(
    r"add\s+article\s+(?P<article>[0-9A-Za-z.]+)\s+"
    r"\(commencing with section\s+(?P<section>\d+(?:\.\d+)*)\)\s+"
    r"to\s+chapter\s+(?P<chapter>[0-9.]+)\s+"
    r"of\s+division\s+(?P<division>[0-9.]+)\s+"
    r"of\s+the\s+(?P<code>[A-Za-z ]+?)\s+code",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AdditionTarget:
    code_abbrev: str
    division: str
    chapter_num: str
    article_num: str
    commencing_section: str


def _normalize_hierarchy_number(value: str) -> str:
    value = value.strip()
    return value if value.endswith(".") else f"{value}."


def _section_key(section_number: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", section_number))


def _excerpt_near(text: str, needle: str, radius: int = 260) -> str:
    lowered = text.lower()
    idx = lowered.find(needle.lower())
    if idx < 0:
        clean = re.sub(r"\s+", " ", text).strip()
        return clean[: radius * 2]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(needle) + radius)
    return re.sub(r"\s+", " ", text[start:end]).strip()


class CaliforniaDraftingChecker:
    def __init__(self, db: Database) -> None:
        self.db = db

    def find_issues(self, *, profile: UploadedBillProfile, bill_text: str) -> list[ConflictFinding]:
        if profile.origin_state_code.upper() != "CA":
            return []

        findings: list[ConflictFinding] = []
        findings.extend(self._codification_findings(profile=profile, bill_text=bill_text))
        findings.extend(self._building_standards_findings(profile=profile, bill_text=bill_text))
        return findings

    def _codification_findings(self, *, profile: UploadedBillProfile, bill_text: str) -> list[ConflictFinding]:
        findings: list[ConflictFinding] = []
        for target in self._addition_targets(bill_text):
            proposed_citation = f"{target.code_abbrev} {target.commencing_section}."
            existing = self._fetch_section(proposed_citation)
            if existing:
                findings.append(
                    ConflictFinding(
                        candidate_id=f"california:{existing['citation']}",
                        source_system="california",
                        source_kind="section",
                        citation=existing["citation"],
                        hierarchy_path=existing.get("hierarchy_path") or "",
                        source_url=existing.get("display_url"),
                        finding_bucket="codification_conflict",
                        conflict_type="same_section_number_reused_for different statutory text",
                        severity="high",
                        confidence=1.0,
                        bill_excerpt=_excerpt_near(
                            bill_text,
                            f"commencing with Section {target.commencing_section}",
                        ),
                        statute_excerpt=(existing.get("body_text") or "")[:500],
                        explanation=(
                            f"The bill proposes adding new text commencing with Section {target.commencing_section} in the "
                            f"{target.code_abbrev}, but {existing['citation']} is already occupied in current law."
                        ),
                        why_conflict=(
                            "California codification cannot reuse an already assigned live section number for different text "
                            "without renumbering or rewriting the bill as an amendment."
                        ),
                    )
                )

            chapter_anchor = self._fetch_chapter_anchor(
                code_abbrev=target.code_abbrev,
                division=target.division,
                chapter_num=target.chapter_num,
            )
            if not chapter_anchor:
                continue
            proposed_key = _section_key(target.commencing_section)
            chapter_floor = _section_key(chapter_anchor["section_number"])
            if proposed_key and chapter_floor and proposed_key < chapter_floor:
                findings.append(
                    ConflictFinding(
                        candidate_id=f"california:{chapter_anchor['citation']}",
                        source_system="california",
                        source_kind="section",
                        citation=chapter_anchor["citation"],
                        hierarchy_path=chapter_anchor.get("hierarchy_path") or "",
                        source_url=chapter_anchor.get("display_url"),
                        finding_bucket="codification_conflict",
                        conflict_type="chapter range mismatch",
                        severity="high",
                        confidence=0.99,
                        bill_excerpt=_excerpt_near(
                            bill_text,
                            (
                                f"Article {target.article_num} (commencing with Section {target.commencing_section}) "
                                f"to Chapter {target.chapter_num.rstrip('.')} of Division {target.division.rstrip('.')}"
                            ),
                        ),
                        statute_excerpt=(chapter_anchor.get("hierarchy_path") or "")[:500],
                        explanation=(
                            f"The bill places Article {target.article_num} in Chapter {target.chapter_num} of Division "
                            f"{target.division} commencing with Section {target.commencing_section}, but the existing "
                            f"chapter starts at {chapter_anchor['citation']}."
                        ),
                        why_conflict=(
                            "The proposed commencing section falls below the current numbering range for the cited chapter, "
                            "which indicates an internal codification mismatch in the bill text."
                        ),
                    )
                )

        return findings

    def _building_standards_findings(self, *, profile: UploadedBillProfile, bill_text: str) -> list[ConflictFinding]:
        text = bill_text.lower()
        immediate_effect = any(
            phrase in text
            for phrase in (
                "take effect immediately upon passage",
                "effective immediately upon passage",
                "take effect immediately",
            )
        )
        implementing_regulations = any(
            phrase in text
            for phrase in (
                "adopt implementing regulations",
                "adopt regulations within",
                "implementing regulations within",
            )
        )
        cec_enforcement = (
            "california energy commission shall enforce" in text
            or "commission shall enforce the provisions" in text
        )
        penalty_scheme = "civil penalty" in text and (
            "per day" in text or re.search(r"\$\s*\d[\d,]*", bill_text) is not None
        )
        if not any(
            (
                any(
                    phrase in text
                    for phrase in (
                        "building standards",
                        "california building standards code",
                        "electric vehicle charger",
                        "electric vehicle charging",
                    )
                ),
                immediate_effect and implementing_regulations,
                cec_enforcement,
                penalty_scheme,
            )
        ):
            return []

        findings: list[ConflictFinding] = []
        bill_excerpt = " ".join(clause.text for clause in profile.key_clauses[:3]).strip() or profile.summary

        if immediate_effect and implementing_regulations:
            for citation, explanation, why_conflict, confidence in (
                (
                    "GOV 11343.4.",
                    "The bill says the new article takes effect immediately and directs implementing regulations within 90 days, "
                    "but Government Code Section 11343.4 sets default regulation effective dates after filing unless another statute "
                    "clearly displaces that schedule.",
                    "Immediate statutory effectiveness does not automatically make implementing regulations operative on the same timetable.",
                    0.91,
                ),
                (
                    "HSC 18930.",
                    "The bill directs rapid implementing regulations for EV-charging building standards, but Health and Safety Code "
                    "Section 18930 routes state building standards through the California Building Standards Commission before codification.",
                    "Building standards normally must move through the California Building Standards Commission process rather than becoming operative solely by an immediate-effect clause.",
                    0.9,
                ),
                (
                    "HSC 18938.5.",
                    "The bill's immediate-effect structure does not line up cleanly with Health and Safety Code Section 18938.5, which ties building-standard applicability to standards effective when permit applications are submitted.",
                    "Even if the article becomes effective immediately, permit-level applicability for building standards follows existing building standards timing rules.",
                    0.82,
                ),
            ):
                statute = self._fetch_section(citation)
                if not statute:
                    continue
                findings.append(
                    ConflictFinding(
                        candidate_id=f"california:{statute['citation']}",
                        source_system="california",
                        source_kind="section",
                        citation=statute["citation"],
                        hierarchy_path=statute.get("hierarchy_path") or "",
                        source_url=statute.get("display_url"),
                        finding_bucket="implementation_constraint",
                        conflict_type="procedure conflict",
                        severity="medium",
                        confidence=confidence,
                        bill_excerpt=_excerpt_near(
                            bill_text,
                            "take effect immediately",
                        ),
                        statute_excerpt=(statute.get("body_text") or "")[:500],
                        explanation=explanation,
                        why_conflict=why_conflict,
                    )
                )

        if cec_enforcement:
            statute = self._fetch_section("PRC 25402.1.")
            if statute:
                findings.append(
                    ConflictFinding(
                        candidate_id=f"california:{statute['citation']}",
                        source_system="california",
                        source_kind="section",
                        citation=statute["citation"],
                        hierarchy_path=statute.get("hierarchy_path") or "",
                        source_url=statute.get("display_url"),
                        finding_bucket="implementation_constraint",
                        conflict_type="enforcement conflict",
                        severity="medium",
                        confidence=0.84,
                        bill_excerpt=_excerpt_near(bill_text, "shall enforce the provisions of this article"),
                        statute_excerpt=(statute.get("body_text") or "")[:500],
                        explanation=(
                            "The bill assigns direct enforcement to the California Energy Commission, but existing Public Resources "
                            "Code Section 25402.1 places ordinary building-energy enforcement on local building departments first, "
                            "with the commission stepping in on narrower terms."
                        ),
                        why_conflict=(
                            "The bill appears to reallocate first-line enforcement authority without expressly reconciling the existing enforcement structure."
                        ),
                    )
                )

        if penalty_scheme:
            statute = self._fetch_section("PRC 25402.11.")
            if statute:
                findings.append(
                    ConflictFinding(
                        candidate_id=f"california:{statute['citation']}",
                        source_system="california",
                        source_kind="section",
                        citation=statute["citation"],
                        hierarchy_path=statute.get("hierarchy_path") or "",
                        source_url=statute.get("display_url"),
                        finding_bucket="implementation_constraint",
                        conflict_type="penalty overlap",
                        severity="medium",
                        confidence=0.78,
                        bill_excerpt=_excerpt_near(bill_text, "civil penalty"),
                        statute_excerpt=(statute.get("body_text") or "")[:500],
                        explanation=(
                            "The bill creates its own charger-by-charger and per-day civil penalties, while existing Public Resources Code "
                            "Section 25402.11 already contains a commission administrative enforcement process and penalty structure for "
                            "energy-efficiency regulations."
                        ),
                        why_conflict=(
                            "The penalty scheme may need explicit reconciliation with the commission's existing administrative enforcement framework."
                        ),
                    )
                )

        return findings

    def _addition_targets(self, bill_text: str) -> list[AdditionTarget]:
        targets: list[AdditionTarget] = []
        for match in ADDITION_TARGET_RE.finditer(bill_text):
            code_name = re.sub(r"\s+", " ", match.group("code").strip().lower())
            if not code_name.endswith("code"):
                code_name = f"{code_name} code"
            code_abbrev = CODE_NAME_TO_ABBREV.get(code_name)
            if not code_abbrev:
                continue
            targets.append(
                AdditionTarget(
                    code_abbrev=code_abbrev,
                    division=_normalize_hierarchy_number(match.group("division")),
                    chapter_num=_normalize_hierarchy_number(match.group("chapter")),
                    article_num=match.group("article").rstrip("."),
                    commencing_section=match.group("section"),
                )
            )
        return targets

    def _fetch_section(self, citation: str) -> dict | None:
        return self.db.california.fetch_one(
            """
            SELECT citation, section_number, hierarchy_path, display_url, body_text
            FROM section_search
            WHERE citation = %(citation)s
            """,
            {"citation": citation},
        )

    def _fetch_chapter_anchor(self, *, code_abbrev: str, division: str, chapter_num: str) -> dict | None:
        return self.db.california.fetch_one(
            """
            SELECT citation, section_number, hierarchy_path, display_url
            FROM section_search
            WHERE code_abbrev = %(code_abbrev)s
              AND division = %(division)s
              AND chapter_num = %(chapter_num)s
            ORDER BY section_number
            LIMIT 1
            """,
            {
                "code_abbrev": code_abbrev,
                "division": division,
                "chapter_num": chapter_num,
            },
        )
