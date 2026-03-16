from __future__ import annotations

import json
import math
import re
from collections import Counter, OrderedDict
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from step4.config import get_settings
from step4.models import LegalCandidate, UploadedBillProfile
from step4.services.codex_client import CodexClient
from step4.services.database import Database
from step4.services.legal_index import alias_forms, normalize_citation


GENERIC_STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "is",
    "it",
    "may",
    "must",
    "no",
    "not",
    "of",
    "on",
    "or",
    "shall",
    "that",
    "the",
    "this",
    "to",
    "under",
    "with",
}

CALIFORNIA_CODE_NAMES = {
    "government code": "GOV",
    "health and safety code": "HSC",
    "labor code": "LAB",
    "penal code": "PEN",
    "public resources code": "PRC",
    "public utilities code": "PUC",
    "welfare and institutions code": "WIC",
}

AGENTIC_SEARCH_PROMPT = """You are a legal retrieval planner operating over a structured statute database.

Return ONLY valid JSON:
{
  "stop": false,
  "reason": "",
  "actions": [
    {
      "tool": "citation_lookup|text_search|semantic_overlay|reference_expansion|hierarchy_neighbors",
      "source_system": "california|federal",
      "query": "",
      "citation": "",
      "overlay": "",
      "limit": 6,
      "reason": ""
    }
  ]
}

Rules:
- Use these tools to find stronger or missing conflicting statutes, not just more topical neighbors.
- Prefer targeted, high-value searches over broad searches.
- Use `citation_lookup` for explicit cites, likely omitted statutes, or sections suggested by the current hits.
- Use `hierarchy_neighbors` when a current hit suggests the surrounding chapter/article/title is likely relevant.
- Use `reference_expansion` when a current or explicit citation probably points to implementing, savings-clause, or related sections.
- Use `semantic_overlay` only with overlays from the prompt.
- Stop when the current candidate families already cover likely direct conflicts and implementation constraints for this source system.
- Do not exceed the action limit.
"""


