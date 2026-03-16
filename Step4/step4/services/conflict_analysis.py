from __future__ import annotations

import json
import re
import time

from step4.models import (
    CandidateVerificationResponse,
    ConflictFinding,
    ConflictJudgeResponse,
    ConflictSearchResult,
    UploadedBillProfile,
)
from step4.services.bill_extraction import detect_file_type, extract_text_from_file
from step4.services.bill_profile import BillProfileExtractor
from step4.services.codex_client import CodexClient
from step4.services.database import Database
from step4.services.legal_retrieval import LegalRetriever


CONFLICT_JUDGE_PROMPT = """You are a statutory conflict analyst.

Return ONLY valid JSON.

You will receive:
- a structured profile of an uploaded bill
- a set of California statute candidates
- a set of federal U.S. Code candidates

Your task is to identify only actual or likely legal conflicts.

A conflict means at least one of:
- the bill authorizes conduct that an existing statute forbids
- the bill forbids conduct that an existing statute requires or protects
- the bill changes mandatory thresholds, timelines, pay rules, notice rules, or eligibility rules in a way that is incompatible with existing law
- federal law would preempt or block the bill's operative rule
- compliance with both the bill and the statute would be impossible or materially inconsistent

Do NOT flag mere topic overlap.
Do NOT flag statutes just because they are in the same subject area.

Expected JSON:
{
  "conflicts": [
    {
      "candidate_id": "",
      "conflict_type": "state contradiction|federal preemption|permission-versus-prohibition|procedure conflict|threshold conflict|compliance impossibility",
      "severity": "high|medium|low",
      "confidence": 0.0,
      "bill_excerpt": "",
      "statute_excerpt": "",
      "explanation": "",
      "why_conflict": ""
    }
  ],
  "notes": ""
}

Rules:
- Only use `candidate_id` values from the provided candidates.
- Quote or closely reproduce exact bill/statute excerpts from the provided material only.
- Prefer direct contradictions over broad policy adjacency.
- For federal candidates, treat federal floor statutes as conflicting when the bill would authorize conduct below the federal minimum protection or would deem unlawful under federal law to be lawful under state law.
- For federal wage-and-hour conflicts, prefer the most specific statute that actually matches the bill's problem. If the bill tries to wipe out stricter state or local protections, prefer a federal savings-clause statute like 29 U.S.C. § 218 over a generic minimum-wage floor statute.
- Do not include a candidate if your own explanation says there is no direct conflict.
- Return an empty `conflicts` array if nothing actually conflicts.
"""

PAIRWISE_VERIFICATION_PROMPT = """You are verifying one candidate statute against one uploaded bill.

Return ONLY valid JSON:
{
  "is_conflict": true,
  "conflict_type": "",
  "severity": "high|medium|low",
  "confidence": 0.0,
  "bill_excerpt": "",
  "statute_excerpt": "",
  "explanation": "",
  "why_conflict": ""
}

Rules:
- `is_conflict` must be false if the candidate is only topically related.
- Mark true only if the bill and statute are materially incompatible or the federal statute would preempt/block the bill's operative rule.
- Do not say there is "no direct conflict" and still set `is_conflict` to true.
- Use only the provided excerpts.
"""


