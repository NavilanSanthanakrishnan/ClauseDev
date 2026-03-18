import os
import random
from pathlib import Path
from typing import List
from urllib.parse import urlsplit
from app.core.env_loader import load_app_env

ACTIVE_ENV_FILE = load_app_env()

def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

def _env_csv(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [value.strip() for value in raw.split(",") if value.strip()]

def _expand_loopback_origins(origins: List[str]) -> List[str]:
    if "*" in origins:
        return ["*"]

    expanded = []
    seen = set()
    loopback_hosts = {"localhost", "127.0.0.1", "::1"}

    for origin in origins:
        candidates = [origin]
        try:
            parsed = urlsplit(origin)
            if parsed.scheme in {"http", "https"} and parsed.hostname in loopback_hosts:
                suffix = f":{parsed.port}" if parsed.port else ""
                candidates = [
                    f"{parsed.scheme}://localhost{suffix}",
                    f"{parsed.scheme}://127.0.0.1{suffix}",
                    f"{parsed.scheme}://[::1]{suffix}",
                ]
        except Exception:
            candidates = [origin]

        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            expanded.append(candidate)

    return expanded

BASE_DATA_DIR = os.getenv("BASE_DATA_DIR", "data")
PROMPTS_DIR = os.path.join(BASE_DATA_DIR, "prompts")

SAMPLES_DIR = os.path.join(BASE_DATA_DIR, "samples")
BILLS_DATA_DIR = os.path.join(BASE_DATA_DIR, "bills_data")
CALIFORNIA_CODE_DIR = os.path.join(BASE_DATA_DIR, "cali_code_cata")

DEFAULT_JURISDICTION = "CA"
SUPPORTED_JURISDICTIONS = ["CA"]

DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "stepfun/step-3.5-flash:free")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEYS = [key.strip() for key in os.getenv("OPENROUTER_API_KEYS", "").split(",") if key.strip()]

def _read_openrouter_keys_file():
    repo_root = Path(__file__).resolve().parents[3]
    candidates = [repo_root / ".env.keys", repo_root / "backend" / ".env.keys"]
    for path in candidates:
        if path.exists():
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                return []
            keys = []
            for line in lines:
                trimmed = line.strip()
                if not trimmed or trimmed.startswith("#"):
                    continue
                keys.append(trimmed)
            return keys
    return []

_file_keys = _read_openrouter_keys_file()
if _file_keys:
    OPENROUTER_API_KEYS = _file_keys
elif not OPENROUTER_API_KEYS and OPENROUTER_API_KEY:
    OPENROUTER_API_KEYS = [OPENROUTER_API_KEY]

if OPENROUTER_API_KEYS:
    random.shuffle(OPENROUTER_API_KEYS)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
HF_TOKEN = os.getenv("HF_TOKEN")

DEFAULT_TEMPERATURE = 0.3
DEFAULT_TOP_P = None
ENABLE_THINKING = False
ENABLE_PROMPT_CACHING = True

DEFAULT_TOKENIZER = "bert-base-uncased"
MAX_BILL_TOKENS = 100_000

LOADER_MAX_TOKENS_PER_BATCH = 20_000 
LOADER_MAX_RETRIES = 3  
LOADER_LLM_TIMEOUT_SECONDS = int(os.getenv("LOADER_LLM_TIMEOUT_SECONDS", "75"))
LLM_REQUEST_TIMEOUT_SECONDS = int(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "120"))

SIMILARITY_STAGE1_LIMIT = 500
SIMILARITY_STAGE2_LIMIT = 50
SIMILARITY_CHUNK_SIZE = 384
SIMILARITY_MAX_CHUNKS = 24

LEGAL_NOISE_WORDS = {
    "herein", "thereof", "therein", "whereas", "subdivision", "pursuant",
    "notwithstanding", "provisions", "amended", "repealed", "added",
    "act", "code", "section", "sections", "article", "chapter", "division",
    "title", "part", "legislature", "law", "statute"
}

CONFLICT_ANALYSIS_MAX_ITERATIONS = 3
CONFLICT_ANALYSIS_MIN_INTERVAL = 5

STAKEHOLDER_ANALYSIS_MAX_ITERATIONS = 3
STAKEHOLDER_ANALYSIS_MIN_INTERVAL = 5
WEB_SEARCH_MAX_RESULTS = 5

API_TITLE = "Legislative Bill Analysis API"
API_VERSION = "1.0.0"
API_DESCRIPTION = "FastAPI backend for legislative bill analysis workflow"

RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

CORS_ALLOW_ORIGINS = _expand_loopback_origins([
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
    if origin.strip()
])

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_JWKS_URL = os.getenv(
    "SUPABASE_JWKS_URL",
    f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else "",
)
SUPABASE_AUTH_APPROVAL_REQUIRED = _env_flag("SUPABASE_AUTH_APPROVAL_REQUIRED", False)
SUPABASE_USER_FILES_BUCKET = os.getenv("SUPABASE_USER_FILES_BUCKET", "user-files")
SUPABASE_BUSINESS_DATA_BUCKET = os.getenv("SUPABASE_BUSINESS_DATA_BUCKET", "business-data")
SUPABASE_STORAGE_REMOTE_ENABLED = _env_flag("SUPABASE_STORAGE_REMOTE_ENABLED", True)
BUSINESS_DATA_CACHE_DIR = os.getenv("BUSINESS_DATA_CACHE_DIR", ".cache/business-data")
BUSINESS_DATA_ALLOW_LOCAL_FALLBACK = _env_flag("BUSINESS_DATA_ALLOW_LOCAL_FALLBACK", True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_REQUEST_BODY_PREVIEW = _env_flag("LOG_REQUEST_BODY_PREVIEW", False)
LOG_MAX_FIELD_LENGTH = int(os.getenv("LOG_MAX_FIELD_LENGTH", "4000"))
LOG_REDACT_HEADERS = [
    value.lower()
    for value in _env_csv(
        "LOG_REDACT_HEADERS",
        "authorization,cookie,set-cookie,x-api-key,proxy-authorization",
    )
]
LOG_REDACT_BODY_KEYS = [
    value.lower()
    for value in _env_csv(
        "LOG_REDACT_BODY_KEYS",
        "password,passphrase,token,auth,api_key,secret,file_content,bill_text,user_bill_raw_text",
    )
]

LOG_LLM_OUTPUTS = _env_flag("LOG_LLM_OUTPUTS", True)
LOG_LLM_PROMPTS = _env_flag("LOG_LLM_PROMPTS", True)