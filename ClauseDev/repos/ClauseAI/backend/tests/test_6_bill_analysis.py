import json
import os
import uuid
import requests
from auth_utils import get_auth_headers
from polling_utils import wait_for_task_completion
from test_helpers import read_json

BASE_URL = "http://localhost:8000"

def test_bill_analysis():
    print("\nTesting Bill Analysis Endpoint")
    extraction_result = read_json("outputs/step2_extraction.json")
    inspect_result = read_json("outputs/step5_inspect_user_bill.json")
    loaded_bills_result = read_json("outputs/step6_loaded_bills.json")

    if not extraction_result.get("success") or not inspect_result.get("success") or not loaded_bills_result.get("success"):
        print("Error: Previous steps failed")
        return None

    loaded_data = loaded_bills_result["data"]
    inspected_user_text = inspect_result.get("data", {}).get("cleaned_text") or extraction_result["data"]
    base_payload = {
        "request_id": f"test-bill-analysis-{uuid.uuid4()}",
        "user_bill": loaded_data["User_Bill"],
        "user_bill_raw_text": inspected_user_text,
        "passed_bills": loaded_data["Passed_Bills"],
        "failed_bills": loaded_data["Failed_Bills"],
        "policy_area": "Public Safety and Privacy",
        "jurisdiction": "CA",
    }
    headers = get_auth_headers(BASE_URL)

    report_payload = {
        **base_payload,
        "phase": "report",
    }

    start_response = requests.post(
        f"{BASE_URL}/api/bill_analysis/analyze-bill",
        json=report_payload,
        headers=headers,
        timeout=60
    )
    print(f"Start Status Code: {start_response.status_code}")
    start_response.raise_for_status()
    start_data = start_response.json()
    print(f"Start status: {start_data.get('status')}")

    status = wait_for_task_completion(
        base_url=BASE_URL,
        status_path="/api/bill_analysis/analyze-bill/status",
        request_id=report_payload["request_id"],
        headers=headers
    )
    print(f"Report phase status: {status.get('status')}")

    result_response = requests.get(
        f"{BASE_URL}/api/bill_analysis/analyze-bill/result",
        params={"request_id": report_payload["request_id"]},
        headers=headers,
        timeout=30
    )
    result_response.raise_for_status()
    report_result_payload = result_response.json()

    report_data = report_result_payload.get("data") or {}
    report_text = report_data.get("report")

    fixes_request_id = f"{report_payload['request_id']}-fixes"
    fixes_payload = {
        **base_payload,
        "request_id": fixes_request_id,
        "phase": "fixes",
        "report_context": {"report": report_text or ""}
    }

    fixes_start_response = requests.post(
        f"{BASE_URL}/api/bill_analysis/analyze-bill",
        json=fixes_payload,
        headers=headers,
        timeout=60
    )
    print(f"Fixes Start Status Code: {fixes_start_response.status_code}")
    fixes_start_response.raise_for_status()

    fixes_status = wait_for_task_completion(
        base_url=BASE_URL,
        status_path="/api/bill_analysis/analyze-bill/status",
        request_id=fixes_payload["request_id"],
        headers=headers
    )
    print(f"Fixes phase status: {fixes_status.get('status')}")

    fixes_result_response = requests.get(
        f"{BASE_URL}/api/bill_analysis/analyze-bill/result",
        params={"request_id": fixes_payload["request_id"]},
        headers=headers,
        timeout=30
    )
    fixes_result_response.raise_for_status()
    fixes_result_payload = fixes_result_response.json()
    fixes_data = fixes_result_payload.get("data") or {}

    fixes_contract_valid = (
        fixes_status.get("status") == "completed"
        and isinstance(fixes_data.get("improvements"), list)
        and isinstance(fixes_data.get("valid_improvement_indices"), list)
        and isinstance(fixes_data.get("invalid_improvements"), list)
        and isinstance(fixes_data.get("validation_summary"), dict)
    )

    result = {
        "success": status.get("status") == "completed" and fixes_status.get("status") == "completed" and fixes_contract_valid,
        "step": "bill_analysis",
        "processing_time": 0,
        "report_phase": {
            "request_id": report_payload["request_id"],
            "status": status.get("status"),
            "data": report_result_payload.get("data"),
        },
        "fixes_phase": {
            "request_id": fixes_payload["request_id"],
            "status": fixes_status.get("status"),
            "data": fixes_result_payload.get("data"),
            "contract_valid": fixes_contract_valid,
        },
    }

    if not result["success"]:
        print(json.dumps(result, indent=2))
    else:
        print(f"Report keys: {list((result['report_phase'].get('data') or {}).keys())}")
        print(f"Fixes keys: {list((result['fixes_phase'].get('data') or {}).keys())}")

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/step7_analysis.json", "w") as file:
        json.dump(result, file, indent=2)

    print("Output saved to: outputs/step7_analysis.json")
    return result

if __name__ == "__main__":
    test_bill_analysis()