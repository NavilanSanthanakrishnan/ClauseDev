import time
import logging
from fastapi import APIRouter

from app.models.requests import BillSimilarityRequest
from app.models.responses import BillSimilarityResponse, SimilarityMatch
from app.services import find_similar_bills
from app.core.config import DEFAULT_JURISDICTION
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

@router.post("/find-similar", response_model=BillSimilarityResponse)
async def find_similar_bills_endpoint(request: BillSimilarityRequest):
    start_time = time.time()
    record = start_request("bill_similarity_matching", request.request_id)
    
    try:
        jurisdiction = request.jurisdiction or DEFAULT_JURISDICTION
        
        results = await find_similar_bills(
            title=request.title,
            description=request.description,
            summary=request.summary,
            jurisdiction=jurisdiction
        )
        
        processing_time = elapsed_seconds(start_time)
        
        matches = [
            SimilarityMatch(
                Bill_Text=r["Bill_Text"],
                Bill_ID=str(r["Bill_ID"]),
                Bill_Number=r.get("Bill_Number"),
                Bill_Title=r.get("Bill_Title"),
                Bill_Description=r.get("Bill_Description"),
                Bill_URL=r.get("Bill_URL"),
                Date_Presented=r.get("Date_Presented"),
                Date_Passed=r.get("Date_Passed"),
                Votes=r.get("Votes"),
                Stage_Passed=r.get("Stage_Passed"),
                Score=r["Score"],
                Passed=r["Passed"]
            )
            for r in results
        ]

        request_store.mark_completed(record.request_id, {"matches": [m.dict() for m in matches]})
        
        return BillSimilarityResponse(
            success=True,
            step="bill_similarity_matching",
            processing_time=processing_time,
            data=matches,
            request_id=record.request_id,
            status="completed"
        )
    
    except Exception as error:
        processing_time = elapsed_seconds(start_time)
        logger.exception(
            "Bill similarity failed with exception",
            extra={"event": "bill_similarity_exception", "request_id": record.request_id},
        )
        mark_request_failed(record, error)
        return BillSimilarityResponse(
            success=False,
            step="bill_similarity_matching",
            processing_time=processing_time,
            data={"Error": str(error)},
            request_id=record.request_id,
            status="failed"
        )

@router.get("/find-similar/status")
async def get_find_similar_status(request_id: str):
    return get_status_payload(request_id)

@router.get("/find-similar/result")
async def get_find_similar_result(request_id: str):
    return get_result_payload(request_id)