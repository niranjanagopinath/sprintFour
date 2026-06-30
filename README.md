# Conseal Batch Review

**Built for:** A paralegal reviewing 150–200 case documents for PII under time pressure.

## Detection Process Flow (per thread)

| Stage | What happens |
|---|---|
| 1. Upload | Document enters the queue; `asyncio.Semaphore(5)` admits up to 5 documents into detection at once |
| 2. Thread acquired | A dedicated `ThreadPoolExecutor(max_workers=5)` picks up the document — model inference runs in real OS threads (true parallelism, since inference releases the GIL), kept separate from the shared default executor |
| 3. Text extraction | PyMuPDF attempts native text extraction; if the page has no extractable text layer, it falls back to Tesseract OCR |
| 4. Tier 1 — structured PII | Presidio + GLiNER run inside the thread (regex as fallback) against the extracted text; first thread to need a model loads it once under a `threading.Lock`, the other 4 threads reuse the loaded instance instead of each loading their own copy |
| 5. Tier 2 — contextual PII | Once Tier 1 finishes, the document is handed to Ollama (`gemma4:e4b`) *outside* the detection semaphore, capped separately at 2 concurrent calls, so it never blocks a Tier 1 thread slot |
| 6. Thread released | As soon as Tier 1 + Tier 2 complete, the thread's slot frees up and the next queued document is admitted |
| 7. Ready | `detection_completed_at` is stamped; the document appears in the pipeline status bar and Review Queue as "ready" |

This is what produced the measured result: 5 threads kept saturated end-to-end → 198/200 docs cleared in the first 8 seconds once models were warm, full 200-doc batch ready in ~56–62s.

## What I Built

| Feature | Detail |
|---|---|
| Batch-first review, not file-by-file | The Review Queue groups PII spans by `(text, type)` across all documents, sorted by frequency — confirm/reject once, propagate the decision everywhere it matches |
| Tier 1 detection | Presidio + GLiNER (regex fallback) for structured PII: names, IDs, phones, addresses |
| Tier 2 detection | Ollama (`gemma4:e4b`) for context-sensitive PII pattern matchers miss |
| Tier 3 detection | Manual flagging by the reviewer |
| OCR ingestion pipeline | PDFs are extracted with PyMuPDF first; if a page is scanned/image-only with no extractable text layer, it automatically falls back to Tesseract OCR — so scanned case files get the same detection coverage as native PDFs |
| Safety rails | Bulk actions over 10 spans trigger a spot-check (~1 in 15 sampled before applying); every decision is written to an append-only audit log |
| Live pipeline status bar | Shows per-document detection progress in real time |
| Batch acceleration extras | Template clustering, confidence recalibration, ZIP export with redaction or anonymization applied |
| Layered architecture | `routes → services → dal` — detection, review logic, and persistence stay separable and testable |
| Result (200-doc batch, measured) | 5 parallel detection threads + 2 concurrent LLM calls → 2,070 spans detected in ~60s (~194 docs/min), vs. ~5 min one-at-a-time |

## What I Chose Not to Build (and Why)

| Skipped | Why |
|---|---|
| Custom PII detector | Presidio/GLiNER already handle the structured cases — the real problem was never detection accuracy, it was what a reviewer does with imperfect detection at scale |
| Auth / multi-user support | Single-reviewer prototype; that effort was better spent elsewhere |
| Transformer OCR model | Tesseract has a lighter footprint, sufficient accuracy, and lower dependency risk on a tight build day |
| Always-on local LLM tier | Wired end-to-end but sits behind a feature flag with a deterministic fixture fallback, so a hardware issue on demo day can't take down the core workflow |
| Redacted-PDF visual re-rendering | Pipeline produces redacted/anonymized text output; a clear next step, not something worth half-finishing now |
| Automatic application of decisions | Propagation, clustering, and anonymization all require explicit reviewer approval before touching a document, regardless of confidence — the reviewer is accountable for what goes out under her name, and a tool that quietly trusts itself on her behalf is a liability, not a feature |
