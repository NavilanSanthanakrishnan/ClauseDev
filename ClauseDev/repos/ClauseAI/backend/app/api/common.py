import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional
from fastapi import HTTPException

from app.utils.request_store import request_store

logger = logging.getLogger(__name__)

def start_request(
    step: str,
    request_id: Optional[str],
    metadata: Optional[Dict[str, Any]] = None
):
    record = request_store.create(step, request_id, metadata=metadata)
    record.mark_running()
    logger.info(
        "Step started",
        extra={"event": "step_started", "step": step, "request_id": record.request_id},
    )
    return record

def elapsed_seconds(start_time: float) -> float:
    return time.time() - start_time

def mark_request_failed(record, error: Exception | str, result: Optional[Any] = None) -> None:
    error_text = str(error)
    payload = result if result is not None else {"Error": error_text}
    request_store.mark_failed(record.request_id, error_text, result=payload)
    logger.error(
        "Step failed",
        extra={
            "event": "step_failed",
            "request_id": record.request_id,
            "step": record.step,
            "error": error_text,
        },
    )

def get_record_or_404(request_id: str):
    record = request_store.get(request_id)
    if not record:
        logger.warning(
            "Request ID not found",
            extra={"event": "request_missing", "request_id": request_id},
        )
        raise HTTPException(status_code=404, detail="Request ID not found")
    return record

def get_status_payload(request_id: str) -> Dict[str, Any]:
    return get_record_or_404(request_id).to_status()

def get_result_payload(request_id: str) -> Dict[str, Any]:
    record = get_record_or_404(request_id)
    return {
        "request_id": record.request_id,
        "status": record.status,
        "data": record.result,
        "error": record.error
    }

def launch_background_job(
    record,
    job_factory: Callable[[], Awaitable[Any]]
) -> None:
    async def runner():
        logger.info(
            "Background job started",
            extra={
                "event": "background_job_started",
                "request_id": record.request_id,
                "step": record.step,
            },
        )
        try:
            result = await job_factory()
            if isinstance(result, dict) and "Error" in result:
                mark_request_failed(record, result.get("Error", "Unknown error"), result=result)
                return
            request_store.mark_completed(record.request_id, result)
            logger.info(
                "Background job completed",
                extra={
                    "event": "background_job_completed",
                    "request_id": record.request_id,
                    "step": record.step,
                },
            )
        except Exception as error:
            logger.exception(
                "Background job crashed",
                extra={
                    "event": "background_job_crashed",
                    "request_id": record.request_id,
                    "step": record.step,
                },
            )
            mark_request_failed(record, error)

    asyncio.create_task(runner())
