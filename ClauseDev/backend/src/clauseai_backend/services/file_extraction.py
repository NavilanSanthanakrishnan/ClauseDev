import io
import re
from pathlib import Path

import docx
from pypdf import PdfReader


def detect_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in {"txt", "pdf", "docx"}:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")
    return suffix


def _clean_text(text: str) -> str:
    text = text.replace("\t", " ")
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


def extract_text_from_bytes(file_type: str, payload: bytes) -> str:
    if file_type == "txt":
        return _clean_text(payload.decode("utf-8", errors="ignore"))

    file_obj = io.BytesIO(payload)
    if file_type == "pdf":
        reader = PdfReader(file_obj)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return _clean_text(text)

    if file_type == "docx":
        document = docx.Document(file_obj)
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return _clean_text(text)

    raise ValueError(f"Unsupported file type: {file_type}")
