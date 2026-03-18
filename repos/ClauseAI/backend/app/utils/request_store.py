import time
import threading
import uuid
import logging
from typing import Dict, Any, Optional
from app.utils.streaming_state import StreamingState

logger = logging.getLogger(__name__)

class RequestRecord:
    def __init__(self, request_id: str, step: str, metadata: Optional[Dict[str, Any]] = None):
        self.request_id = request_id
        self.step = step
        self.metadata = metadata or {}
        self.status = "pending"
        self.state = StreamingState()
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.updated_at = time.time()

    def mark_running(self):
        self.status = "running"
        self.updated_at = time.time()
        self.state.reset(self.step)
        logger.info(
            "Request marked running",
            extra={"event": "request_running", "request_id": self.request_id, "step": self.step},
        )

    def mark_completed(self, result: Any):
        self.status = "completed"
        self.result = result
        self.updated_at = time.time()
        self.state.complete(result)
        logger.info(
            "Request marked completed",
            extra={"event": "request_completed", "request_id": self.request_id, "step": self.step},
        )

    def mark_failed(self, error: str, result: Optional[Any] = None):
        self.status = "failed"
        self.error = error
        if result is not None:
            self.result = result
        self.updated_at = time.time()
        self.state.set_error(error)
        logger.error(
            "Request marked failed",
            extra={
                "event": "request_failed",
                "request_id": self.request_id,
                "step": self.step,
                "error": error,
            },
        )

    def to_status(self) -> Dict[str, Any]:
        payload = self.state.to_dict()
        payload.update({
            "request_id": self.request_id,
            "status": self.status,
            "data": self.result,
            "error": self.error
        })
        return payload

class RequestStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._records: Dict[str, RequestRecord] = {}

    def generate_id(self) -> str:
        return str(uuid.uuid4())

    def create(
        self,
        step: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RequestRecord:
        with self._lock:
            req_id = request_id or self.generate_id()
            record = RequestRecord(req_id, step, metadata=metadata)
            self._records[req_id] = record
            logger.info(
                "Request record created",
                extra={"event": "request_created", "request_id": req_id, "step": step},
            )
            return record

    def get(self, request_id: str) -> Optional[RequestRecord]:
        with self._lock:
            return self._records.get(request_id)

    def find_running(
        self,
        step: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[RequestRecord]:
        with self._lock:
            running_records = [
                record
                for record in self._records.values()
                if (
                    record.step == step and
                    record.status == "running" and
                    (
                        not metadata or
                        all(record.metadata.get(key) == value for key, value in metadata.items())
                    )
                )
            ]
            if not running_records:
                return None
            return max(running_records, key=lambda record: record.updated_at)

    def mark_running(self, request_id: str) -> Optional[RequestRecord]:
        with self._lock:
            record = self._records.get(request_id)
            if record:
                record.mark_running()
            return record

    def mark_completed(self, request_id: str, result: Any) -> Optional[RequestRecord]:
        with self._lock:
            record = self._records.get(request_id)
            if record:
                record.mark_completed(result)
            return record

    def mark_failed(self, request_id: str, error: str, result: Optional[Any] = None) -> Optional[RequestRecord]:
        with self._lock:
            record = self._records.get(request_id)
            if record:
                record.mark_failed(error, result)
            return record

request_store = RequestStore()
