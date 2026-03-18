import time
from fastapi import APIRouter

from app.models.requests import StakeholderAnalysisRequest
from app.models.responses import StakeholderAnalysisResponse
from app.services import analyze_stakeholders
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

@router.post("/analyze-stakeholders", response_model=StakeholderAnalysisResponse)
async def analyze_stakeholders_endpoint(request: StakeholderAnalysisRequest):
    start_time = time.time()
    existing_running = request_store.find_running("stakeholder_analysis", metadata={"phase": request.phase})
    if existing_running and existing_running.request_id != request.request_id:
        return StakeholderAnalysisResponse(
            success=True,
            step="stakeholder_analysis",
            processing_time=elapsed_seconds(start_time),
            data={"message": "analysis already in progress"},
            request_id=existing_running.request_id,
            status="running"
        )

    record = start_request("stakeholder_analysis", request.request_id, metadata={"phase": request.phase})

    if request.phase == "fixes":
        report_context = request.report_context if isinstance(request.report_context, dict) else {}
        analysis = report_context.get("analysis")
        structured_data = report_context.get("structured_data")
        if not isinstance(analysis, str) or not analysis.strip() or not isinstance(structured_data, dict):
            error = "Missing report_context.analysis or report_context.structured_data for fixes phase"
            mark_request_failed(record, error, result={"Error": error})
            return StakeholderAnalysisResponse(
                success=False,
                step="stakeholder_analysis",
                processing_time=elapsed_seconds(start_time),
                data={"Error": error},
                request_id=record.request_id,
                status="failed"
            )

    launch_background_job(
        record,
        lambda: analyze_stakeholders(
            bill_text=request.bill_text,
            phase=request.phase,
            report_context=request.report_context,
            streaming_state=record.state
        )
    )

    processing_time = elapsed_seconds(start_time)
    return StakeholderAnalysisResponse(
        success=True,
        step="stakeholder_analysis",
        processing_time=processing_time,
        data={"message": "analysis started"},
        request_id=record.request_id,
        status="running"
    )

@router.get("/analyze-stakeholders/status")
async def get_stakeholder_analysis_status(request_id: str):
    return get_status_payload(request_id)

@router.get("/analyze-stakeholders/result")
async def get_stakeholder_analysis_result(request_id: str):
    return get_result_payload(request_id)
