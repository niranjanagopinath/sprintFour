"""
Document routes.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from models import DocumentOut, DocumentListItem, StateTransitionIn, BatchProgress, SpanOut
from services import document_service
import asyncio
import os
import sys
import subprocess
from database import close_db

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/load-sample")
async def load_sample_batch():
    """Run the synthetic data generator to load a sample batch."""
    # Close active DB connection to allow file replacement on Windows
    await close_db()
    
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "generate_data.py"))
    
    def run_script():
        subprocess.run([sys.executable, script_path], check=True)
        
    try:
        await asyncio.to_thread(run_script)
        return {"message": "Sample batch loaded successfully"}
    except Exception as e:
        raise HTTPException(500, f"Failed to load sample batch: {str(e)}")

@router.get("", response_model=List[DocumentListItem])
async def list_documents(
    state: Optional[str] = Query(None, description="Filter by state: pending|in_review|completed"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List documents with optional state filter, pagination, sorted by priority."""
    if state and state not in ("pending", "in_review", "completed"):
        raise HTTPException(400, f"Invalid state: {state}")
    docs = await document_service.list_documents(state=state, limit=limit, offset=offset)
    return docs


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: str):
    """Get a document with all its spans (priority-sorted)."""
    doc = await document_service.get_document_with_spans(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.post("/{doc_id}/state")
async def transition_state(doc_id: str, body: StateTransitionIn):
    """Transition a document's state."""
    doc, error = await document_service.transition_state(doc_id, body.state)
    if error:
        raise HTTPException(400, error)
    return doc


@router.get("/{doc_id}/llm-review", response_model=List[SpanOut])
async def get_llm_review(doc_id: str):
    """
    Get Tier 2 (LLM) spans for a document.
    When USE_LOCAL_LLM_TIER=false, returns pre-generated fixture data.
    When true, calls the local LLM API.
    """
    from services.llm_tier_service import get_llm_tier_spans
    spans = await get_llm_tier_spans(doc_id)
    return spans


@router.get("/{doc_id}/export")
async def export_document_route(doc_id: str):
    """
    Export the document with confirmed redactions applied.
    """
    from services.export_service import export_document
    result = await export_document(doc_id)
    if result is None:
        raise HTTPException(404, "Document not found")
    return {"text": result}
