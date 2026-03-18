import json
import os
import uuid
import requests
from auth_utils import get_auth_headers

BASE_URL = "http://localhost:8000"

def read_json(path: str):
    with open(path, "r") as file:
        return json.load(file)

def save_json(path: str, data):
    os.makedirs("outputs", exist_ok=True)
    with open(path, "w") as file:
        json.dump(data, file, indent=2)

def test_bill_inspect():
    print("\nTesting Bill Inspect Endpoint")
    extraction_result = read_json("outputs/step2_extraction.json")
    metadata_result = read_json("outputs/step3_metadata.json")
    similarity_result = read_json("outputs/step4_similarity.json")

    if not extraction_result.get("success") or not metadata_result.get("success"):
        print("Error: Previous steps failed")
        return None

    headers = get_auth_headers(BASE_URL)

    user_payload = {
        "request_id": f"test-bill-inspect-user-{uuid.uuid4()}",
        "bill_text": extraction_result["data"],
        "jurisdiction": "CA",
        "source": "user",
        "title": metadata_result["data"].get("Title"),
        "description": metadata_result["data"].get("Description")
    }

    user_response = requests.post(
        f"{BASE_URL}/api/bill_inspect/inspect",
        json=user_payload,
        headers=headers,
        timeout=60
    )
    print(f"User inspect status code: {user_response.status_code}")
    user_result = user_response.json()
    save_json("outputs/step5_inspect_user_bill.json", user_result)

    if user_result.get("success"):
        user_data = user_result.get("data", {})
        print(f"User cleaned chars: {user_data.get('char_count')}")
        print(f"User cleaned lines: {user_data.get('line_count')}")
    else:
        print(f"User inspect failed: {user_result.get('data')}")

    similar_bill_result = None
    matches = similarity_result.get("data") if similarity_result.get("success") else []
    if isinstance(matches, list) and matches:
        first_match = matches[0]
        similar_payload = {
            "request_id": f"test-bill-inspect-similar-{uuid.uuid4()}",
            "bill_id": str(first_match.get("Bill_ID")),
            "jurisdiction": "CA",
            "source": "similar",
            "title": first_match.get("Bill_Title"),
            "description": first_match.get("Bill_Description")
        }
        similar_response = requests.post(
            f"{BASE_URL}/api/bill_inspect/inspect",
            json=similar_payload,
            headers=headers,
            timeout=60
        )
        print(f"Similar bill inspect status code: {similar_response.status_code}")
        similar_bill_result = similar_response.json()
        save_json("outputs/step5_inspect_similar_bill.json", similar_bill_result)

        if similar_bill_result.get("success"):
            similar_data = similar_bill_result.get("data", {})
            print(f"Inspected similar bill id: {similar_data.get('bill_id')}")
            print(f"Similar cleaned chars: {similar_data.get('char_count')}")
        else:
            print(f"Similar inspect failed: {similar_bill_result.get('data')}")
    else:
        print("No similarity matches available; skipped similar-bill inspect test.")

    return {
        "user": user_result,
        "similar": similar_bill_result
    }

if __name__ == "__main__":
    test_bill_inspect()