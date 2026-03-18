import requests
import json
import os
from auth_utils import get_auth_headers

BASE_URL = "http://localhost:8000"

def test_title_description():
    print("\nTesting Title/Description/Summary Generation Endpoint")

    with open("outputs/step2_extraction.json", "r") as f:
        extraction_result = json.load(f)

    if not extraction_result.get("success"):
        print("Error: Bill extraction failed in previous step")
        return None

    bill_text = extraction_result["data"]

    payload = {
        "bill_text": bill_text,
        "example_bill": None,
        "example_title": None,
        "example_description": None,
        "example_summary": None
    }
    headers = get_auth_headers(BASE_URL)

    print(f"Generating metadata for extracted bill")
    print(f"Bill text length: {len(bill_text)} characters")

    response = requests.post(
        f"{BASE_URL}/api/title_description/generate-metadata",
        json=payload,
        headers=headers
    )

    print(f"\nStatus Code: {response.status_code}")
    response.raise_for_status()

    result = response.json()
    print(json.dumps(result, indent=4))

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/step3_metadata.json", "w") as f:
        json.dump(result, f, indent=4)

    print("\nOutput saved to: outputs/step3_metadata.json")

    return result

if __name__ == "__main__":
    test_title_description()