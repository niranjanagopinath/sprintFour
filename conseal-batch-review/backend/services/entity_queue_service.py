"""
Entity Queue Service — batch-first review workflow.
Groups spans by entity text+type and resolves them in one action,
propagating across all matching documents.
"""

from __future__ import annotations
import math, random
from typing import Optional, List
from dal import entity_queue_dal, span_dal, decision_dal, category_stat_dal, pseudonym_dal

SPOT_CHECK_THRESHOLD = 10


async def get_entity_queue(show_singletons: bool = False) -> List[dict]:
    return await entity_queue_dal.get_entity_queue(show_singletons)


async def preview_resolve(
    entity_text: str, entity_type: str, action: str, action_mode: Optional[str]
) -> dict:
    """
    Return a preview of how many documents will be affected,
    plus a spot-check sample if the span count exceeds the threshold.
    Nothing is written to the DB here.
    """
    spans = await entity_queue_dal.get_undecided_spans_for_entity(entity_text, entity_type)
    affected_count = len(set(s["document_id"] for s in spans))

    needs_spot_check = len(spans) > SPOT_CHECK_THRESHOLD
    sample_spans: list = []
    if needs_spot_check:
        sample_size = math.ceil(len(spans) / 15)
        sampled = random.sample(spans, min(sample_size, len(spans)))
        sample_spans = [
            {
                "span_id": s["id"],
                "document_title": s["document_title"],
                "text": s["text"],
                "snippet": s.get("snippet", ""),
            }
            for s in sampled
        ]

    return {
        "affected_count": affected_count,
        "span_count": len(spans),
        "needs_spot_check": needs_spot_check,
        "sample_spans": sample_spans,
    }


async def resolve_entity(
    entity_text: str, entity_type: str, action: str, action_mode: Optional[str]
) -> dict:
    """
    Apply a confirm/reject decision to every undecided span for this entity
    across all documents.  Records each decision as 'propagated' in the audit log.
    """
    spans = await entity_queue_dal.get_undecided_spans_for_entity(entity_text, entity_type)
    if not spans:
        return {"applied_count": 0, "applied_ids": []}

    db_status = "confirmed" if action == "confirm" else "rejected"
    applied_ids: List[str] = []

    for span in spans:
        await span_dal.update_span_status(
            span["id"], db_status, "propagated", action_mode=action_mode
        )
        await decision_dal.create_decision(
            span_id=span["id"],
            document_id=span["document_id"],
            action=action,
            decided_via="propagated",
            confidence_at_decision=span.get("confidence"),
            action_mode=action_mode,
        )
        if action == "confirm" and action_mode == "anonymize":
            await pseudonym_dal.get_or_create_pseudonym(
                span["text"], span["type"], span["document_id"]
            )
        if span["tier"] in ("structured", "llm"):
            if action == "reject":
                await category_stat_dal.increment_reject(span["type"])
            else:
                await category_stat_dal.increment_confirm(span["type"])
        applied_ids.append(span["id"])

    return {"applied_count": len(applied_ids), "applied_ids": applied_ids}


async def abort_spot_check(entity_text: str, entity_type: str, reason: str) -> dict:
    """
    Called when the user rejects a spot-check sample for an entity action.
    Writes a BatchAuditEvent so the queue can display the failure note.
    The entity remains in the queue (partially_decided or undecided).
    """
    await entity_queue_dal.write_batch_audit_event(
        event_type="spot_check_failed_aborted",
        entity_text=entity_text,
        entity_type=entity_type,
        note=reason,
    )
    return {"success": True, "message": "Action aborted; entity left for manual review."}
