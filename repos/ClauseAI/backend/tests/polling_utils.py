import time
from typing import Dict, Any
import requests

def wait_for_task_completion(
    base_url: str,
    status_path: str,
    request_id: str,
    headers: Dict[str, str],
    timeout_seconds: int = 900,
    poll_interval_seconds: int = 2
) -> Dict[str, Any]:
    started_at = time.time()
    while time.time() - started_at < timeout_seconds:
        response = requests.get(
            f"{base_url}{status_path}",
            params={"request_id": request_id},
            headers=headers,
            timeout=15
        )
        status = response.json()
        task_state = status.get("status")
        operation = status.get("current_operation", "Processing")
        progress = status.get("progress", 0)
        print(f"[{progress}%] {operation} ({task_state})")
        if task_state in {"completed", "failed"}:
            return status
        time.sleep(poll_interval_seconds)

    return {"status": "failed", "error": "Timeout waiting for task completion"}