import os
import time
import logging
from fastapi import APIRouter

from app.api.common import elapsed_seconds, mark_request_failed, start_request
from app.core.config import BILLS_DATA_DIR, DEFAULT_JURISDICTION
from app.models.requests import BillInspectRequest
from app.models.responses import BillInspectResponse
from app.services.business_data_repository import business_data_repo
from app.utils.bill_cleaning import clean_bill_text
from app.utils.request_store import request_store

router = APIRouter()
logger = logging.getLogger(__name__)

def _load_bill_from_corpus(bill_id: str, jurisdiction: str):
    master_path = os.path.join(BILLS_DATA_DIR, jurisdiction, "master.json")
    master = business_data_repo.read_json(master_path)

    bill_meta = next((item for item in master if str(item.get("Bill ID")) == str(bill_id)), {}) or {}
    bill_path = os.path.join(BILLS_DATA_DIR, jurisdiction, f"cleaned_bills/{bill_id}.txt")
    try:
        raw_text = business_data_repo.read_text(bill_path)
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Bill text not found for bill_id={bill_id}") from error

    return {
        "bill_id": str(bill_id),
        "bill_number": bill_meta.get("Bill Number"),
        "title": bill_meta.get("Bill Title") or f"Bill {bill_id}",
        "description": bill_meta.get("Bill Description") or "",
        "bill_url": bill_meta.get("Bill URL"),
        "date_presented": bill_meta.get("Date Presented"),
        "date_passed": bill_meta.get("Date Passed"),
        "raw_text": raw_text
    }

@router.post("/inspect", response_model=BillInspectResponse)
async def inspect_bill_endpoint(request: BillInspectRequest):
    start_time = time.time()
    record = start_request("bill_inspect", request.request_id)

    try:
        jurisdiction = request.jurisdiction or DEFAULT_JURISDICTION

        payload = {
            "bill_id": request.bill_id,
            "bill_number": None,
            "title": request.title,
            "description": request.description,
            "bill_url": None,
            "date_presented": None,
            "date_passed": None,
            "raw_text": request.bill_text or ""
        }

        if request.bill_id:
            payload = _load_bill_from_corpus(request.bill_id, jurisdiction)
            if request.title:
                payload["title"] = request.title
            if request.description:
                payload["description"] = request.description

        if not payload["raw_text"]:
            raise ValueError("Either bill_id or bill_text must be provided")

        cleaned_text = clean_bill_text(payload["raw_text"], aggressive=True)
        result = {
            "bill_id": payload["bill_id"],
            "bill_number": payload.get("bill_number"),
            "source": request.source or ("corpus" if request.bill_id else "user"),
            "title": payload["title"],
            "description": payload["description"],
            "bill_url": payload.get("bill_url"),
            "date_presented": payload.get("date_presented"),
            "date_passed": payload.get("date_passed"),
            "cleaned_text": cleaned_text,
            "char_count": len(cleaned_text),
            "line_count": len([line for line in cleaned_text.split("\n") if line.strip()])
        }

        request_store.mark_completed(record.request_id, result)
        return BillInspectResponse(
            success=True,
            step="bill_inspect",
            processing_time=elapsed_seconds(start_time),
            data=result,
            request_id=record.request_id,
            status="completed"
        )
    except Exception as error:
        logger.exception(
            "Bill inspection failed",
            extra={"event": "bill_inspect_failed", "request_id": record.request_id},
        )
        mark_request_failed(record, error)
        return BillInspectResponse(
            success=False,
            step="bill_inspect",
            processing_time=elapsed_seconds(start_time),
            data={"Error": str(error)},
            request_id=record.request_id,
            status="failed"
        )