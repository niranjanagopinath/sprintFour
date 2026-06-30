"""
Entity Queue routes — batch-first review landing screen.
"""

from fastapi import APIRouter
from models import ResolveEntityRequest, SpotCheckAbortRequest
from services import entity_queue_service

router = APIRouter(prefix="/entity-queue", tags=["entity-queue"])


@router.get("")
async def list_entity_queue(show_singletons: bool = False):
    """List entity groups with undecided spans, sorted by occurrence_count desc."""
    return await entity_queue_service.get_entity_queue(show_singletons)


@router.post("/preview")
async def preview_entity_resolve(body: ResolveEntityRequest):
    """
    Preview how many documents a resolve action will affect.
    Returns sample_spans for spot-check when span count exceeds threshold.
    Does not modify any data.
    """
    return await entity_queue_service.preview_resolve(
        body.entity_text, body.entity_type, body.action, body.action_mode
    )


@router.post("/resolve")
async def resolve_entity(body: ResolveEntityRequest):
    """Apply a decision to all undecided spans for this entity across all documents."""
    return await entity_queue_service.resolve_entity(
        body.entity_text, body.entity_type, body.action, body.action_mode
    )


@router.post("/spot-check-abort")
async def abort_spot_check(body: SpotCheckAbortRequest):
    """
    Record a spot-check failure.  Writes a BatchAuditEvent and leaves the
    entity in the queue with a visible note.
    """
    return await entity_queue_service.abort_spot_check(
        body.entity_text, body.entity_type, body.reason
    )
