import requests
import json
import os
from auth_utils import get_auth_headers

BASE_URL = "http://localhost:8000"

def test_bill_similarity():
    print("\nTesting Bill Similarity Endpoint")

    with open("outputs/step3_metadata.json", "r") as f:
        metadata_result = json.load(f)

    if not metadata_result.get("success"):
        print("Error: Metadata generation failed in previous step")
        return None

    metadata = metadata_result["data"]

    payload = {
        "title": metadata["Title"],
        "description": metadata["Description"],
        "summary": metadata["Summary"],
        "jurisdiction": "CA"
    }
    headers = get_auth_headers(BASE_URL)

    print(f"Finding similar bills for:")
    print(f"  Title: {metadata['Title'][:100]}...")
    print(f"  Description: {metadata['Description'][:100]}...")

    response = requests.post(
        f"{BASE_URL}/api/bill_similarity/find-similar",
        json=payload,
        headers=headers
    )

    print(f"\nStatus Code: {response.status_code}")
    response.raise_for_status()

    result = response.json()

    if result.get("success") and isinstance(result.get("data"), list):
        print(f"Found {len(result['data'])} similar bills")
        print(f"Processing time: {result.get('processing_time')} seconds")
        print(f"\nFirst 3 matches:")
        for i, match in enumerate(result['data'][:3]):
            print(f"\n  Match {i+1}:")
            print(f"    Bill ID: {match.get('Bill_ID')}")
            print(f"    Score: {match.get('Score')}")
            print(f"    Passed: {match.get('Passed')}")
    else:
        print(json.dumps(result, indent=4))

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/step4_similarity.json", "w") as f:
        json.dump(result, f, indent=4)

    print("\nOutput saved to: outputs/step4_similarity.json")

    return result

if __name__ == "__main__":
    test_bill_similarity()