def _normalize_text(text: str) -> str:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _sanitize_tsquery(text: str) -> str:
    text = _normalize_text(text)
    text = re.sub(r"[^A-Za-z0-9\s\-./§]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _important_tokens(text: str) -> list[str]:
    normalized = _normalize_text(text).lower()
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return [token for token in tokens if len(token) >= 3 and token not in GENERIC_STOPWORDS]


def _query_terms(profile: UploadedBillProfile) -> set[str]:
    parts = [
        profile.title,
        profile.summary,
        *profile.policy_domains,
        *profile.affected_entities,
        *profile.required_actions,
        *profile.prohibited_actions,
        *profile.permissions_created,
        *profile.enforcement_mechanisms,
        *profile.named_agencies,
        *profile.conflict_search_phrases,
    ]
    terms: set[str] = set()
    for part in parts:
        terms.update(_important_tokens(part))
    return terms


def _candidate_terms(candidate: LegalCandidate) -> set[str]:
    parts = [candidate.citation, candidate.heading, candidate.hierarchy_path, candidate.excerpt]
    terms: set[str] = set()
    for part in parts:
        terms.update(_important_tokens(part))
    return terms


def _best_excerpt(raw_text: str, search_terms: list[str], char_limit: int) -> str:
    clean_text = _normalize_text(raw_text)
    if not clean_text:
        return ""
    lowered = clean_text.lower()
    for term in search_terms:
        normalized = _normalize_text(term).lower()
        if len(normalized) < 5:
            continue
        idx = lowered.find(normalized[:80])
        if idx >= 0:
            start = max(0, idx - char_limit // 3)
            end = min(len(clean_text), start + char_limit)
            return clean_text[start:end]
    return clean_text[:char_limit]


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(
        settings.embedding_model,
        device=settings.embedding_device,
        local_files_only=True,
    )


class LegalRetriever:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.settings = get_settings()
        self.codex = CodexClient()

    def retrieve(self, profile: UploadedBillProfile) -> dict[str, list[LegalCandidate]]:
        california = self._retrieve_california(profile)
        federal = self._retrieve_uscode(profile)
        if self.settings.agentic_search_enabled:
            california = self._agentic_expand(profile, california, source_system="california", jurisdiction="CA")
            federal = self._agentic_expand(profile, federal, source_system="federal", jurisdiction="US")
        california = self._semantic_rerank(profile, california)
        federal = self._semantic_rerank(profile, federal)
        return {
            "california": california[: self.settings.llm_input_limit],
            "federal": federal[: self.settings.llm_input_limit],
        }

    def _query_phrases(self, profile: UploadedBillProfile) -> list[str]:
        raw_sources = [
            profile.title,
            profile.summary,
            *profile.required_actions,
            *profile.prohibited_actions,
            *profile.permissions_created,
            *profile.enforcement_mechanisms,
            *profile.named_agencies,
            *profile.explicit_citations,
            *profile.conflict_search_phrases,
            *(clause.text for clause in profile.key_clauses),
        ]
        weighted_queries: dict[str, float] = {}

        def add_query(text: str, weight: float) -> None:
            normalized = _sanitize_tsquery(text)
            if len(normalized) < 4:
                return
            key = normalized.lower()
            if key not in weighted_queries or weighted_queries[key] < weight:
                weighted_queries[key] = weight

        token_counts: Counter[str] = Counter()
        for source in raw_sources:
            token_counts.update(set(_important_tokens(source)))

        for source in raw_sources:
            normalized = _sanitize_tsquery(source)
            tokens = _important_tokens(normalized)
            if 2 <= len(tokens) <= 7:
                add_query(" ".join(tokens), len(tokens) + sum(token_counts[token] for token in set(tokens)))
            for size in (2, 3, 4):
                if len(tokens) < size:
                    continue
                for idx in range(0, len(tokens) - size + 1):
                    window = tokens[idx : idx + size]
                    weight = size * 2 + sum(token_counts[token] for token in set(window))
                    add_query(" ".join(window), weight)

        for citation in self._citation_sources(profile):
            add_query(citation, 20.0)

        combined_source_text = " | ".join(raw_sources).lower()
        if "minimum wage" in combined_source_text:
            add_query("29 U.S.C. 206 minimum wage", 24.0)
            add_query("29 U.S.C. 218 minimum wage higher state local ordinance", 25.0)
            add_query("municipal ordinance minimum wage higher", 24.0)
        if "overtime" in combined_source_text or "40 hours" in combined_source_text or "workweek" in combined_source_text:
            add_query("29 U.S.C. 207 overtime 40 hours workweek", 25.0)
            add_query("29 U.S.C. 218 maximum workweek lower", 24.0)
        if "state local minimum wage" in combined_source_text or "higher hourly minimum wage" in combined_source_text:
            add_query("higher state local minimum wage preserved", 24.0)
            add_query("state law municipal ordinance higher minimum wage", 24.0)

        ranked = [
            query
            for query, _ in sorted(weighted_queries.items(), key=lambda item: (-item[1], len(item[0]), item[0]))
        ]
        return list(OrderedDict.fromkeys(ranked))[:14]

    def _risk_overlay_terms(self, profile: UploadedBillProfile) -> list[str]:
        text = " ".join(
            [
                profile.title,
                profile.summary,
                *profile.policy_domains,
                *profile.affected_entities,
                *profile.conflict_search_phrases,
                *(clause.text for clause in profile.key_clauses),
            ]
        ).lower()
        overlays: list[str] = []
        if any(term in text for term in ("zoning", "dwelling", "single-family", "housing", "recovery", "treatment facility")):
            overlays.extend(["fair_housing", "housing_land_use", "disability_civil_rights", "ada_section504"])
        if any(term in text for term in ("minimum wage", "hourly wage")):
            overlays.extend(["minimum_wage_floor", "labor_employment"])
        if any(term in text for term in ("overtime", "meal period", "rest period", "workweek")):
            overlays.extend(["overtime_floor", "labor_employment"])
        if any(term in text for term in ("regional center", "developmental disability", "foster child")):
            overlays.extend(["child_welfare", "disability_civil_rights"])
        if any(term in text for term in ("building standards", "california building standards code", "calgreen", "energy commission")):
            overlays.extend(["building_standards_process", "california_fund_structure"])
        return list(OrderedDict.fromkeys(overlays))

    def _citation_sources(self, profile: UploadedBillProfile) -> list[str]:
        return list(
            OrderedDict.fromkeys(
                [
                    *profile.explicit_citations,
                    *profile.amended_citations,
                    *profile.repealed_citations,
                    *profile.conflict_search_phrases,
                ]
            )
        )

    def _normalized_california_citations(self, profile: UploadedBillProfile) -> list[str]:
        matches: list[str] = []
        for citation in self._citation_sources(profile):
            raw = citation.strip()
            if not raw:
                continue
            upper = raw.upper().replace("SECTION", "").replace("§", " ").strip()
            upper = re.sub(r"\s+", " ", upper)
            if re.match(r"^[A-Z]{2,5}\s+\d", upper):
                matches.append(upper.rstrip("."))
                continue
            lowered = raw.lower()
            for code_name, code_abbrev in CALIFORNIA_CODE_NAMES.items():
                if code_name in lowered:
                    number_match = re.search(r"(\d+(?:\.\d+)*)", raw)
                    if number_match:
                        matches.append(f"{code_abbrev} {number_match.group(1)}")
        return list(OrderedDict.fromkeys(matches))

    def _normalized_uscode_citations(self, profile: UploadedBillProfile) -> list[str]:
        matches: list[str] = []
        for citation in self._citation_sources(profile):
            match = re.search(r"(\d+)\s*U\.?S\.?C\.?\s*(?:§+)?\s*([0-9A-Za-z.\-()]+)", citation, re.IGNORECASE)
            if match:
                matches.append(f"{match.group(1)} U.S.C. § {match.group(2)}")
        return list(OrderedDict.fromkeys(matches))

    def _domain_hint_citations(self, profile: UploadedBillProfile, *, source_system: str) -> list[str]:
        text = " ".join(
            [
                profile.title,
                profile.summary,
                *profile.policy_domains,
                *profile.required_actions,
                *profile.permissions_created,
                *profile.enforcement_mechanisms,
                *profile.conflict_search_phrases,
                *(clause.text for clause in profile.key_clauses),
            ]
        ).lower()
        hints: list[str] = []
        if source_system == "california":
            if any(term in text for term in ("building standards", "california building standards code", "calgreen", "permit application", "energy commission")):
                hints.extend(
                    [
                        "PRC 25402",
                        "PRC 25402.1",
                        "PRC 25402.11",
                        "HSC 18930",
                        "HSC 18938.5",
                        "HSC 18941.17",
                        "HSC 18949.6",
                        "GOV 11343.4",
                    ]
                )
            if "clean transportation fund" in text or ("deposit" in text and "fund" in text):
                hints.append("GOV 16370")
            if any(term in text for term in ("regional center", "developmental disability", "foster child")):
                hints.extend(["WIC 4642", "WIC 4643", "WIC 4710"])
        else:
            if any(term in text for term in ("housing", "zoning", "recovery", "single-family", "treatment facility")):
                hints.extend(["42 U.S.C. § 3604", "42 U.S.C. § 12132", "29 U.S.C. § 794"])
            if any(term in text for term in ("minimum wage", "hourly wage")):
                hints.extend(["29 U.S.C. § 206", "29 U.S.C. § 218"])
            if any(term in text for term in ("overtime", "meal period", "rest period", "workweek")):
                hints.extend(["29 U.S.C. § 207", "29 U.S.C. § 218"])
        return list(OrderedDict.fromkeys(hints))

    def _retrieve_california(self, profile: UploadedBillProfile) -> list[LegalCandidate]:
        prioritized_citations = list(
            OrderedDict.fromkeys(
                [
                    *self._domain_hint_citations(profile, source_system="california"),
                    *self._normalized_california_citations(
                        profile.model_copy(update={"explicit_citations": profile.amended_citations})
                    ),
                    *self._normalized_california_citations(profile),
                ]
            )
        )
        return self._retrieve_from_legal_index(
            profile,
            source_system="california",
            jurisdiction="CA",
            lexical_limit=self.settings.california_lexical_limit,
            prioritized_citations=prioritized_citations,
        )

    def _retrieve_uscode(self, profile: UploadedBillProfile) -> list[LegalCandidate]:
        return self._retrieve_from_legal_index(
            profile,
            source_system="federal",
            jurisdiction="US",
            lexical_limit=self.settings.uscode_lexical_limit,
            prioritized_citations=list(
                OrderedDict.fromkeys(
                    [
                        *self._domain_hint_citations(profile, source_system="federal"),
                        *self._normalized_uscode_citations(profile),
                    ]
                )
            ),
        )

    def _retrieve_from_legal_index(
        self,
        profile: UploadedBillProfile,
        *,
        source_system: str,
        jurisdiction: str,
        lexical_limit: int,
        prioritized_citations: list[str],
    ) -> list[LegalCandidate]:
        candidates: dict[tuple[str, str], LegalCandidate] = {}
        for query in self._query_phrases(profile):
            rows = self._search_text(
                source_system=source_system,
                jurisdiction=jurisdiction,
                query=query,
                limit=lexical_limit,
            )
            self._merge_candidates(candidates, rows, query, source_system, None)

        for overlay in self._risk_overlay_terms(profile):
            overlay_rows = self._search_overlay(
                source_system=source_system,
                jurisdiction=jurisdiction,
                overlay=overlay,
                limit=max(12, lexical_limit // 3),
            )
            self._merge_candidates(candidates, overlay_rows, overlay, source_system, None, exact_boost=1.2)

        for idx, citation in enumerate(prioritized_citations):
            exact_rows = self._lookup_citation(
                source_system=source_system,
                jurisdiction=jurisdiction,
                citation=citation,
            )
            self._merge_candidates(candidates, exact_rows, citation, source_system, None, exact_boost=2.4 if idx == 0 else 1.8)

            for alias in alias_forms(citation):
                alias_rows = self._lookup_alias(
                    source_system=source_system,
                    jurisdiction=jurisdiction,
                    alias=alias,
                )
                self._merge_candidates(candidates, alias_rows, alias, source_system, None, exact_boost=1.6)

                reference_rows = self._expand_references(
                    source_system=source_system,
                    jurisdiction=jurisdiction,
                    citation=alias,
                )
                self._merge_candidates(candidates, reference_rows, alias, source_system, None, exact_boost=1.25)

        return self._finalize_candidates(profile, list(candidates.values()))

    def _search_text(self, *, source_system: str, jurisdiction: str, query: str, limit: int) -> list[dict]:
        sanitized = _sanitize_tsquery(query)
        if not sanitized:
            return []
        return self.db.legal_index.fetch_all(
            """
            SELECT
                document_id,
                source_kind,
                citation,
                COALESCE(heading, citation) AS heading,
                COALESCE(hierarchy_path, '') AS hierarchy_path,
                source_url,
                body_text,
                ts_rank_cd(search_text, websearch_to_tsquery('english', %(query)s)) AS rank
            FROM legal_document_search
            WHERE source_system = %(source_system)s
              AND jurisdiction = %(jurisdiction)s
              AND search_text @@ websearch_to_tsquery('english', %(query)s)
            ORDER BY rank DESC
            LIMIT %(limit)s
            """,
            {
                "query": sanitized,
                "source_system": source_system,
                "jurisdiction": jurisdiction,
                "limit": limit,
            },
        )

    def _search_overlay(self, *, source_system: str, jurisdiction: str, overlay: str, limit: int) -> list[dict]:
        overlay_query = overlay.replace("_", " ")
        return self.db.legal_index.fetch_all(
            """
            SELECT
                s.document_id,
                s.source_kind,
                s.citation,
                COALESCE(s.heading, s.citation) AS heading,
                COALESCE(s.hierarchy_path, '') AS hierarchy_path,
                s.source_url,
                s.body_text,
                ts_rank_cd(s.profile_search, websearch_to_tsquery('english', %(overlay_query)s)) + 0.35 AS rank
            FROM legal_semantic_search s
            WHERE s.source_system = %(source_system)s
              AND s.jurisdiction = %(jurisdiction)s
              AND (
                s.domains ? %(overlay)s
                OR s.risk_tags ? %(overlay)s
                OR s.profile_search @@ websearch_to_tsquery('english', %(overlay_query)s)
              )
            ORDER BY rank DESC
            LIMIT %(limit)s
            """,
            {
                "overlay": overlay,
                "overlay_query": overlay_query,
                "source_system": source_system,
                "jurisdiction": jurisdiction,
                "limit": limit,
            },
        )

    def _lookup_citation(self, *, source_system: str, jurisdiction: str, citation: str) -> list[dict]:
        return self.db.legal_index.fetch_all(
            """
            SELECT
                d.document_id,
                d.source_kind,
                d.citation,
                COALESCE(d.heading, d.citation) AS heading,
                COALESCE(d.hierarchy_path, '') AS hierarchy_path,
                d.source_url,
                d.body_text,
                1.0 AS rank
            FROM legal_documents d
            WHERE d.source_system = %(source_system)s
              AND d.jurisdiction = %(jurisdiction)s
              AND d.normalized_citation = %(normalized_citation)s
            LIMIT 20
            """,
            {
                "source_system": source_system,
                "jurisdiction": jurisdiction,
                "normalized_citation": normalize_citation(citation),
            },
        )

    def _lookup_alias(self, *, source_system: str, jurisdiction: str, alias: str) -> list[dict]:
        return self.db.legal_index.fetch_all(
            """
            SELECT
                d.document_id,
                d.source_kind,
                d.citation,
                COALESCE(d.heading, d.citation) AS heading,
                COALESCE(d.hierarchy_path, '') AS hierarchy_path,
                d.source_url,
                d.body_text,
                0.9 AS rank
            FROM legal_aliases a
            JOIN legal_documents d
              ON d.document_id = a.document_id
            WHERE d.source_system = %(source_system)s
              AND d.jurisdiction = %(jurisdiction)s
              AND a.normalized_alias = %(normalized_alias)s
            LIMIT 20
            """,
            {
                "source_system": source_system,
                "jurisdiction": jurisdiction,
                "normalized_alias": normalize_citation(alias),
            },
        )

    def _expand_references(self, *, source_system: str, jurisdiction: str, citation: str) -> list[dict]:
        return self.db.legal_index.fetch_all(
            """
            SELECT
                d.document_id,
                d.source_kind,
                d.citation,
                COALESCE(d.heading, d.citation) AS heading,
                COALESCE(d.hierarchy_path, '') AS hierarchy_path,
                d.source_url,
                d.body_text,
                0.7 AS rank
            FROM legal_references r
            JOIN legal_documents d
              ON d.document_id = r.document_id
            WHERE d.source_system = %(source_system)s
              AND d.jurisdiction = %(jurisdiction)s
              AND r.normalized_referenced_citation = %(normalized_alias)s
            LIMIT 20
            """,
            {
                "source_system": source_system,
                "jurisdiction": jurisdiction,
                "normalized_alias": normalize_citation(citation),
            },
        )

    def _hierarchy_neighbors(self, *, source_system: str, jurisdiction: str, citation: str, limit: int) -> list[dict]:
        if source_system == "california":
            return self.db.legal_index.fetch_all(
                """
                WITH target AS (
                    SELECT
                        metadata->>'code_abbrev' AS code_abbrev,
                        metadata->>'division' AS division,
                        metadata->>'chapter_num' AS chapter_num,
                        metadata->>'article_num' AS article_num
                    FROM legal_documents
                    WHERE source_system = %(source_system)s
                      AND jurisdiction = %(jurisdiction)s
                      AND normalized_citation = %(normalized_citation)s
                    LIMIT 1
                )
                SELECT
                    d.document_id,
                    d.source_kind,
                    d.citation,
                    COALESCE(d.heading, d.citation) AS heading,
                    COALESCE(d.hierarchy_path, '') AS hierarchy_path,
                    d.source_url,
                    d.body_text,
                    0.8 AS rank
                FROM legal_documents d
                CROSS JOIN target t
                WHERE d.source_system = %(source_system)s
                  AND d.jurisdiction = %(jurisdiction)s
                  AND d.metadata->>'code_abbrev' = t.code_abbrev
                  AND (
                    (COALESCE(t.chapter_num, '') <> '' AND d.metadata->>'chapter_num' = t.chapter_num)
                    OR (COALESCE(t.article_num, '') <> '' AND d.metadata->>'article_num' = t.article_num)
                    OR (COALESCE(t.division, '') <> '' AND d.metadata->>'division' = t.division)
                  )
                ORDER BY d.normalized_citation
                LIMIT %(limit)s
                """,
                {
                    "source_system": source_system,
                    "jurisdiction": jurisdiction,
                    "normalized_citation": normalize_citation(citation),
                    "limit": limit,
                },
            )
        return self.db.legal_index.fetch_all(
            """
            WITH target AS (
                SELECT
                    title_number,
                    metadata->>'parent_identifier' AS parent_identifier
                FROM legal_documents
                WHERE source_system = %(source_system)s
                  AND jurisdiction = %(jurisdiction)s
                  AND normalized_citation = %(normalized_citation)s
                LIMIT 1
            )
            SELECT
                d.document_id,
                d.source_kind,
                d.citation,
                COALESCE(d.heading, d.citation) AS heading,
                COALESCE(d.hierarchy_path, '') AS hierarchy_path,
                d.source_url,
                d.body_text,
                0.8 AS rank
            FROM legal_documents d
            CROSS JOIN target t
            WHERE d.source_system = %(source_system)s
              AND d.jurisdiction = %(jurisdiction)s
              AND d.title_number = t.title_number
              AND (
                COALESCE(d.metadata->>'parent_identifier', '') = COALESCE(t.parent_identifier, '')
                OR d.normalized_citation LIKE split_part(%(normalized_citation)s, ' § ', 1) || '%%'
              )
            ORDER BY d.normalized_citation
            LIMIT %(limit)s
            """,
            {
                "source_system": source_system,
                "jurisdiction": jurisdiction,
                "normalized_citation": normalize_citation(citation),
                "limit": limit,
            },
        )

    def _agentic_expand(
        self,
        profile: UploadedBillProfile,
        seed_candidates: list[LegalCandidate],
        *,
        source_system: str,
        jurisdiction: str,
    ) -> list[LegalCandidate]:
        candidates: dict[tuple[str, str], LegalCandidate] = {
            (candidate.source_system, candidate.citation): candidate.model_copy(deep=True) for candidate in seed_candidates
        }
        history: list[dict] = []
        for round_index in range(self.settings.agentic_max_rounds):
            plan = self._plan_agentic_actions(
                profile=profile,
                source_system=source_system,
                current_candidates=list(candidates.values()),
                history=history,
            )
            actions = (plan.get("actions") or [])[: self.settings.agentic_actions_per_round]
            if plan.get("stop") or not actions:
                break
            new_hits = 0
            round_results: list[dict] = []
            for action in actions:
                rows = self._execute_agentic_action(
                    action=action,
                    source_system=source_system,
                    jurisdiction=jurisdiction,
                )
                before = len(candidates)
                query_label = action.get("query") or action.get("citation") or action.get("overlay") or action.get("tool", "")
                exact_boost = 1.35 if action.get("tool") in {"citation_lookup", "hierarchy_neighbors"} else 1.15
                self._merge_candidates(candidates, rows, query_label, source_system, None, exact_boost=exact_boost)
                added = len(candidates) - before
                new_hits += max(0, added)
                round_results.append(
                    {
                        "tool": action.get("tool"),
                        "query": query_label,
                        "added_candidates": added,
                        "top_citations": [row.get("citation") for row in rows[:5]],
                    }
                )
            history.append({"round": round_index + 1, "reason": plan.get("reason", ""), "results": round_results})
            if new_hits == 0:
                break
        return list(candidates.values())

    def _plan_agentic_actions(
        self,
        *,
        profile: UploadedBillProfile,
        source_system: str,
        current_candidates: list[LegalCandidate],
        history: list[dict],
    ) -> dict:
        top_candidates = [
            {
                "citation": candidate.citation,
                "heading": candidate.heading,
                "hierarchy_path": candidate.hierarchy_path,
                "matched_queries": candidate.matched_queries[:5],
                "score": round(candidate.final_score or candidate.lexical_score, 4),
            }
            for candidate in sorted(current_candidates, key=lambda item: item.final_score or item.lexical_score, reverse=True)[:10]
        ]
        payload = {
            "source_system": source_system,
            "action_limit": self.settings.agentic_actions_per_round,
            "bill_profile": {
                "title": profile.title,
                "summary": profile.summary,
                "policy_domains": profile.policy_domains,
                "required_actions": profile.required_actions[:10],
                "permissions_created": profile.permissions_created[:10],
                "enforcement_mechanisms": profile.enforcement_mechanisms[:8],
                "explicit_citations": profile.explicit_citations,
                "amended_citations": profile.amended_citations,
                "repealed_citations": profile.repealed_citations,
                "conflict_search_phrases": profile.conflict_search_phrases[:12],
            },
            "current_candidates": top_candidates,
            "history": history,
            "suggested_overlays": self._risk_overlay_terms(profile),
        }
        try:
            return self.codex.chat_json(
                system_prompt=AGENTIC_SEARCH_PROMPT,
                user_prompt=json.dumps(payload, indent=2),
            )
        except Exception:
            return {"stop": True, "reason": "Agentic planning failed.", "actions": []}

    def _execute_agentic_action(self, *, action: dict, source_system: str, jurisdiction: str) -> list[dict]:
        tool = (action.get("tool") or "").strip()
        action_source = (action.get("source_system") or source_system).strip().lower()
        if action_source != source_system:
            return []
        limit = max(1, min(self.settings.agentic_action_limit, int(action.get("limit") or self.settings.agentic_action_limit)))
        if tool == "citation_lookup":
            citation = action.get("citation") or action.get("query") or ""
            return self._lookup_citation(source_system=source_system, jurisdiction=jurisdiction, citation=citation)
        if tool == "text_search":
            query = action.get("query") or ""
            return self._search_text(source_system=source_system, jurisdiction=jurisdiction, query=query, limit=limit)
        if tool == "semantic_overlay":
            overlay = action.get("overlay") or action.get("query") or ""
            return self._search_overlay(source_system=source_system, jurisdiction=jurisdiction, overlay=overlay, limit=limit)
        if tool == "reference_expansion":
            citation = action.get("citation") or action.get("query") or ""
            return self._expand_references(source_system=source_system, jurisdiction=jurisdiction, citation=citation)
        if tool == "hierarchy_neighbors":
            citation = action.get("citation") or action.get("query") or ""
            return self._hierarchy_neighbors(source_system=source_system, jurisdiction=jurisdiction, citation=citation, limit=limit)
        return []

    def _merge_candidates(
        self,
        existing: dict[tuple[str, str], LegalCandidate],
        rows: list[dict],
        query: str,
        source_system: str,
        source_kind: str | None,
        exact_boost: float = 1.0,
    ) -> None:
        for row in rows:
            key = (source_system, row["citation"])
            if key not in existing:
                existing[key] = LegalCandidate(
                    document_id=row["document_id"],
                    source_system=source_system,
                    source_kind=(row.get("source_kind") or source_kind or "section"),
                    citation=row["citation"],
                    heading=row.get("heading") or "",
                    hierarchy_path=row.get("hierarchy_path") or "",
                    source_url=row.get("source_url"),
                    body_text=row.get("body_text") or "",
                )
            candidate = existing[key]
            candidate.lexical_score += float(row.get("rank") or 0.0) * exact_boost
            if query and query not in candidate.matched_queries:
                candidate.matched_queries.append(query)
            if (row.get("source_kind") or source_kind) == "provision" and candidate.source_kind != "provision":
                candidate.source_kind = "provision"

    def _finalize_candidates(self, profile: UploadedBillProfile, candidates: list[LegalCandidate]) -> list[LegalCandidate]:
        if not candidates:
            return []
        search_terms = [
            profile.title,
            *profile.conflict_search_phrases,
            *profile.explicit_citations,
            *(clause.text for clause in profile.key_clauses),
        ]
        for candidate in candidates:
            candidate.excerpt = _best_excerpt(candidate.body_text, search_terms, self.settings.excerpt_char_limit)
        return sorted(candidates, key=lambda item: item.lexical_score, reverse=True)[: self.settings.semantic_input_limit]

    def _semantic_rerank(self, profile: UploadedBillProfile, candidates: list[LegalCandidate]) -> list[LegalCandidate]:
        if not candidates:
            return []

        model = _load_model()
        query_text = "\n".join(
            part
            for part in [
                profile.title,
                profile.summary,
                " ".join(profile.policy_domains),
                " ".join(profile.required_actions),
                " ".join(profile.prohibited_actions),
                " ".join(profile.permissions_created),
                " ".join(profile.named_agencies),
                " ".join(profile.conflict_search_phrases),
                " ".join(clause.text for clause in profile.key_clauses),
            ]
            if part
        )
        docs = [
            "\n".join(part for part in [candidate.citation, candidate.heading, candidate.hierarchy_path, candidate.excerpt] if part)
            for candidate in candidates
        ]
        embeddings = model.encode(
            [query_text, *docs],
            batch_size=self.settings.embedding_batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        query_embedding = embeddings[0]
        query_terms = _query_terms(profile)
        candidate_embeddings = embeddings[1:]

        for idx, candidate in enumerate(candidates):
            semantic = float(np.dot(query_embedding, candidate_embeddings[idx]))
            candidate_terms = _candidate_terms(candidate)
            overlap = 0.0
            if query_terms and candidate_terms:
                overlap = len(query_terms & candidate_terms) / max(1, math.sqrt(len(query_terms) * len(candidate_terms)))
            candidate.semantic_score = max(
                0.0,
                min(1.0, semantic * 0.72 + min(1.0, overlap) * 0.18 + min(1.0, candidate.lexical_score / 12.0) * 0.10),
            )
            candidate.final_score = candidate.semantic_score * 0.7 + min(1.0, candidate.lexical_score / 12.0) * 0.3

        return sorted(candidates, key=lambda item: item.final_score, reverse=True)
