import json
import os
import uuid
import requests
from auth_utils import get_auth_headers
from polling_utils import wait_for_task_completion
from test_helpers import read_json

BASE_URL = "http://localhost:8000"

def test_conflict_analysis():
    print("\nTesting Conflict Analysis Endpoint")
    extraction_result = read_json("outputs/step2_extraction.json")
    inspect_result = read_json("outputs/step5_inspect_user_bill.json")
    if not extraction_result.get("success") or not inspect_result.get("success"):
        print("Error: Bill extraction failed in previous step")
        return None

    inspected_user_text = inspect_result.get("data", {}).get("cleaned_text") or extraction_result["data"]
    report_payload = {
        "request_id": f"test-conflict-analysis-{uuid.uuid4()}",
        "bill_text": inspected_user_text,
        "phase": "report"
    }
    headers = get_auth_headers(BASE_URL)

    start_response = requests.post(
        f"{BASE_URL}/api/conflict_analysis/analyze-conflicts",
        json=report_payload,
        headers=headers,
        timeout=60
    )
    print(f"Start Status Code: {start_response.status_code}")
    start_response.raise_for_status()

    status = wait_for_task_completion(
        base_url=BASE_URL,
        status_path="/api/conflict_analysis/analyze-conflicts/status",
        request_id=report_payload["request_id"],
        headers=headers
    )

    if status.get("status") == "completed":
        print("Conflict analysis completed")
    else:
        print(f"Conflict analysis failed: {status.get('error')}")

    result_response = requests.get(
        f"{BASE_URL}/api/conflict_analysis/analyze-conflicts/result",
        params={"request_id": report_payload["request_id"]},
        headers=headers,
        timeout=30
    )
    result_response.raise_for_status()
    report_result = result_response.json()
    report_data = report_result.get("data") or {}

    fixes_payload = {
        "request_id": f"test-conflict-fixes-{uuid.uuid4()}",
        "bill_text": inspected_user_text,
        "phase": "fixes",
        "report_context": {
            "analysis": report_data.get("analysis", ""),
            "structured_data": report_data.get("structured_data", {})
        }
    }

    fixes_start_response = requests.post(
        f"{BASE_URL}/api/conflict_analysis/analyze-conflicts",
        json=fixes_payload,
        headers=headers,
        timeout=60
    )
    print(f"Fixes Start Status Code: {fixes_start_response.status_code}")
    fixes_start_response.raise_for_status()

    fixes_status = wait_for_task_completion(
        base_url=BASE_URL,
        status_path="/api/conflict_analysis/analyze-conflicts/status",
        request_id=fixes_payload["request_id"],
        headers=headers
    )

    fixes_result_response = requests.get(
        f"{BASE_URL}/api/conflict_analysis/analyze-conflicts/result",
        params={"request_id": fixes_payload["request_id"]},
        headers=headers,
        timeout=30
    )
    fixes_result_response.raise_for_status()
    fixes_result = fixes_result_response.json()
    fixes_data = fixes_result.get("data") or {}

    fixes_contract_valid = (
        fixes_status.get("status") == "completed"
        and isinstance(fixes_data.get("improvements"), list)
        and isinstance(fixes_data.get("valid_improvement_indices"), list)
        and isinstance(fixes_data.get("invalid_improvements"), list)
        and isinstance(fixes_data.get("validation_summary"), dict)
    )

    result = {
        "success": status.get("status") == "completed" and fixes_status.get("status") == "completed" and fixes_contract_valid,
        "report_phase": {
            "request_id": report_payload["request_id"],
            "status": status.get("status"),
            "data": report_result.get("data")
        },
        "fixes_phase": {
            "request_id": fixes_payload["request_id"],
            "status": fixes_status.get("status"),
            "data": fixes_result.get("data"),
            "contract_valid": fixes_contract_valid,
        }
    }

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/step8_conflicts.json", "w") as file:
        json.dump(result, file, indent=2)

    print("Output saved to: outputs/step8_conflicts.json")
    return result

if __name__ == "__main__":
    test_conflict_analysis()