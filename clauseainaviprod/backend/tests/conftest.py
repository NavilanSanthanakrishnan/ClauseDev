from __future__ import annotations

from pathlib import Path

import pytest

from clause_backend.core.config import settings
from clause_backend.db import execute_script
from clause_backend.repositories.bills import replace_bills


ROOT = Path(__file__).resolve().parents[2]


TEST_RECORDS = [
    {
        "bill_id": "tn-fluoride-1",
        "identifier": "HB 2471",
        "jurisdiction": "Tennessee",
        "state_code": "TN",
        "session_name": "2025",
        "status": "Filed",
        "outcome": "Active",
        "sponsor": "Sen. Holt",
        "committee": "Water",
        "title": "Tennessee Fluoride-Free Water Act",
        "summary": "Prohibits public water systems from adding fluoride to drinking water.",
        "excerpt": "Prohibits public water systems from adding fluoride to drinking water.",
        "full_text": "A bill to prohibit public water systems from adding fluoride to drinking water.",
        "source_url": "https://example.com/tn-fluoride",
        "latest_action_date": "2025-02-01",
        "topics": ["water", "health"],
    },
    {
        "bill_id": "tn-privacy-old",
        "identifier": "SB 100",
        "jurisdiction": "Tennessee",
        "state_code": "TN",
        "session_name": "2024",
        "status": "Signed by Governor",
        "outcome": "Passed",
        "sponsor": "Sen. Alvarez",
        "committee": "Judiciary",
        "title": "Consumer Data Broker Privacy Act",
        "summary": "Regulates data brokers, consumer deletion requests, and privacy disclosures.",
        "excerpt": "Regulates data brokers, consumer deletion requests, and privacy disclosures.",
        "full_text": "Data brokers must honor deletion requests and publish privacy disclosures.",
        "source_url": "https://example.com/tn-privacy",
        "latest_action_date": "2024-01-10",
        "topics": ["privacy", "consumer"],
    },
    {
        "bill_id": "wa-privacy-new",
        "identifier": "HB 2200",
        "jurisdiction": "Washington",
        "state_code": "WA",
        "session_name": "2025",
        "status": "Committee report",
        "outcome": "Active",
        "sponsor": "Rep. Harper",
        "committee": "Technology",
        "title": "Consumer Data Broker Accountability Act",
        "summary": "Creates stronger privacy duties for data brokers and consumer data deletion rights.",
        "excerpt": "Creates stronger privacy duties for data brokers and consumer data deletion rights.",
        "full_text": "Data brokers must register, honor deletion rights, and disclose data sale practices.",
        "source_url": "https://example.com/wa-privacy",
        "latest_action_date": "2025-03-10",
        "topics": ["privacy", "consumer"],
    },
    {
        "bill_id": "in-education-1",
        "identifier": "HB 1004",
        "jurisdiction": "Indiana",
        "state_code": "IN",
        "session_name": "2025",
        "status": "Passed House",
        "outcome": "Passed",
        "sponsor": "Rep. Carter",
        "committee": "Education",
        "title": "State Board of Education Executive Director Appointment Act",
        "summary": "Allows the state board of education to appoint an executive director and update board duties.",
        "excerpt": "Allows the state board of education to appoint an executive director and update board duties.",
        "full_text": "The state board of education may appoint an executive director and define board duties.",
        "source_url": "https://example.com/in-education",
        "latest_action_date": "2025-01-20",
        "topics": ["education", "appointments"],
    },
]


@pytest.fixture()
def test_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "clause.sqlite3"
    monkeypatch.setattr(settings, "database_path", database_path)
    monkeypatch.setattr(settings, "schema_path", ROOT / "database" / "schema.sql")
    monkeypatch.setattr(settings, "seed_path", ROOT / "database" / "seed" / "bills.json")
    execute_script(settings.schema_path)
    replace_bills(TEST_RECORDS)
