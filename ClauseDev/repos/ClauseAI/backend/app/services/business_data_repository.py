import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import (
    BUSINESS_DATA_ALLOW_LOCAL_FALLBACK,
    BUSINESS_DATA_CACHE_DIR,
    SUPABASE_BUSINESS_DATA_BUCKET,
    SUPABASE_STORAGE_REMOTE_ENABLED,
)
from app.services.supabase_service import download_storage_bytes

logger = logging.getLogger(__name__)

class BusinessDataRepository:
    def __init__(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[3]
        self.backend_root = self.repo_root / "backend"
        self.cache_root = self.backend_root / BUSINESS_DATA_CACHE_DIR

    @staticmethod
    def _normalize(path: str) -> str:
        normalized = path.replace("\\", "/").lstrip("./")
        if normalized.startswith("backend/"):
            normalized = normalized[len("backend/") :]
        return normalized

    def _source_local_path(self, relative_path: str) -> Path:
        return self.backend_root / relative_path

    def _cache_path(self, relative_path: str) -> Path:
        return self.cache_root / relative_path

    def _download_to_cache(self, relative_path: str) -> Path:
        cache_path = self._cache_path(relative_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = download_storage_bytes(SUPABASE_BUSINESS_DATA_BUCKET, relative_path)
        cache_path.write_bytes(payload)
        return cache_path

    def get_local_path(self, path: str) -> Path:
        relative_path = self._normalize(path)
        source_local = self._source_local_path(relative_path)

        if not SUPABASE_STORAGE_REMOTE_ENABLED:
            if source_local.exists():
                return source_local
            raise FileNotFoundError(f"Business data not found: {relative_path}")

        cache_path = self._cache_path(relative_path)
        if cache_path.exists():
            return cache_path

        try:
            return self._download_to_cache(relative_path)
        except Exception as error:
            if BUSINESS_DATA_ALLOW_LOCAL_FALLBACK and source_local.exists():
                logger.warning(
                    "Falling back to local business data",
                    extra={"event": "business_data_fallback_local", "path": relative_path, "error": str(error)},
                )
                return source_local
            raise

    def read_bytes(self, path: str) -> bytes:
        return self.get_local_path(path).read_bytes()

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return self.get_local_path(path).read_text(encoding=encoding, errors="ignore")

    def read_json(self, path: str) -> Any:
        return json.loads(self.read_text(path))

business_data_repo = BusinessDataRepository()