import os
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / '.env.local')

def _login_with_password() -> str:
    supabase_url = os.getenv('SUPABASE_URL', 'http://127.0.0.1:54321').rstrip('/')
    anon_key = os.getenv('SUPABASE_ANON_KEY', '')
    email = os.getenv('SUPABASE_TEST_EMAIL', '')
    password = os.getenv('SUPABASE_TEST_PASSWORD', '')

    if not anon_key or not email or not password:
        raise RuntimeError(
            'Set SUPABASE_ANON_KEY, SUPABASE_TEST_EMAIL, and SUPABASE_TEST_PASSWORD for test auth.'
        )

    token_url = f"{supabase_url}/auth/v1/token?grant_type=password"
    headers = {
      'apikey': anon_key,
      'Content-Type': 'application/json',
    }
    response = requests.post(token_url, headers=headers, json={'email': email, 'password': password}, timeout=15)

    if response.status_code == 400 and os.getenv('SUPABASE_TEST_AUTO_SIGNUP', 'true').lower() in {'1', 'true', 'yes'}:
        signup_url = f"{supabase_url}/auth/v1/signup"
        requests.post(signup_url, headers=headers, json={'email': email, 'password': password}, timeout=15)
        response = requests.post(token_url, headers=headers, json={'email': email, 'password': password}, timeout=15)

    if response.status_code != 200:
        raise RuntimeError(f"Supabase auth token request failed ({response.status_code}): {response.text}")

    payload = response.json()
    access_token = payload.get('access_token')
    if not access_token:
        raise RuntimeError('Supabase token response missing access_token')
    return access_token

def get_auth_headers(base_url: str = 'http://localhost:8000') -> dict:
    status_response = requests.get(f"{base_url}/auth/status", timeout=10)
    status_response.raise_for_status()
    auth_enabled = status_response.json().get('enabled', False)

    if not auth_enabled:
        return {}

    preset_token = os.getenv('SUPABASE_TEST_ACCESS_TOKEN', '')
    token = preset_token or _login_with_password()
    return {'Authorization': f'Bearer {token}'}