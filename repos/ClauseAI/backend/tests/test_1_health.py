import requests
import json
import os

BASE_URL = "http://localhost:8000"

def test_health_check():
    print("\nTesting Health Check Endpoint")

    response = requests.get(f"{BASE_URL}/health")

    print(f"Status Code: {response.status_code}")
    response.raise_for_status()

    result = response.json()
    print(json.dumps(result, indent=4))

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/step1_health.json", "w") as f:
        json.dump(result, f, indent=4)

    print("\nOutput saved to: outputs/step1_health.json")

    return result

if __name__ == "__main__":
    test_health_check()