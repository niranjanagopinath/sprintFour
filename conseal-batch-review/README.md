# Conseal Batch Review

A PII redaction review tool for paralegals processing batch case documents. Built as a hackathon prototype prioritizing correct core logic and clean architecture.

**Persona:** Maya, a paralegal processing 150–200 case documents under time pressure.

---

## Quick Start

### 1. Generate Synthetic Data

```bash
cd conseal-batch-review
python scripts/generate_data.py
```

This seeds the SQLite database (`backend/conseal.db`) with 150 documents and writes `generation_manifest.json`.

Optional parameters:
```bash
python scripts/generate_data.py \
  --doc-count 150 \
  --entity-overlap-rate 0.2 \
  --noise-rate 0.15 \
  --unanticipated-rate 0.1
```

### 2. System Dependencies

Before running the backend, ensure you have the following system dependencies installed:

**Tesseract OCR (Required for raster PDFs):**
- **Windows:** Download and install from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki). Ensure `tesseract` is added to your system PATH.
- **macOS:** `brew install tesseract`
- **Linux:** `sudo apt-get install tesseract-ocr`

**GLiNER & Presidio (Required for Tier 1 structured detection):**
Ensure your Python environment has a C++ compiler available if building dependencies from source. The requirements include `gliner` (which depends on PyTorch/Transformers) and `presidio-analyzer`. If these fail to install, the backend uses a fallback regex detection.

### 3. Start the Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs available at http://localhost:8000/docs

### 3. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Vite + Vanilla JS)                               │
│  ┌──────────┐  ┌─────────────────┐  ┌──────────┐          │
│  │Dashboard │  │ Document Review  │  │Audit Log │          │
│  └────┬─────┘  └───────┬─────────┘  └────┬─────┘          │
│       └────────────────┼──────────────────┘                │
│                        │ REST/JSON                          │
├────────────────────────┼────────────────────────────────────┤
│  Backend (FastAPI)     │                                    │
│  ┌─────────┐  ┌───────┴──────┐  ┌────────────┐            │
│  │ Routes  │→ │  Services    │→ │    DAL      │            │
│  └─────────┘  └──────────────┘  └──────┬─────┘            │
│                                        │                    │
│                                  ┌─────┴─────┐             │
│                                  │  SQLite    │             │
│                                  └───────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### Backend Structure

| Layer | Purpose |
|-------|---------|
| `routes/` | HTTP endpoint definitions, request validation |
| `services/` | Business logic — state machine, propagation, recalibration |
| `dal/` | Data access layer — SQL queries, no business logic |
| `config.py` | Feature flags (`USE_LIVE_LLM_TIER`), DB path |
| `database.py` | Schema init, connection management |
| `models.py` | Pydantic request/response schemas |

### Data Model

- **Document** — id, title, raw_text, template_id, state (pending→in_review→completed)
- **Span** — a PII candidate at any tier, with status (undecided→confirmed/rejected)
- **Decision** — append-only audit log entry per span decision
- **CategoryStat** — session-scoped reject/confirm counts for recalibration

---

## Tiered Detection Model

### Tier 1: Structured Detection (Pre-computed)
Standard PII types (name, SSN, phone, address, case number) detected by the synthetic data generator with character offsets. Includes deliberate noise (false positives and omissions per `noise_rate`).

### Tier 2: LLM Safety Net (Stubbed)
For ~10% of documents, the LLM tier identifies non-standard sensitive information (medical conditions, bank accounts, identifying remarks) that structured detection misses. **Currently stubbed** — returns pre-generated fixture data.

### Tier 3: Manual Flagging
Maya can select any text and press `F` to flag it as sensitive. Creates a confirmed span immediately.

### Switching to Live LLM Tier 2

1. Set environment variable: `USE_LIVE_LLM_TIER=true`
2. Set environment variable: `ANTHROPIC_API_KEY=your-key-here`
3. Replace the `_call_live_llm()` function in `backend/services/llm_tier_service.py` with the real Anthropic API call (the prompt template is documented in comments)
4. Restart the backend

**No other code changes required.** The function signature, data model, UI, and routing all remain the same. Note that `USE_LOCAL_LLM_TIER` flag and `OLLAMA_URL` are available for configuring local models like Gemma E4B in `config.py`.

---

## Four Batch Acceleration Mechanisms

### 1. Entity Propagation
When Maya confirms/rejects a span, the system finds case-insensitive exact text matches in other non-completed documents. She can Apply to All, Review Each, or Dismiss.

### 2. Structural Clustering
Documents sharing a `template_id` form a cluster. After deciding a span, Maya can apply the same decision to similar spans (same type at similar character positions) across all cluster members.

### 3. Confidence Recalibration
Each rejection of a structured/LLM span updates `CategoryStat`. Types Maya keeps rejecting are deprioritized in the display order:

```
weight = 1.0 / (1.0 + reject_count / (reject_count + confirm_count + 1))
```

### 4. Spot-Check Guard
When Apply to All affects >10 spans, the system randomly samples ~1 in 15 for manual confirmation before bulk-applying the rest.

---

## Keyboard Shortcuts (Document Review)

| Key | Action |
|-----|--------|
| `C` | Confirm selected span |
| `R` | Reject selected span |
| `F` | Flag selected text as sensitive |
| `N` | Jump to next undecided span |

---

## Known Simplifications

| Area | Simplification | Production Improvement |
|------|---------------|----------------------|
| Entity matching | Case-insensitive exact match | Fuzzy matching (edit distance, phonetic) |
| Clustering | Pre-computed `template_id` | Runtime text similarity (TF-IDF, embeddings) |
| Recalibration | Session-scoped, resets on restart | Persistent per-user calibration |
| Propagation scope | Only searches pending + in_review docs | Option to propagate to completed docs |
| Spot-check | Simple random sampling | Stratified sampling by type/confidence |
| Auth | None | Multi-user with role-based access |

---

## What Was Deliberately Left Out

- **Authentication / multi-user** — Single-user prototype per hackathon scope
- **Live PII detector (Tier 1)** — Stays mocked; real detection would use NER models
- **Live LLM calls (Tier 2)** — Stubbed but fully wired; one config flag + one function swap to enable
- **Heavy visual design** — Functional dark theme with clear type/tier color coding; no animations or theming system
- **Undo/redo** — Decisions are append-only; reversal would require a new Decision entry

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/documents?state=&limit=&offset=` | List documents |
| GET | `/documents/:id` | Full document with spans |
| POST | `/documents/:id/state` | Transition state |
| GET | `/documents/:id/llm-review` | Tier 2 (LLM) spans |
| POST | `/spans/:id/decision` | Confirm/reject a span |
| GET | `/spans/:id/propagation` | Find matching spans |
| POST | `/spans/propagate` | Apply decision to multiple spans |
| POST | `/spans/manual` | Create manual flag |
| POST | `/spans/spot-check/:id` | Spot-check decision |
| GET | `/batch/progress` | Batch progress stats |
| GET | `/batch/clusters/:doc_id` | Cluster info |
| GET | `/batch/clusters/:doc_id/spans/:span_id/matches` | Cluster span matches |
| POST | `/batch/cluster-apply` | Apply cluster pattern |
| GET | `/batch/category-stats` | Recalibration stats |
| GET | `/audit/log` | Filterable decision log |
