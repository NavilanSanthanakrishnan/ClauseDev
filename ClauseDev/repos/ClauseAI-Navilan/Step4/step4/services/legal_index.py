from __future__ import annotations

import re
from dataclasses import dataclass


CALIFORNIA_CODE_NAMES = {
    "BPC": "Business and Professions Code",
    "CCP": "Code of Civil Procedure",
    "CIV": "Civil Code",
    "EDC": "Education Code",
    "ELEC": "Elections Code",
    "FAC": "Food and Agricultural Code",
    "FAM": "Family Code",
    "GOV": "Government Code",
    "HSC": "Health and Safety Code",
    "INS": "Insurance Code",
    "LAB": "Labor Code",
    "PCC": "Public Contract Code",
    "PEN": "Penal Code",
    "PRC": "Public Resources Code",
    "PUC": "Public Utilities Code",
    "RTC": "Revenue and Taxation Code",
    "UIC": "Unemployment Insurance Code",
    "VEH": "Vehicle Code",
    "WIC": "Welfare and Institutions Code",
}


def normalize_citation(citation: str) -> str:
    text = citation.upper().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("SECTION ", "")
    text = text.rstrip(".")
    text = re.sub(r"\s*§+\s*", " § ", text)
    return text.strip()


def alias_forms(citation: str) -> list[str]:
    normalized = normalize_citation(citation)
    aliases = {normalized}
    bare = normalized.replace(" § ", " ").replace("§", " ")
    bare = re.sub(r"\s+", " ", bare).strip()
    aliases.add(bare)
    aliases.add(bare.replace(".", ""))
    aliases.add(normalized.replace(".", ""))
    return [alias for alias in aliases if alias]


@dataclass(frozen=True)
class ExtractedReference:
    referenced_citation: str
    normalized_referenced_citation: str
    reference_text: str
    reference_type: str


def extract_references(text: str) -> list[ExtractedReference]:
    refs: dict[tuple[str, str], ExtractedReference] = {}
    source = text or ""

    for match in re.finditer(r"(\d+)\s*U\.?S\.?C\.?\s*(?:§+)?\s*([0-9A-Za-z.\-()]+)", source, re.IGNORECASE):
        citation = f"{match.group(1)} U.S.C. § {match.group(2)}"
        normalized = normalize_citation(citation)
        refs[(normalized, "usc")] = ExtractedReference(
            referenced_citation=citation,
            normalized_referenced_citation=normalized,
            reference_text=match.group(0),
            reference_type="usc",
        )

    code_pattern = "|".join(re.escape(code) for code in CALIFORNIA_CODE_NAMES)
    for match in re.finditer(rf"\b({code_pattern})\s+([0-9A-Za-z.\-]+)", source, re.IGNORECASE):
        citation = f"{match.group(1).upper()} {match.group(2)}"
        normalized = normalize_citation(citation)
        refs[(normalized, "ca_code")] = ExtractedReference(
            referenced_citation=citation,
            normalized_referenced_citation=normalized,
            reference_text=match.group(0),
            reference_type="ca_code",
        )

    return list(refs.values())
