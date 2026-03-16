from __future__ import annotations

import io
import re
from pathlib import Path

import docx
from pypdf import PdfReader


def clean_bill_text(text: str, preserve_brackets: bool = True, aggressive: bool = False) -> str:
    structural_starts = (
        "SECTION",
        "SEC.",
        "CHAPTER",
        "Bill ",
        "Assembly Bill",
        "Senate Bill",
        "An act",
        "Approved",
        "Filed",
        "LEGISLATIVE",
        "AB ",
        "SB ",
        "Vote:",
        "Appropriation:",
        "Fiscal Committee:",
        "Local Program:",
        "The people",
        "Digest Key",
        "DIGEST",
        "Bill Text",
    )
    ending_punctuation = (".", ":", ";", ")", "]", "?", "!")

    if not text:
        return "\n"

    if not preserve_brackets:
        text = re.sub(r"\[.*?\]", "", text)

    def clean_line(line: str) -> str:
        line = line.replace("\t", " ")
        line = re.sub(r" {2,}", " ", line)
        return line.strip()

    def should_join(current_line: str, next_line: str) -> bool:
        if not current_line or not next_line:
            return False
        if any(next_line.startswith(prefix) for prefix in structural_starts):
            return False
        if (
            re.match(r"^\d+\.", next_line)
            or re.match(r"^\([a-z0-9]+\)", next_line)
            or re.match(r"^[A-Z]+\s+\d+", next_line)
        ):
            return False
        if current_line.endswith(ending_punctuation):
            if aggressive and current_line.endswith("."):
                words = current_line.split()
                if words and len(words[-1]) <= 5 and words[-1].count(".") > 1:
                    return True
            return False
        if re.search(r"Section \d+(\.\d+)*$", current_line):
            return False
        return True

    lines = [clean_line(line) for line in text.split("\n")]
    result: list[str] = []
    idx = 0
    while idx < len(lines):
        current = lines[idx]
        if not current:
            result.append(current)
            idx += 1
            continue
        while idx + 1 < len(lines) and should_join(current, lines[idx + 1]):
            current = current + " " + lines[idx + 1]
            idx += 1
        result.append(current)
        idx += 1

    text = "\n".join(result)
    text = text.replace(". ", ".\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\s+([.,;:)])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    return text.strip() + "\n"


def normalize_extracted_bill_text(text: str) -> str:
    text = text.replace("\t", " ")
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return clean_bill_text(text, aggressive=True).strip()


def detect_file_type(filename: str) -> str:
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in {"pdf", "docx", "txt"}:
        raise ValueError("Unsupported file type. Use PDF, DOCX, or TXT.")
    return extension


def extract_text_from_file(file_type: str, payload: bytes) -> str:
    file_type = file_type.lower().strip()
    if file_type == "txt":
        return normalize_extracted_bill_text(payload.decode("utf-8", errors="ignore"))

    file_obj = io.BytesIO(payload)

    if file_type == "pdf":
        reader = PdfReader(file_obj)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return normalize_extracted_bill_text(text)

    if file_type == "docx":
        document = docx.Document(file_obj)
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return normalize_extracted_bill_text(text)

    raise ValueError(f"Unsupported file type: {file_type}")

