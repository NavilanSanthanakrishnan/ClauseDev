import requests
import json
import os
from auth_utils import get_auth_headers

BASE_URL = "http://localhost:8000"

def test_root():
    print("\nTesting Root Endpoint")
    headers = get_auth_headers(BASE_URL)

    response = requests.get(f"{BASE_URL}/", headers=headers)

    print(f"Status Code: {response.status_code}")
    response.raise_for_status()

    result = response.json()
    endpoints = result.get("endpoints", {})
    if "bill_inspect" not in endpoints:
        raise AssertionError("Root endpoints payload is missing bill_inspect")
    print(json.dumps(result, indent=4))

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/step0_root.json", "w") as f:
        json.dump(result, f, indent=4)

    print("\nOutput saved to: outputs/step0_root.json")

    return result

if __name__ == "__main__":
    test_root()