class ConflictAnalysisService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.profile_extractor = BillProfileExtractor()
        self.retriever = LegalRetriever(db)
        self.codex = CodexClient()

    def analyze(self, *, filename: str, payload: bytes) -> ConflictSearchResult:
        timings: dict[str, float] = {}
        warnings: list[str] = []

        started = time.perf_counter()
        file_type = detect_file_type(filename)
        bill_text = extract_text_from_file(file_type, payload)
        timings["extract"] = time.perf_counter() - started

        profile_started = time.perf_counter()
        profile = self.profile_extractor.extract(bill_text)
        timings["profile"] = time.perf_counter() - profile_started

        retrieval_started = time.perf_counter()
        candidates = self.retriever.retrieve(profile)
        timings["retrieve"] = time.perf_counter() - retrieval_started

        llm_started = time.perf_counter()
        conflicts = self._judge_conflicts(profile=profile, bill_text=bill_text, candidates=candidates, warnings=warnings)
        timings["judge"] = time.perf_counter() - llm_started
        timings["total"] = time.perf_counter() - started

        return ConflictSearchResult(
            filename=filename,
            file_type=file_type,
            extracted_text_preview=bill_text[:1600],
            extracted_text_length=len(bill_text),
            profile=profile,
            conflicts=conflicts,
            candidate_counts={key: len(value) for key, value in candidates.items()},
            timings={key: round(value, 3) for key, value in timings.items()},
            warnings=warnings,
        )

    def _judge_conflicts(
        self,
        *,
        profile: UploadedBillProfile,
        bill_text: str,
        candidates: dict[str, list],
        warnings: list[str],
    ) -> list[ConflictFinding]:
        if not any(candidates.values()):
            warnings.append("No candidate statutes were retrieved.")
            return []

        bill_context = {
            "title": profile.title,
            "summary": profile.summary,
            "origin_country": profile.origin_country,
            "origin_state_code": profile.origin_state_code,
            "policy_domains": profile.policy_domains,
            "affected_entities": profile.affected_entities,
            "required_actions": profile.required_actions,
            "prohibited_actions": profile.prohibited_actions,
            "permissions_created": profile.permissions_created,
            "enforcement_mechanisms": profile.enforcement_mechanisms,
            "named_agencies": profile.named_agencies,
            "explicit_citations": profile.explicit_citations,
            "key_clauses": [clause.model_dump() for clause in profile.key_clauses],
        }
        bill_excerpt = bill_text[:12000]

        findings: list[ConflictFinding] = []
        for source_system in ("california", "federal"):
            source_candidates = candidates.get(source_system, [])
            if not source_candidates:
                continue
            source_findings = self._judge_source_conflicts(
                source_system=source_system,
                bill_context=bill_context,
                bill_excerpt=bill_excerpt,
                candidates=source_candidates,
                warnings=warnings,
            )
            if self._needs_pairwise_verification(
                source_system=source_system,
                candidates=source_candidates,
                findings=source_findings,
            ):
                source_findings = self._merge_verified_findings(
                    source_findings,
                    self._pairwise_verify_candidates(
                        source_system=source_system,
                        bill_context=bill_context,
                        bill_excerpt=bill_excerpt,
                        candidates=source_candidates[:4],
                        warnings=warnings,
                    ),
                )
            heuristic_findings = self._heuristic_pattern_findings(
                source_system=source_system,
                profile=profile,
                candidates=source_candidates[:6],
            )
            if heuristic_findings:
                warnings.append(f"{source_system.title()} heuristic conflict rules contributed results.")
                source_findings = self._merge_verified_findings(source_findings, heuristic_findings)
            if source_system == "federal" and not source_findings:
                source_findings = self._heuristic_federal_findings(profile=profile, candidates=source_candidates)
                if source_findings:
                    warnings.append("Federal conflict heuristic fallback contributed results.")
            if source_system == "federal":
                source_findings = self._prefer_specific_federal_findings(source_findings)
            findings.extend(source_findings)

        findings = self._postprocess_findings(profile=profile, findings=findings)
        return sorted(findings, key=lambda item: item.confidence, reverse=True)

    def _judge_source_conflicts(
        self,
        *,
        source_system: str,
        bill_context: dict,
        bill_excerpt: str,
        candidates: list,
        warnings: list[str],
    ) -> list[ConflictFinding]:
        candidate_map = {}
        serialized_candidates = []
        for candidate in candidates:
            candidate_id = f"{source_system}:{candidate.document_id}"
            candidate_map[candidate_id] = candidate
            serialized_candidates.append(
                {
                    "candidate_id": candidate_id,
                    "source_system": source_system,
                    "source_kind": candidate.source_kind,
                    "citation": candidate.citation,
                    "heading": candidate.heading,
                    "hierarchy_path": candidate.hierarchy_path,
                    "source_url": candidate.source_url,
                    "excerpt": candidate.excerpt,
                    "score": round(candidate.final_score, 4),
                    "matched_queries": candidate.matched_queries,
                }
            )

        try:
            payload = self.codex.chat_json(
                system_prompt=CONFLICT_JUDGE_PROMPT,
                user_prompt=(
                    f"Analyze this uploaded bill for actual conflicts with the {source_system} candidate statutes only.\n\n"
                    f"Bill profile:\n{json.dumps(bill_context, indent=2)}\n\n"
                    f"Bill excerpt:\n{bill_excerpt}\n\n"
                    f"{source_system.title()} candidates:\n{json.dumps(serialized_candidates, indent=2)}"
                ),
            )
            response = ConflictJudgeResponse.model_validate(payload)
        except Exception as exc:
            warnings.append(f"{source_system.title()} conflict judge fallback triggered: {exc}")
            return []

        findings: list[ConflictFinding] = []
        for item in response.conflicts:
            candidate = candidate_map.get(item.candidate_id)
            if not candidate:
                continue
            finding = ConflictFinding(
                candidate_id=item.candidate_id,
                source_system=candidate.source_system,
                source_kind=candidate.source_kind,
                citation=candidate.citation,
                heading=candidate.heading,
                hierarchy_path=candidate.hierarchy_path,
                source_url=candidate.source_url,
                conflict_type=item.conflict_type,
                severity=item.severity,
                confidence=item.confidence,
                bill_excerpt=item.bill_excerpt,
                statute_excerpt=item.statute_excerpt or candidate.excerpt,
                explanation=item.explanation,
                why_conflict=item.why_conflict,
            )
            if source_system == "federal" and self._is_weak_federal_finding(finding):
                continue
            findings.append(finding)
        return findings

    def _is_weak_federal_finding(self, finding: ConflictFinding) -> bool:
        explanation = (finding.explanation or "").lower()
        weak_markers = (
            "no direct conflict",
            "no conflict on the numeric floor",
            "not directly below the federal floor",
            "there is no conflict on the numeric floor",
        )
        return any(marker in explanation for marker in weak_markers)

    def _needs_pairwise_verification(self, *, source_system: str, candidates: list, findings: list[ConflictFinding]) -> bool:
        if not candidates:
            return False
        found_citations = {finding.citation for finding in findings}
        return candidates[0].citation not in found_citations

    def _pairwise_verify_candidates(
        self,
        *,
        source_system: str,
        bill_context: dict,
        bill_excerpt: str,
        candidates: list,
        warnings: list[str],
    ) -> list[ConflictFinding]:
        findings: list[ConflictFinding] = []
        for candidate in candidates:
            try:
                payload = self.codex.chat_json(
                    system_prompt=PAIRWISE_VERIFICATION_PROMPT,
                    user_prompt=(
                        f"Verify whether this uploaded bill conflicts with this {source_system} statute.\n\n"
                        f"Bill profile:\n{json.dumps(bill_context, indent=2)}\n\n"
                        f"Bill excerpt:\n{bill_excerpt}\n\n"
                        f"Candidate statute:\n{json.dumps({'citation': candidate.citation, 'heading': candidate.heading, 'hierarchy_path': candidate.hierarchy_path, 'source_url': candidate.source_url, 'excerpt': candidate.excerpt, 'source_kind': candidate.source_kind}, indent=2)}"
                    ),
                )
                response = CandidateVerificationResponse.model_validate(payload)
            except Exception as exc:
                warnings.append(f"{source_system.title()} pairwise verification failed for {candidate.citation}: {exc}")
                continue

            if not response.is_conflict:
                continue
            finding = ConflictFinding(
                candidate_id=f"{source_system}:{candidate.document_id}",
                source_system=source_system,
                source_kind=candidate.source_kind,
                citation=candidate.citation,
                heading=candidate.heading,
                hierarchy_path=candidate.hierarchy_path,
                source_url=candidate.source_url,
                conflict_type=response.conflict_type,
                severity=response.severity,
                confidence=response.confidence,
                bill_excerpt=response.bill_excerpt,
                statute_excerpt=response.statute_excerpt or candidate.excerpt,
                explanation=response.explanation,
                why_conflict=response.why_conflict,
            )
            if source_system == "federal" and self._is_weak_federal_finding(finding):
                continue
            findings.append(finding)
        return findings

    def _merge_verified_findings(self, existing: list[ConflictFinding], verified: list[ConflictFinding]) -> list[ConflictFinding]:
        merged: dict[tuple[str, str], ConflictFinding] = {
            (finding.source_system, finding.citation): finding for finding in existing
        }
        for finding in verified:
            key = (finding.source_system, finding.citation)
            current = merged.get(key)
            if current is None or finding.confidence > current.confidence:
                merged[key] = finding
        return list(merged.values())

    def _prefer_specific_federal_findings(self, findings: list[ConflictFinding]) -> list[ConflictFinding]:
        has_218 = any(finding.citation.startswith("29 U.S.C. § 218") for finding in findings)
        if not has_218:
            return findings
        return [finding for finding in findings if not finding.citation.startswith("29 U.S.C. § 206")]

    def _postprocess_findings(self, *, profile: UploadedBillProfile, findings: list[ConflictFinding]) -> list[ConflictFinding]:
        if not findings:
            return []

        profile_text = " ".join(
            [profile.summary, *profile.permissions_created, *profile.required_actions, *(clause.text for clause in profile.key_clauses)]
        ).lower()
        filtered = findings

        if "minimum wage" in profile_text:
            preferred_prefixes = (
                "LAB 1182.12",
                "LAB 1197",
                "LAB 1197.1",
                "LAB 1194",
                "LAB 1194.2",
                "LAB 226.2",
                "29 U.S.C. § 218",
                "29 U.S.C. § 206",
            )
            preferred = [finding for finding in filtered if finding.citation.startswith(preferred_prefixes)]
            if preferred:
                filtered = preferred
        elif any(phrase in profile_text for phrase in ("overtime", "meal period", "rest period", "80 hours", "14 hours")):
            preferred_prefixes = (
                "LAB 510",
                "LAB 511",
                "LAB 512",
                "LAB 226.7",
                "29 U.S.C. § 207",
                "29 U.S.C. § 218",
            )
            preferred = [finding for finding in filtered if finding.citation.startswith(preferred_prefixes)]
            if preferred:
                filtered = preferred

        deduped: dict[str, ConflictFinding] = {}
        for finding in filtered:
            family = re.sub(r"\([^)]+\)$", "", finding.citation).strip()
            current = deduped.get(family)
            if current is None or finding.confidence > current.confidence:
                deduped[family] = finding
        return list(deduped.values())

    def _heuristic_pattern_findings(
        self,
        *,
        source_system: str,
        profile: UploadedBillProfile,
        candidates: list,
    ) -> list[ConflictFinding]:
        permissions_text = " ".join(
            [profile.summary, *profile.required_actions, *profile.permissions_created, *(clause.text for clause in profile.key_clauses)]
        ).lower()
        bill_wage_amounts = [float(match) for match in re.findall(r"\$?\s*(\d+(?:\.\d+)?)", permissions_text)]
        bill_floor = min(bill_wage_amounts) if bill_wage_amounts else None
        findings: list[ConflictFinding] = []

        def add(candidate, conflict_type: str, explanation: str, confidence: float) -> None:
            findings.append(
                ConflictFinding(
                    candidate_id=f"{source_system}:{candidate.document_id}",
                    source_system=source_system,
                    source_kind=candidate.source_kind,
                    citation=candidate.citation,
                    heading=candidate.heading,
                    hierarchy_path=candidate.hierarchy_path,
                    source_url=candidate.source_url,
                    conflict_type=conflict_type,
                    severity="high" if confidence >= 0.9 else "medium",
                    confidence=confidence,
                    bill_excerpt=(profile.key_clauses[0].text if profile.key_clauses else profile.summary),
                    statute_excerpt=candidate.excerpt,
                    explanation=explanation,
                    why_conflict="Deterministic fallback on strong wage-and-hour conflict signals.",
                )
            )

        for candidate in candidates:
            citation = candidate.citation or ""
            text = (candidate.excerpt or "").lower()
            if "minimum wage" in permissions_text:
                allowed_min_wage = (
                    citation.startswith("LAB 1182.12")
                    or citation.startswith("LAB 1197")
                    or citation.startswith("LAB 1197.1")
                    or citation.startswith("LAB 1194")
                    or citation.startswith("LAB 1194.2")
                    or citation.startswith("LAB 226.2")
                    or citation.startswith("29 U.S.C. § 206")
                    or citation.startswith("29 U.S.C. § 218")
                )
                if not allowed_min_wage:
                    continue
                excerpt_amounts = [float(match) for match in re.findall(r"\$?\s*(\d+(?:\.\d+)?)", text)]
                has_higher_floor = bill_floor is not None and any(amount > bill_floor + 0.01 for amount in excerpt_amounts)
                if "minimum wage" in text and (
                    has_higher_floor
                    or "payment of a lower wage" in text
                    or "less than the applicable state or local minimum wage" in text
                    or "unpaid minimum wages" in text
                    or "higher than the minimum wage established" in text
                    or "municipal ordinance establishing a minimum wage higher" in text
                ):
                    add(
                        candidate,
                        "threshold conflict" if source_system == "california" else "federal preemption",
                        "The bill authorizes or deems compliant a lower wage rule, while the candidate statute preserves or requires a higher applicable minimum wage standard.",
                        0.95 if source_system == "california" else 0.92,
                    )
                    continue
            if any(phrase in permissions_text for phrase in ("without overtime", "80 hours", "14 hours", "40 hours")):
                allowed_overtime = (
                    citation.startswith("LAB 510")
                    or citation.startswith("LAB 511")
                    or citation.startswith("LAB 512")
                    or citation.startswith("LAB 512.1")
                    or citation.startswith("LAB 512.2")
                    or citation.startswith("LAB 226.7")
                    or citation.startswith("LAB 226.75")
                    or citation.startswith("29 U.S.C. § 207")
                    or citation.startswith("29 U.S.C. § 218")
                )
                if not allowed_overtime:
                    continue
                if any(phrase in text for phrase in ("overtime", "40 hours", "eight hours", "one-half", "double time")):
                    add(
                        candidate,
                        "compliance impossibility" if source_system == "federal" else "state contradiction",
                        "The bill would authorize work beyond the cited threshold without overtime protections, while the candidate statute requires overtime or premium pay once those thresholds are crossed.",
                        0.95,
                    )
                    continue
            if any(phrase in permissions_text for phrase in ("without a meal period", "without meal period", "without a rest period", "without rest period")):
                allowed_breaks = (
                    citation.startswith("LAB 512")
                    or citation.startswith("LAB 512.1")
                    or citation.startswith("LAB 512.2")
                    or citation.startswith("LAB 226.7")
                    or citation.startswith("LAB 226.75")
                )
                if not allowed_breaks:
                    continue
                if "meal period" in text or "rest period" in text:
                    add(
                        candidate,
                        "procedure conflict",
                        "The bill would allow work through meal or rest periods that the candidate statute requires or protects.",
                        0.94,
                    )
        return findings

    def _heuristic_federal_findings(self, *, profile: UploadedBillProfile, candidates: list) -> list[ConflictFinding]:
        findings: list[ConflictFinding] = []
        permissions_text = " ".join(
            [*profile.required_actions, *profile.permissions_created, *profile.conflict_search_phrases, *(clause.text for clause in profile.key_clauses)]
        ).lower()

        def add_finding(candidate, conflict_type: str, explanation: str, confidence: float) -> None:
            findings.append(
                ConflictFinding(
                    candidate_id=f"federal:{candidate.document_id}",
                    source_system="federal",
                    source_kind=candidate.source_kind,
                    citation=candidate.citation,
                    heading=candidate.heading,
                    hierarchy_path=candidate.hierarchy_path,
                    source_url=candidate.source_url,
                    conflict_type=conflict_type,
                    severity="high" if confidence >= 0.9 else "medium",
                    confidence=confidence,
                    bill_excerpt=(profile.key_clauses[0].text if profile.key_clauses else profile.summary),
                    statute_excerpt=candidate.excerpt,
                    explanation=explanation,
                    why_conflict="Rule-based fallback on an obvious federal floor conflict.",
                )
            )

        for candidate in candidates:
            citation = (candidate.citation or "").lower()
            if citation.startswith("29 u.s.c. § 207"):
                if "without overtime" in permissions_text or "40 hours" in permissions_text or "80 hours" in permissions_text:
                    add_finding(
                        candidate,
                        "compliance impossibility",
                        "The bill would authorize work beyond 40 hours in a workweek without overtime compensation, while 29 U.S.C. § 207 requires overtime pay for covered employees working more than 40 hours in a workweek.",
                        0.95,
                    )
            elif citation.startswith("29 u.s.c. § 206"):
                if re.search(r"\$?\s*([0-6](?:\.\d+)?|7(?:\.0|\.00)?)", permissions_text):
                    add_finding(
                        candidate,
                        "threshold conflict",
                        "The bill appears to authorize wages below the federal minimum wage floor in 29 U.S.C. § 206.",
                        0.93,
                    )
            elif citation.startswith("29 u.s.c. § 218"):
                if any(phrase in permissions_text for phrase in ("no state or local agency shall require", "higher hourly minimum wage", "notwithstanding any other law", "without overtime compensation")):
                    add_finding(
                        candidate,
                        "federal preemption",
                        "The bill would treat a lower wage-or-hour rule as lawful notwithstanding stricter applicable wage protections, while 29 U.S.C. § 218 preserves higher state and local protections and does not excuse noncompliance with them.",
                        0.9,
                    )
        return findings
