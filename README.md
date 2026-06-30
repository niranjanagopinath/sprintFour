# Conseal Batch Review

**Built for:** Maya, a paralegal reviewing 150–200 case documents for PII under time pressure.

## What I Built

- **Batch-first review, not file-by-file.** The Review Queue groups PII spans by `(text, type)` across all documents, sorted by frequency — confirm/reject once, propagate the decision everywhere it matches.
- **Three-tier detection on upload:**
  - Tier 1 — Presidio + GLiNER (regex fallback) for structured PII: names, IDs, phones, addresses
  - Tier 2 — Ollama (`gemma4:e4b`) for context-sensitive PII pattern matchers miss
  - Tier 3 — manual flagging by the reviewer
- **OCR ingestion pipeline.** PDFs are extracted with PyMuPDF first; if a page is scanned/image-only with no extractable text layer, it automatically falls back to Tesseract OCR — so scanned case files get the same detection coverage as native PDFs.
- **Safety rails:** bulk actions over 10 spans trigger a spot-check (~1 in 15 sampled before applying); every decision is written to an append-only audit log.
- **Live pipeline status bar** showing per-document detection progress in real time.
- **Batch acceleration extras:** template clustering, confidence recalibration, ZIP export with redaction or anonymization applied.
- **Layered architecture:** `routes → services → dal` — detection, review logic, and persistence stay separable and testable.


## What I Chose Not to Build (and Why)

| Skipped | Why |
|---|---|
| Custom PII detector | Presidio/GLiNER already handle the structured cases — the real problem was never detection accuracy, it was what a reviewer does with imperfect detection at scale |
| Auth / multi-user support | Single-reviewer prototype; that effort was better spent elsewhere |
| Transformer OCR model | Tesseract has a lighter footprint, sufficient accuracy, and lower dependency risk on a tight build day |
| Always-on local LLM tier | Wired end-to-end but sits behind a feature flag with a deterministic fixture fallback, so a hardware issue on demo day can't take down the core workflow |
| Redacted-PDF visual re-rendering | Pipeline produces redacted/anonymized text output; a clear next step, not something worth half-finishing now |
| Automatic application of decisions | Propagation, clustering, and anonymization all require explicit reviewer approval before touching a document, regardless of confidence — the reviewer is accountable for what goes out under her name, and a tool that quietly trusts itself on her behalf is a liability, not a feature |
~5 min one-at-a-time loop → ~1 min concurrent pipeline.

**Bugs found and fixed to get a clean concurrent run:**
- DB `CHECK` constraint silently rejected `source='regex'` inserts, so no doc ever reached "ready" — widened constraint to include `regex` and `ollama`.
- Thundering-herd model load (5 cold threads loading GLiNER/Presidio at once) — fixed with a double-checked `threading.Lock` so each model loads exactly once.

**Known caveat:** Presidio's shared spaCy `nlp` object isn't formally thread-safe across 5 threads. Results were correct and uncorrupted across test runs, but a small pool of Presidio engine instances (vs. one shared singleton) would be the more robust long-term fix.
