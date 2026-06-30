from typing import List
"""
Batch routes — progress, clustering.
"""

from fastapi import APIRouter, HTTPException, Response
from models import BatchProgress, ClusterInfo, ClusterApplyRequest, SpotCheckResult, CategoryStatOut
from services import document_service, cluster_service, span_service, recalibration_service, export_service

router = APIRouter(prefix="/batch", tags=["batch"])


@router.get("/progress", response_model=BatchProgress)
async def get_progress():
    """Get batch progress stats."""
    return await document_service.get_batch_progress()


@router.get("/pipeline-status")
async def pipeline_status():
    """
    Per-document pipeline timing for the live status bar.
    Returns all docs with their detection phase and elapsed time.
    """
    from database import get_db
    db = await get_db()
    cursor = await db.execute("""
        SELECT
            id, title, state, span_count,
            created_at, detection_started_at, detection_completed_at,
            CASE
                WHEN detection_completed_at IS NOT NULL THEN 'ready'
                WHEN detection_started_at  IS NOT NULL THEN 'detecting'
                ELSE 'queued'
            END AS pipeline_phase,
            CASE
                WHEN detection_completed_at IS NOT NULL THEN
                    ROUND((julianday(detection_completed_at) - julianday(created_at)) * 86400, 1)
                WHEN detection_started_at IS NOT NULL THEN
                    ROUND((julianday('now') - julianday(created_at)) * 86400, 1)
                ELSE NULL
            END AS elapsed_s
        FROM documents
        ORDER BY created_at DESC
        LIMIT 200
    """)
    rows = await cursor.fetchall()
    docs = [dict(r) for r in rows]

    total   = len(docs)
    ready   = sum(1 for d in docs if d["pipeline_phase"] == "ready")
    detect  = sum(1 for d in docs if d["pipeline_phase"] == "detecting")
    queued  = sum(1 for d in docs if d["pipeline_phase"] == "queued")
    avg_s   = (
        sum(d["elapsed_s"] for d in docs if d["elapsed_s"] is not None and d["pipeline_phase"] == "ready")
        / max(ready, 1)
    )
    return {
        "total": total, "ready": ready, "detecting": detect, "queued": queued,
        "avg_detection_s": round(avg_s, 1),
        "docs": docs,
    }


@router.get("/clusters/{doc_id}")
async def get_cluster(doc_id: str):
    """Get the template cluster for a document."""
    cluster = await cluster_service.get_cluster_for_document(doc_id)
    if cluster is None:
        raise HTTPException(404, "Document not found")
    return cluster


@router.get("/clusters/{doc_id}/spans/{span_id}/matches")
async def get_cluster_matches(doc_id: str, span_id: str):
    """Find matching spans in cluster members at similar positions."""
    matches = await cluster_service.find_cluster_matching_spans(doc_id, span_id)
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


@router.post("/cluster-apply", response_model=SpotCheckResult)
async def apply_cluster_pattern(body: ClusterApplyRequest):
    """
    Apply a redaction pattern to cluster members.
    Uses the same propagation mechanism with decided_via='cluster'.
    """
    applied, spot_check = await span_service.propagate_decision(
        source_span_id=body.source_span_id,
        action=body.action,
        target_span_ids=body.target_document_ids,  # These are actually span IDs
        decided_via="cluster",
        action_mode=body.action_mode,
    )
    return {"applied_span_ids": applied, "spot_check_span_ids": spot_check}


@router.get("/category-stats", response_model=List[CategoryStatOut])
async def get_category_stats():
    """Get current category statistics for recalibration."""
    return await recalibration_service.get_all_category_stats()


@router.post("/auto-confirm")
async def auto_confirm_batch():
    """
    Automatically confirms all undecided system spans as redact across the batch.
    """
    count = await span_service.auto_confirm_all()
    return {"message": f"Successfully auto-confirmed {count} spans across the batch.", "count": count}


@router.post("/generate-sample")
async def generate_sample_batch(count: int = 20):
    """
    Generate synthetic Indian legal documents and trigger detection on each.
    Returns immediately; detection runs in the background.
    """
    import asyncio
    import sqlite3
    import uuid as _uuid
    import os as _os
    from concurrent.futures import ThreadPoolExecutor
    from services.sample_generator import make_document
    from services.detection_service import run_tier1_detection

    cap = min(count, 200)
    batch_id = f"batch-syn-{_uuid.uuid4().hex[:6]}"

    docs = []
    for i in range(cap):
        title, text = make_document(i)
        doc_id = f"doc-{_uuid.uuid4().hex[:8]}"
        docs.append((doc_id, title, text))

    # Insert via sync sqlite3 in a thread so we don't block / fight aiosqlite
    db_path = _os.path.join(_os.path.dirname(__file__), "..", "conseal.db")

    def _sync_insert():
        conn = sqlite3.connect(db_path, timeout=30)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            for doc_id, title, text in docs:
                conn.execute(
                    """INSERT OR IGNORE INTO documents
                       (id, title, raw_text, state, source_type, file_type, ocr_used, batch_id)
                       VALUES (?, ?, ?, 'pending', 'synthetic', 'text', 0, ?)""",
                    (doc_id, title, text, batch_id),
                )
            conn.commit()
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as ex:
        await loop.run_in_executor(ex, _sync_insert)

    # Fire detection in background (outside any semaphore logic here)
    for doc_id, text in [(d, t) for d, _, t in docs]:
        asyncio.create_task(run_tier1_detection(doc_id, text))

    return {"batch_id": batch_id, "count": len(docs), "doc_ids": [d for d, _, _ in docs]}


@router.get("/export")
async def export_batch_zip():
    """
    Export all documents in the batch as a single ZIP file.
    """
    zip_bytes = await export_service.export_all_documents()
    if not zip_bytes:
        raise HTTPException(404, "No documents available for export")
        
    return Response(
        content=zip_bytes, 
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=conseal_batch_export.zip"}
    )
