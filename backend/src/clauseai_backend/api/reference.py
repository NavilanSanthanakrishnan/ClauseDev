from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from clauseai_backend.api.deps import get_current_user, get_reference_db
from clauseai_backend.db.session import ReferenceDatabases
from clauseai_backend.models.auth import User
from clauseai_backend.services.reference_search import get_bill_detail, get_law_detail, search_bills, search_laws

router = APIRouter(prefix="/api/reference", tags=["reference"])


@router.get("/status")
def reference_status(
    db: ReferenceDatabases = Depends(get_reference_db),
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    def scalar_count(session, sql: str) -> int | None:
        try:
            return int(session.execute(text(sql)).scalar_one())
        except Exception:
            return None

    bill_count = scalar_count(db.openstates, "select count(*) from public.opencivicdata_bill where 'bill' = any(classification)")
    law_count_parts = [
        scalar_count(db.legal_index, "select count(*) from public.legal_documents"),
        scalar_count(db.california_code, "select count(*) from public.official_law_sections"),
        scalar_count(db.uscode, "select count(*) from public.usc_nodes where kind = 'section'"),
    ]
    law_count = sum(part for part in law_count_parts if part is not None) if any(part is not None for part in law_count_parts) else None
    return {
        "bills_ready": bill_count is not None,
        "laws_ready": law_count is not None,
        "bill_count": bill_count,
        "law_count": law_count,
    }


@router.get("/bills")
def bills_search(
    q: str = Query(default="", max_length=200),
    status: str = Query(default="", max_length=64),
    state_code: str = Query(default="", max_length=16),
    limit: int = Query(default=10, ge=1, le=50),
    db: ReferenceDatabases = Depends(get_reference_db),
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    items = search_bills(db=db, query=q, limit=limit, status=status, state_code=state_code)
    return {"items": items, "query": q, "status": status, "state_code": state_code}


@router.get("/bills/{bill_id:path}")
def bill_detail(
    bill_id: str,
    db: ReferenceDatabases = Depends(get_reference_db),
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    item = get_bill_detail(db=db, bill_id=bill_id)
    if not item:
        raise HTTPException(status_code=404, detail="Bill not found")
    return item


@router.get("/laws")
def laws_search(
    q: str = Query(default="", max_length=200),
    jurisdiction: str = Query(default="", max_length=128),
    limit: int = Query(default=10, ge=1, le=50),
    db: ReferenceDatabases = Depends(get_reference_db),
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    items = search_laws(db=db, query=q, limit=limit, jurisdiction=jurisdiction)
    return {"items": items, "query": q, "jurisdiction": jurisdiction}


@router.get("/laws/{document_id:path}")
def law_detail(
    document_id: str,
    db: ReferenceDatabases = Depends(get_reference_db),
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    item = get_law_detail(db=db, document_id=document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Law not found")
    return item
