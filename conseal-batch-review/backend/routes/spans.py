from typing import List
"""
Span routes — decisions, propagation, manual flagging.
"""

from fastapi import APIRouter, HTTPException
from models import (
    DecisionIn, DecisionOut, SpanOut, ManualSpanIn,
    PropagationMatch, PropagateRequest, SpotCheckResult,
)
from services import span_service

router = APIRouter(prefix="/spans", tags=["spans"])


@router.post("/{span_id}/decision")
async def make_decision(span_id: str, body: DecisionIn):
    """
    Record a decision (confirm/reject) on a span.
    Returns the decision record and any propagation matches.
    """
    decision, error, matches = await span_service.make_decision(
        span_id=span_id,
        action=body.action,
        decided_via=body.decided_via,
        action_mode=body.action_mode,
    )
    if error:
        raise HTTPException(400, error)

    return {
        "decision": decision,
        "propagation_matches": [
            {
                "span_id": m["id"],
                "document_id": m["document_id"],
                "document_title": m.get("document_title", ""),
                "text": m["text"],
                "char_start": m["char_start"],
                "char_end": m["char_end"],
                "status": m["status"],
            }
            for m in matches
            if m["status"] == "undecided"  # Only suggest undecided spans
        ],
    }


@router.get("/{span_id}/propagation", response_model=List[PropagationMatch])
async def get_propagation_matches(span_id: str):
    """Get propagation matches for a span without making a decision."""
    matches, error = await span_service.get_propagation_matches(span_id)
    if error:
        raise HTTPException(400, error)

    return [
        {
            "span_id": m["id"],
            "document_id": m["document_id"],
            "document_title": m.get("document_title", ""),
            "text": m["text"],
            "char_start": m["char_start"],
            "char_end": m["char_end"],
            "status": m["status"],
        }
        for m in matches
        if m["status"] == "undecided"
    ]


@router.post("/propagate", response_model=SpotCheckResult)
async def propagate_decision(body: PropagateRequest):
    """
    Apply a decision to multiple spans (propagation or cluster).
    If >10 targets, triggers spot-check guard.
    """
    applied, spot_check = await span_service.propagate_decision(
        source_span_id=body.source_span_id,
        action=body.action,
        target_span_ids=body.target_span_ids,
        decided_via=body.decided_via,
        action_mode=body.action_mode,
    )
    return {"applied_span_ids": applied, "spot_check_span_ids": spot_check}


@router.post("/spot-check/{span_id}")
async def spot_check_decision(span_id: str, body: DecisionIn):
    """Apply a spot-check confirmed decision to a single span."""
    decision, error = await span_service.apply_spot_check_decision(
        span_id=span_id,
        action=body.action,
        source_span_id="",  # Could be passed from frontend if needed
    )
    if error:
        raise HTTPException(400, error)
    return decision


@router.post("/manual")
async def create_manual_flag(body: ManualSpanIn):
    """
    Create a manually flagged span (Tier 3).
    Returns the new span plus propagation_matches so the frontend can offer
    to apply the same decision to matching text in other documents.
    """
    span, matches = await span_service.create_manual_flag(
        document_id=body.document_id,
        text=body.text,
        char_start=body.char_start,
        char_end=body.char_end,
        span_type=body.type,
        action_mode=body.action_mode,
    )
    return {
        "span": span,
        "propagation_matches": [
            {
                "span_id": m["id"],
                "document_id": m["document_id"],
                "document_title": m.get("document_title", ""),
                "text": m["text"],
                "char_start": m["char_start"],
                "char_end": m["char_end"],
                "status": m["status"],
            }
            for m in matches
            if m["status"] == "undecided"
        ],
    }
