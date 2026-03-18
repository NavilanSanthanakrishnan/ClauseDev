import time
import logging
from fastapi import APIRouter

from app.models.requests import TitleDescSummaryRequest
from app.models.responses import TitleDescSummaryResponse, TitleDescSummaryData
from app.services import generate_title_desc_summary
from app.utils.request_store import request_store
from app.api.common import (
    start_request,
    elapsed_seconds,
    mark_request_failed,
    get_status_payload,
    get_result_payload
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate-metadata", response_model=TitleDescSummaryResponse)
async def generate_bill_metadata(request: TitleDescSummaryRequest):
    start_time = time.time()
    record = start_request("title_desc_summary_generation", request.request_id)
    
    try:
        result = await generate_title_desc_summary(
            bill_text=request.bill_text,
            example_bill=request.example_bill,
            example_title=request.example_title,
            example_description=request.example_description,
            example_summary=request.example_summary
        )
        
        processing_time = elapsed_seconds(start_time)
        
        if "Error" in result:
            mark_request_failed(record, result.get("Error", "Unknown error"), result=result)
            return TitleDescSummaryResponse(
                success=False,
                step="title_desc_summary_generation",
                processing_time=processing_time,
                data=result,
                request_id=record.request_id,
                status="failed"
            )
        
        data = TitleDescSummaryData(
            Title=result.get("Title", ""),
            Description=result.get("Description", ""),
            Summary=result.get("Summary", "")
        )

        request_store.mark_completed(record.request_id, {"Title": data.Title, "Description": data.Description, "Summary": data.Summary})
        
        return TitleDescSummaryResponse(
            success=True,
            step="title_desc_summary_generation",
            processing_time=processing_time,
            data=data,
            request_id=record.request_id,
            status="completed"
        )
    
    except Exception as error:
        processing_time = elapsed_seconds(start_time)
        logger.exception(
            "Metadata generation failed with exception",
            extra={"event": "metadata_generation_exception", "request_id": record.request_id},
        )
        mark_request_failed(record, error)
        return TitleDescSummaryResponse(
            success=False,
            step="title_desc_summary_generation",
            processing_time=processing_time,
            data={"Error": str(error)},
            request_id=record.request_id,
            status="failed"
        )

@router.get("/generate-metadata/status")
async def get_generate_metadata_status(request_id: str):
    return get_status_payload(request_id)

@router.get("/generate-metadata/result")
async def get_generate_metadata_result(request_id: str):
    return get_result_payload(request_id)