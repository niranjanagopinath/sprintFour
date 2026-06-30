"""
Document service — state transitions and priority-aware document listing.
"""

from dal import document_dal, span_dal, category_stat_dal, entity_queue_dal


async def list_documents(state=None, limit=50, offset=0):
    """List documents with priority sorting."""
    docs = await document_dal.get_documents(state=state, limit=limit, offset=offset)
    return docs


async def get_document_with_spans(doc_id: str):
    """Get full document with all its spans (excluding LLM tier by default)."""
    doc = await document_dal.get_document_by_id(doc_id)
    if not doc:
        return None

    # Get non-LLM spans, sorted by priority weight
    spans = await span_dal.get_spans_for_document(doc_id)
    non_llm_spans = [s for s in spans if s["tier"] != "llm"]

    # Apply priority weighting to undecided spans
    weights = await category_stat_dal.get_priority_weights()
    for span in non_llm_spans:
        w = weights.get(span["type"], 1.0)
        span["_priority"] = (span.get("confidence") or 0.5) * w

    # Sort: undecided first (by priority desc), then decided
    non_llm_spans.sort(
        key=lambda s: (
            0 if s["status"] == "undecided" else 1,
            -(s.get("_priority", 0.5)),
            s["char_start"],
        )
    )

    # Clean up internal fields
    for span in non_llm_spans:
        span.pop("_priority", None)

    # Attach pseudonym labels so the UI can show them for anonymized spans.
    pseudonym_rows = await _fetch_pseudonyms(non_llm_spans)
    for span in non_llm_spans:
        if span.get("action_mode") == "anonymize":
            span["pseudonym"] = pseudonym_rows.get(span["text"].lower().strip())

    doc["spans"] = non_llm_spans
    return doc


async def _fetch_pseudonyms(spans: list) -> dict:
    from database import get_db
    db = await get_db()
    result = {}
    for s in spans:
        if s.get("action_mode") != "anonymize":
            continue
        norm_text = s["text"].lower().strip()
        cursor = await db.execute(
            "SELECT pseudonym FROM pseudonym_map WHERE entity_text_normalized = ?",
            (norm_text,),
        )
        row = await cursor.fetchone()
        if row:
            result[norm_text] = row["pseudonym"]
    return result


async def transition_state(doc_id: str, new_state: str):
    """Transition document state with validation."""
    doc = await document_dal.get_document_by_id(doc_id)
    if not doc:
        return None, "Document not found"

    valid_transitions = {
        "pending": ["in_review"],
        "in_review": ["pending", "completed"],
        "completed": ["in_review"],
    }

    current = doc["state"]
    if new_state not in valid_transitions.get(current, []):
        return None, f"Invalid transition from '{current}' to '{new_state}'"

    # If transitioning to completed, verify all spans are decided
    if new_state == "completed":
        all_decided = await span_dal.check_all_spans_decided(doc_id)
        if not all_decided:
            return None, "Cannot complete: not all spans have been decided"

    await document_dal.update_document_state(doc_id, new_state)
    return await document_dal.get_document_by_id(doc_id), None


async def get_batch_progress():
    """Get batch progress stats including entity resolution metrics."""
    counts = await document_dal.count_by_state()
    total = await document_dal.get_total_count()
    completed = counts.get("completed", 0)
    pct = (completed / total * 100) if total > 0 else 0
    entity_stats = await entity_queue_dal.get_entity_stats()
    return {
        "total": total,
        "pending": counts.get("pending", 0),
        "in_review": counts.get("in_review", 0),
        "completed": completed,
        "completion_pct": round(pct, 1),
        **entity_stats,
    }
