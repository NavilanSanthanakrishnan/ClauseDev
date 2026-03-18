import time
from fastapi import APIRouter

from app.models.requests import BillAnalysisRequest
from app.models.responses import BillAnalysisResponse
from app.services import analyze_bill
from app.core.config import DEFAULT_JURISDICTION
from app.utils.request_store import request_store
from app.api.common import (
    start_request,
    elapsed_seconds,
    mark_request_failed,
    get_status_payload,
    get_result_payload,
    launch_background_job
)

router = APIRouter()

@router.post("/analyze-bill", response_model=BillAnalysisResponse)
async def analyze_bill_endpoint(request: BillAnalysisRequest):
    start_time = time.time()
    existing_running = request_store.find_running("bill_analysis", metadata={"phase": request.phase})
    if existing_running and existing_running.request_id != request.request_id:
        return BillAnalysisResponse(
            success=True,
            step="bill_analysis",
            processing_time=elapsed_seconds(start_time),
            data={"message": "analysis already in progress"},
            request_id=existing_running.request_id,
            status="running"
        )

    record = start_request("bill_analysis", request.request_id, metadata={"phase": request.phase})
    jurisdiction = request.jurisdiction or DEFAULT_JURISDICTION

    if request.phase == "fixes":
        report_context = request.report_context if isinstance(request.report_context, dict) else {}
        report_text = report_context.get("report")
        if not isinstance(report_text, str) or not report_text.strip():
            error = "Missing report_context.report for fixes phase"
            mark_request_failed(record, error, result={"Error": error})
            return BillAnalysisResponse(
                success=False,
                step="bill_analysis",
                processing_time=elapsed_seconds(start_time),
                data={"Error": error},
                request_id=record.request_id,
                status="failed"
            )

    async def run_analysis():
        return await analyze_bill(
            user_bill=request.user_bill,
            user_bill_raw_text=request.user_bill_raw_text,
            passed_bills=request.passed_bills,
            failed_bills=request.failed_bills,
            policy_area=request.policy_area,
            jurisdiction=jurisdiction,
            phase=request.phase,
            report_context=request.report_context,
            streaming_state=record.state
        )

    launch_background_job(record, run_analysis)

    processing_time = elapsed_seconds(start_time)
    return BillAnalysisResponse(
        success=True,
        step="bill_analysis",
        processing_time=processing_time,
        data={"message": "analysis started"},
        request_id=record.request_id,
        status="running"
    )

@router.get("/analyze-bill/status")
async def get_bill_analysis_status(request_id: str):
    return get_status_payload(request_id)

@router.get("/analyze-bill/result")
async def get_bill_analysis_result(request_id: str):
    return get_result_payload(request_id)
