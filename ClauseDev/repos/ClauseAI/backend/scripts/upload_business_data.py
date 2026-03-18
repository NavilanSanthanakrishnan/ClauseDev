import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.env_loader import load_app_env  # noqa: E402
from app.core.config import SUPABASE_BUSINESS_DATA_BUCKET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  # noqa: E402

from supabase import create_client, ClientOptions  # noqa: E402
import httpx  # noqa: E402

def get_upload_client():
    """Create a supabase client with a generous timeout for bulk uploads."""
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY,
        options=ClientOptions(storage_client_timeout=120),
    )

def load_state(path: Path) -> Dict[str, bool]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_state(path: Path, payload: Dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", default=SUPABASE_BUSINESS_DATA_BUCKET)
    parser.add_argument("--state-file", default=str(BACKEND_ROOT / ".cache" / "business_data_upload_state.json"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=50)
    args = parser.parse_args()

    env_file = load_app_env()
    print(f"Loaded env: {env_file}")
    print("SUPABASE_URL =", SUPABASE_URL)
    print("BUCKET =", SUPABASE_BUSINESS_DATA_BUCKET)

    data_root = BACKEND_ROOT / "data"
    if not data_root.exists():
        print(f"Data directory missing: {data_root}")
        return 1

    state_path = Path(args.state_file)
    uploaded = load_state(state_path) if args.resume else {}

    all_files = [p for p in data_root.rglob("*") if p.is_file()]
    total = len(all_files)
    print(f"Found {total} files under {data_root}")

    if args.dry_run:
        for idx, path in enumerate(all_files[:20], start=1):
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            print(f"[{idx}] would upload: {rel}")
        print("Dry-run completed.")
        return 0

    # Filter out already-uploaded files upfront
    to_upload = []
    skipped_count = 0
    for path in all_files:
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        if uploaded.get(rel):
            skipped_count += 1
        else:
            to_upload.append((path, rel))

    print(f"Skipping {skipped_count} already-uploaded files, uploading {len(to_upload)}")

    lock = threading.Lock()
    uploaded_count = 0
    failed_count = 0
    processed = 0

    def upload_one(file_path: Path, rel: str) -> None:
        nonlocal uploaded_count, failed_count, skipped_count, processed
        payload = file_path.read_bytes()
        client = get_upload_client()
        max_retries = 3
        for attempt in range(max_retries):
            try:
                client.storage.from_(args.bucket).upload(
                    rel,
                    payload,
                    {"upsert": "false", "content-type": "application/octet-stream"},
                )
                with lock:
                    uploaded[rel] = True
                    uploaded_count += 1
                break
            except Exception as error:
                message = str(error).lower()
                if "already exists" in message or "duplicate" in message:
                    with lock:
                        uploaded[rel] = True
                        skipped_count += 1
                    break
                elif attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                else:
                    with lock:
                        failed_count += 1
                    print(f"failed: {rel} -> {error}")

        with lock:
            processed += 1
            if processed % 100 == 0:
                save_state(state_path, uploaded)
                print(f"Progress: {processed}/{len(to_upload)} (uploaded={uploaded_count}, skipped={skipped_count}, failed={failed_count})")

    print(f"Uploading with {args.workers} workers...")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(upload_one, fp, rel) for fp, rel in to_upload]
        for f in as_completed(futures):
            f.result()  # propagate any uncaught exceptions

    save_state(state_path, uploaded)
    print(
        "Completed upload: "
        f"uploaded={uploaded_count}, skipped={skipped_count}, failed={failed_count}, total={total}"
    )
    return 0 if failed_count == 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())
