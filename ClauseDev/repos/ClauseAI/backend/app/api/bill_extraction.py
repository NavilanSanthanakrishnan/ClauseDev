import mimetypes
import time
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.core.config import SUPABASE_USER_FILES_BUCKET
from app.core.supabase_auth import AuthenticatedUser
from app.models.requests import BillTextExtractionRequest
from app.models.responses import BillTextExtractionResponse
from app.services import extract_text_from_file
from app.services.supabase_service import download_storage_bytes, record_user_file
from app.utils.request_store import request_store
from app.api.common import (
    start_request,
    elapsed_seconds,
    mark_request_failed,
    get_status_payload,
    get_result_payload,
)

router = APIRouter()
logger = logging.getLogger(__name__)

def _resolve_file_type(request: BillTextExtractionRequest) -> str:
    if request.file_type:
        return request.file_type
    if request.original_file_name:
        suffix = Path(request.original_file_name).suffix.lower().lstrip(".")
        if suffix:
            return suffix
    if request.storage_path:
        suffix = Path(request.storage_path).suffix.lower().lstrip(".")
        if suffix:
            return suffix
    raise ValueError("file_type is required when it cannot be inferred from file name/path")

@router.post("/extract-text", response_model=BillTextExtractionResponse)
async def extract_bill_text(
    request: BillTextExtractionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    start_time = time.time()
    record = start_request("bill_text_extraction", request.request_id)

    try:
        resolved_type = _resolve_file_type(request)
        payload_bytes = None

        if request.storage_path:
            bucket = request.bucket or SUPABASE_USER_FILES_BUCKET
            payload_bytes = download_storage_bytes(bucket, request.storage_path)
            record_user_file(
                user_id=current_user.user_id,
                bucket=bucket,
                path=request.storage_path,
                original_name=request.original_file_name,
                mime_type=request.mime_type
                or mimetypes.guess_type(request.original_file_name or request.storage_path)[0],
                size_bytes=request.size_bytes if request.size_bytes is not None else len(payload_bytes),
            )

        extracted_text = extract_text_from_file(
            file_type=resolved_type,
            file_content=request.file_content,
            file_bytes=payload_bytes,
        )

        processing_time = elapsed_seconds(start_time)
        request_store.mark_completed(record.request_id, {"text": extracted_text})

        return BillTextExtractionResponse(
            success=True,
            step="bill_text_extraction",
            processing_time=processing_time,
            data=extracted_text,
            request_id=record.request_id,
            status="completed",
        )

    except HTTPException:
        raise
    except Exception as error:
        processing_time = elapsed_seconds(start_time)
        logger.exception(
            "Bill extraction failed with exception",
            extra={"event": "bill_extraction_exception", "request_id": record.request_id},
        )
        mark_request_failed(record, error)
        return BillTextExtractionResponse(
            success=False,
            step="bill_text_extraction",
            processing_time=processing_time,
            data=str(error),
            request_id=record.request_id,
            status="failed",
        )

@router.get("/extract-text/status")
async def get_extract_text_status(request_id: str):
    return get_status_payload(request_id)

@router.get("/extract-text/result")
async def get_extract_text_result(request_id: str):
    return get_result_payload(request_id)