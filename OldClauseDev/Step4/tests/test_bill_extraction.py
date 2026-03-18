from __future__ import annotations

from step4.services.bill_extraction import detect_file_type, normalize_extracted_bill_text


def test_detect_file_type_supports_expected_extensions() -> None:
    assert detect_file_type("bill.pdf") == "pdf"
    assert detect_file_type("bill.docx") == "docx"
    assert detect_file_type("bill.txt") == "txt"


def test_normalize_extracted_bill_text_keeps_structural_markers() -> None:
    source = "SECTION 1.\nAn employer shall pay overtime.\nSEC. 2.\nThe act applies statewide."
    normalized = normalize_extracted_bill_text(source)
    assert "SECTION 1." in normalized
    assert "SEC. 2." in normalized
    assert "An employer shall pay overtime." in normalized
