import requests
import json
import base64
import os
from auth_utils import get_auth_headers

BASE_URL = "http://localhost:8000"

def test_bill_extraction():
    print("\nTesting Bill Text Extraction Endpoint")

    sample_bill_path = "samples/bill.pdf"

    with open(sample_bill_path, "rb") as f:
        bill_bytes = f.read()
        bill_base64 = base64.b64encode(bill_bytes).decode("utf-8")

    payload = {
        "file_content": bill_base64,
        "file_type": "pdf"
    }
    headers = get_auth_headers(BASE_URL)

    print(f"Extracting text from sample bill")
    print(f"Bill file size: {len(bill_bytes)} bytes")

    response = requests.post(
        f"{BASE_URL}/api/bill_extraction/extract-text",
        json=payload,
        headers=headers
    )

    print(f"\nStatus Code: {response.status_code}")
    response.raise_for_status()

    try:
        result = response.json()
        print(json.dumps(result, indent=4))
    except json.JSONDecodeError:
        print("Server did not return valid JSON:")
        print(response.text)
        return None

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/step2_extraction.json", "w") as f:
        json.dump(result, f, indent=4)

    print("\nOutput saved to: outputs/step2_extraction.json")

    return result

if __name__ == "__main__":
    test_bill_extraction()