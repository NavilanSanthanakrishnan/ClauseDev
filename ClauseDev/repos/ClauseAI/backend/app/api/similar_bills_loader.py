import time
from fastapi import APIRouter

from app.models.requests import SimilarBillsLoadRequest
from app.models.responses import SimilarBillsLoadResponse, LoadedBillWithCategories
from app.services import load_similar_bills
from app.core.config import DEFAULT_JURISDICTION
from app.utils.request_store import request_store
from app.api.common import (
    start_request,
    elapsed_seconds,
    get_status_payload,
    get_result_payload,
    launch_background_job
)

router = APIRouter()

@router.post("/load-similar-bills", response_model=SimilarBillsLoadResponse)
async def load_similar_bills_endpoint(request: SimilarBillsLoadRequest):
    start_time = time.time()
    existing_running = request_store.find_running("similar_bills_loading")
    if existing_running and existing_running.request_id != request.request_id:
        processing_time = elapsed_seconds(start_time)
        return SimilarBillsLoadResponse(
            success=True,
            step="similar_bills_loading",
            processing_time=processing_time,
            data={"message": "loading already in progress"},
            request_id=existing_running.request_id,
            status="running"
        )

    record = start_request("similar_bills_loading", request.request_id)
    jurisdiction = request.jurisdiction or DEFAULT_JURISDICTION
    user_bill_metadata = request.user_bill_metadata or {}

    async def load_and_shape_result():
        result = await load_similar_bills(
            similarity_matches=request.similarity_matches,
            user_bill_text=request.user_bill_text,
            user_bill_metadata=user_bill_metadata,
            jurisdiction=jurisdiction,
            streaming_state=record.state
        )
        passed_bills = [
            LoadedBillWithCategories(
                Bill_ID=b["Bill_ID"],
                Bill_Number=b.get("Bill_Number"),
                Bill_Title=b["Bill_Title"],
                Bill_Description=b["Bill_Description"],
                Bill_Text=b.get("Bill_Text"),
                Bill_URL=b.get("Bill_URL"),
                Date_Presented=b.get("Date_Presented"),
                Date_Passed=b.get("Date_Passed"),
                Votes=b.get("Votes"),
                Stage_Passed=b.get("Stage_Passed"),
                Categorized_Sentences=b["Categorized_Sentences"],
                Passed=b["Passed"]
            )
            for b in result["Passed_Bills"]
        ]

        failed_bills = [
            LoadedBillWithCategories(
                Bill_ID=b["Bill_ID"],
                Bill_Number=b.get("Bill_Number"),
                Bill_Title=b["Bill_Title"],
                Bill_Description=b["Bill_Description"],
                Bill_Text=b.get("Bill_Text"),
                Bill_URL=b.get("Bill_URL"),
                Date_Presented=b.get("Date_Presented"),
                Date_Passed=b.get("Date_Passed"),
                Votes=b.get("Votes"),
                Stage_Passed=b.get("Stage_Passed"),
                Categorized_Sentences=b["Categorized_Sentences"],
                Passed=b["Passed"]
            )
            for b in result["Failed_Bills"]
        ]

        return {
            "User_Bill": result["User_Bill"],
            "Passed_Bills": [b.dict() for b in passed_bills],
            "Failed_Bills": [b.dict() for b in failed_bills]
        }

    launch_background_job(record, load_and_shape_result)

    processing_time = elapsed_seconds(start_time)
    return SimilarBillsLoadResponse(
        success=True,
        step="similar_bills_loading",
        processing_time=processing_time,
        data={"message": "loading started"},
        request_id=record.request_id,
        status="running"
    )

@router.get("/load-similar-bills/status")
async def get_similar_bills_loader_status(request_id: str):
    return get_status_payload(request_id)

@router.get("/load-similar-bills/result")
async def get_similar_bills_loader_result(request_id: str):
    return get_result_payload(request_id)
