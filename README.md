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
| Fuzzy entity matching | Exact match is fast and predictable; fuzzy match risks false positives in legal redaction |
| Embedding-based clustering | `template_id` from the synthetic generator already proves batch-apply, no ML infra needed |
| Visual/bounding-box PDF redaction | Text-level export proves the decision pipeline; visual markup is a separate product surface |
| Undo/redo | Append-only `Decision` records already satisfy audit needs; reversal = new decision |
| Polished UI/design system | Time went to throughput (queue, propagation, detection) — where Maya's minutes are actually saved |
| Unbounded LLM concurrency | Capped Tier 2 at 2 concurrent calls so it can't starve Tier 1 |

**Through-line:** optimize for reviewer leverage at batch scale, not feature completeness.

## Performance — 200-Document Batch (measured)

| Metric | Value |
|---|---|
| Documents ingested | 200 |
| Detection threads | 5 (dedicated thread pool, true parallelism) |
| LLM concurrency | 2 (Tier 2 runs outside the detection semaphore) |
| Wall-clock to "200 ready" | ~56–62 s |
| PII spans detected | 2,070 |
| Throughput | ~194 docs/min |
| First-wave completion | 198/200 docs done in 8 s once models were warm |

~5 min one-at-a-time loop → ~1 min concurrent pipeline.

**Bugs found and fixed to get a clean concurrent run:**
- DB `CHECK` constraint silently rejected `source='regex'` inserts, so no doc ever reached "ready" — widened constraint to include `regex` and `ollama`.
- Thundering-herd model load (5 cold threads loading GLiNER/Presidio at once) — fixed with a double-checked `threading.Lock` so each model loads exactly once.

**Known caveat:** Presidio's shared spaCy `nlp` object isn't formally thread-safe across 5 threads. Results were correct and uncorrupted across test runs, but a small pool of Presidio engine instances (vs. one shared singleton) would be the more robust long-term fix.
