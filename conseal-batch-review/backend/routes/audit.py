"""
Audit log routes — read-only view of the decision trail.
"""

from fastapi import APIRouter, Query
from typing import Optional
from dal import decision_dal

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/log")
async def get_audit_log(
    document_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    decided_via: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Query the append-only decision audit log.
    Filterable by document_id, span type, and decided_via.
    """
    decisions = await decision_dal.get_decisions(
        document_id=document_id,
        span_type=type,
        decided_via=decided_via,
        limit=limit,
        offset=offset,
    )
    total = await decision_dal.get_decision_count(
        document_id=document_id,
        span_type=type,
        decided_via=decided_via,
    )
    return {"decisions": decisions, "total": total}
