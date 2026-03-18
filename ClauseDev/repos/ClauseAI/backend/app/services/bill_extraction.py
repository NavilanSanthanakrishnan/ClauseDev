import io
import re
import base64
from typing import Optional
from pypdf import PdfReader
import docx

from app.utils.bill_cleaning import clean_bill_text

def clean_extracted_text(text: str) -> str:
    text = text.replace('\t', ' ')
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    text = re.sub(r'\s+([.,;:)])', r'\1', text)
    text = re.sub(r'([([])\s+', r'\1', text)
    return text.strip()

def normalize_extracted_bill_text(text: str) -> str:
    normalized = clean_extracted_text(text)
    return clean_bill_text(normalized, aggressive=True)

def _decode_file_content(file_content: str, file_type: str) -> bytes:
    if file_type == "txt":
        try:
            return base64.b64decode(file_content)
        except Exception:
            return file_content.encode("utf-8")

    try:
        return base64.b64decode(file_content)
    except Exception as error:
        raise ValueError("Invalid base64 encoded file content") from error

def extract_text_from_file(
    file_type: str,
    file_content: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
) -> str:
    normalized_type = (file_type or "").lower().strip()
    if not normalized_type:
        raise ValueError("file_type is required")

    if file_bytes is None and file_content is None:
        raise ValueError("Either file_content or file_bytes must be provided")

    payload = file_bytes if file_bytes is not None else _decode_file_content(file_content or "", normalized_type)

    if normalized_type == "txt":
        text = payload.decode("utf-8", errors="ignore")
        return normalize_extracted_bill_text(text)

    file_obj = io.BytesIO(payload)

    if normalized_type == "pdf":
        reader = PdfReader(file_obj)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return normalize_extracted_bill_text(text)

    if normalized_type == "docx":
        document = docx.Document(file_obj)
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return normalize_extracted_bill_text(text)

    raise ValueError(f"Unsupported file type: {normalized_type}")