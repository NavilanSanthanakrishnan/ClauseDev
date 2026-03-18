import json
import os
import uuid
import requests
from auth_utils import get_auth_headers
from polling_utils import wait_for_task_completion

BASE_URL = "http://localhost:8000"

def read_json(path: str):
    with open(path, "r") as file:
        return json.load(file)

def test_similar_bills_loader():
    print("\nTesting Similar Bills Loader Endpoint")
    extraction_result = read_json("outputs/step2_extraction.json")
    inspect_result = read_json("outputs/step5_inspect_user_bill.json")
    metadata_result = read_json("outputs/step3_metadata.json")
    similarity_result = read_json("outputs/step4_similarity.json")

    if not all([
        extraction_result.get("success"),
        inspect_result.get("success"),
        metadata_result.get("success"),
        similarity_result.get("success")
    ]):
        print("Error: Previous steps failed")
        return None

    inspected_user_text = inspect_result.get("data", {}).get("cleaned_text") or extraction_result["data"]
    payload = {
        "request_id": f"test-similar-loader-{uuid.uuid4()}",
        "similarity_matches": similarity_result["data"],
        "user_bill_text": inspected_user_text,
        "user_bill_metadata": {
            "Title": metadata_result["data"]["Title"],
            "Description": metadata_result["data"]["Description"],
            "Summary": metadata_result["data"]["Summary"]
        },
        "jurisdiction": "CA"
    }
    headers = get_auth_headers(BASE_URL)

    start_response = requests.post(
        f"{BASE_URL}/api/similar_bills_loader/load-similar-bills",
        json=payload,
        headers=headers,
        timeout=60
    )
    print(f"Start Status Code: {start_response.status_code}")
    start_response.raise_for_status()
    start_data = start_response.json()
    print(f"Start status: {start_data.get('status')}")

    status = wait_for_task_completion(
        base_url=BASE_URL,
        status_path="/api/similar_bills_loader/load-similar-bills/status",
        request_id=payload["request_id"],
        headers=headers
    )
    print(f"Status endpoint state: {status.get('status')}")

    result_response = requests.get(
        f"{BASE_URL}/api/similar_bills_loader/load-similar-bills/result",
        params={"request_id": payload["request_id"]},
        headers=headers,
        timeout=30
    )
    result_response.raise_for_status()
    result_payload = result_response.json()
    result = {
        "success": status.get("status") == "completed",
        "step": "similar_bills_loading",
        "processing_time": 0,
        "data": result_payload.get("data"),
        "request_id": payload["request_id"],
        "status": status.get("status")
    }
    if status.get("status") != "completed":
        result["data"] = result_payload.get("data") or {"Error": status.get("error") or result_payload.get("error")}

    if status.get("status") == "completed":
        data = result.get("data", {})
        print(f"Passed bills loaded: {len(data.get('Passed_Bills', []))}")
        print(f"Failed bills loaded: {len(data.get('Failed_Bills', []))}")
    else:
        print(json.dumps(result, indent=2))

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/step6_loaded_bills.json", "w") as file:
        json.dump(result, file, indent=2)

    print("Output saved to: outputs/step6_loaded_bills.json")
    return result

if __name__ == "__main__":
    test_similar_bills_loader()