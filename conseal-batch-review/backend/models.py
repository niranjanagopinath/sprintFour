"""
Pydantic schemas for request/response validation.
"""

from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List


# ── Span ──────────────────────────────────────────────────────────────

class SpanOut(BaseModel):
    id: str
    document_id: str
    text: str
    char_start: int
    char_end: int
    type: str
    confidence: Optional[float] = None
    tier: str
    source: str = "synthetic"
    reasoning: Optional[str] = None
    status: str
    action_mode: Optional[str] = None
    decided_via: Optional[str] = None
    source_span_id: Optional[str] = None


class ManualSpanIn(BaseModel):
    document_id: str
    text: str
    char_start: int
    char_end: int
    type: str = "other"
    action_mode: Optional[str] = "redact"  # redact | anonymize


# ── Decision ──────────────────────────────────────────────────────────

class DecisionIn(BaseModel):
    action: str  # confirm | reject
    action_mode: Optional[str] = None  # redact | anonymize
    decided_via: str = "manual"  # manual | propagated | cluster | spot_check


class DecisionOut(BaseModel):
    id: str
    span_id: str
    document_id: str
    action: str
    action_mode: Optional[str] = None
    decided_via: str
    confidence_at_decision: Optional[float] = None
    timestamp: str


# ── Document ──────────────────────────────────────────────────────────

class DocumentListItem(BaseModel):
    id: str
    title: str
    template_id: Optional[str] = None
    state: str
    source_type: str = "synthetic"
    file_type: str = "text"
    ocr_used: bool = False
    span_count: int = 0
    decided_count: int = 0
    created_at: str
    updated_at: str


class DocumentOut(BaseModel):
    id: str
    title: str
    raw_text: str
    template_id: Optional[str] = None
    state: str
    source_type: str = "synthetic"
    file_type: str = "text"
    ocr_used: bool = False
    ocr_confidence: Optional[float] = None
    batch_id: Optional[str] = None
    created_at: str
    updated_at: str
    spans: List[SpanOut] = []


class StateTransitionIn(BaseModel):
    state: str  # pending | in_review | completed


# ── Batch ─────────────────────────────────────────────────────────────

class BatchProgress(BaseModel):
    total: int
    pending: int
    in_review: int
    completed: int
    completion_pct: float
    total_entities: int = 0
    resolved_entities: int = 0
    pending_entities: int = 0
    propagated_decisions: int = 0
    manual_decisions: int = 0


# ── Entity Queue ──────────────────────────────────────────────────────

class EntityQueueItem(BaseModel):
    entity_text: str
    entity_type: str
    occurrence_count: int
    total_docs: int
    undecided_span_count: int
    first_doc_id: Optional[str] = None
    status: str  # undecided | partially_decided
    snippet: str
    note: Optional[str] = None


class ResolveEntityRequest(BaseModel):
    entity_text: str
    entity_type: str
    action: str           # confirm | reject
    action_mode: Optional[str] = None  # redact | anonymize


class SpotCheckAbortRequest(BaseModel):
    entity_text: str
    entity_type: str
    reason: str = "User rejected spot-check sample"


# ── Propagation ───────────────────────────────────────────────────────

class PropagationMatch(BaseModel):
    span_id: str
    document_id: str
    document_title: str
    text: str
    char_start: int
    char_end: int
    status: str


class PropagateRequest(BaseModel):
    source_span_id: str
    action: str  # confirm | reject
    action_mode: Optional[str] = None
    target_span_ids: List[str]
    decided_via: str = "propagated"


class SpotCheckResult(BaseModel):
    applied_span_ids: List[str]
    spot_check_span_ids: List[str]


# ── Cluster ───────────────────────────────────────────────────────────

class ClusterInfo(BaseModel):
    template_id: str
    document_count: int
    documents: List[DocumentListItem]


class ClusterApplyRequest(BaseModel):
    source_document_id: str
    source_span_id: str
    action: str  # confirm | reject
    action_mode: Optional[str] = None
    target_document_ids: List[str]
    decided_via: str = "cluster"


# ── Category Stats ───────────────────────────────────────────────────

class CategoryStatOut(BaseModel):
    type: str
    reject_count: int
    confirm_count: int
    current_priority_weight: float


# ── Audit ─────────────────────────────────────────────────────────────

class AuditQuery(BaseModel):
    document_id: Optional[str] = None
    type: Optional[str] = None
    decided_via: Optional[str] = None
    limit: int = 100
    offset: int = 0