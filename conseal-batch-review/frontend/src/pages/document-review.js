/**
 * Document Review Page
 *
 * Core review screen: inline highlighted spans, confirm/reject decisions,
 * manual flagging (select + F), propagation prompts, cluster panel,
 * LLM tier section, transparency tooltips, spot-check guard.
 */

import {
  fetchDocument, fetchLlmReview, makeDecision, createManualSpan,
  propagateDecision, fetchCluster, fetchClusterMatches,
  transitionState, spotCheckDecision, exportDocument,
} from '../api.js';
import { showToast } from '../main.js';

let _keyHandler = null;
let _selectedSpanId = null;
let _docData = null;
let _llmSpans = [];
let _clusterInfo = null;

export function cleanupDocumentReview() {
  if (_keyHandler) {
    document.removeEventListener('keydown', _keyHandler);
    _keyHandler = null;
  }
  _selectedSpanId = null;
  _docData = null;
  _llmSpans = [];
  _clusterInfo = null;
}

export async function renderDocumentReview(container, docId) {
  // Load document data, LLM spans, and cluster info in parallel
  const [doc, llmSpans, cluster] = await Promise.all([
    fetchDocument(docId),
    fetchLlmReview(docId).catch(() => []),
    fetchCluster(docId).catch(() => null),
  ]);

  _docData = doc;
  _llmSpans = llmSpans;
  _clusterInfo = cluster;

  // Auto-transition to in_review if pending
  if (doc.state === 'pending') {
    try { await transitionState(docId, 'in_review'); doc.state = 'in_review'; } catch {}
  }

  container.innerHTML = `
    <a href="#/queue" class="back-link">← Review Queue</a>
    <div class="doc-review">
      <div class="doc-review-main">
        <div class="doc-review-header">
          <div>
            <div class="doc-review-title">${escHtml(doc.title)}</div>
            <div style="display:flex;align-items:center;gap:0.5rem;margin-top:0.25rem;">
              <span class="state-badge ${doc.state}">${doc.state.replace('_', ' ')}</span>
              <span style="font-size:0.72rem;color:var(--text-muted);">${(doc.template_id || 'uploaded').replace('_', ' ')}</span>
            </div>
          </div>
          <div class="doc-review-actions">
            ${_clusterInfo && _clusterInfo.document_count > 0 ? `
              <span class="cluster-badge" id="cluster-toggle">${_clusterInfo.document_count} related</span>
            ` : ''}
            <button class="btn btn-sm btn-secondary" id="export-doc-btn">Export</button>
            <button class="btn btn-sm ${doc.state === 'completed' ? 'btn-secondary' : 'btn-primary'}" id="complete-doc-btn"
              ${doc.state === 'completed' ? 'disabled' : ''}>
              ${doc.state === 'completed' ? 'Completed' : 'Mark Complete'}
            </button>
          </div>
        </div>
        <div class="doc-text-container" id="doc-text"></div>
        <div class="llm-section" id="llm-section-card">
          <div class="llm-section-header" id="llm-toggle">
            <span class="chevron">▶</span>
            Needs Deeper Review
            <span style="margin-left:auto;font-size:0.72rem;color:var(--text-muted);">
              ${llmSpans.length} item${llmSpans.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div class="llm-section-body" id="llm-body"></div>
        </div>
      </div>

      <div class="doc-review-sidebar">
        <div class="sidebar-card">
          <div class="sidebar-card-header">
            <span>Selected Span</span>
            <span id="span-progress" style="font-weight:400;text-transform:none;letter-spacing:0;font-size:0.72rem;color:var(--text-secondary);"></span>
          </div>
          <div class="sidebar-card-body">
            <div class="decision-panel" id="decision-panel">
              <div class="decision-span-text" id="decision-text"></div>
              <div class="decision-meta" id="decision-meta"></div>
              <div class="decision-btns" id="decision-btns">
                <button class="btn btn-sm btn-confirm" id="btn-confirm-redact">Redact <span class="kbd">C</span></button>
                <button class="btn btn-sm btn-confirm" id="btn-confirm-anonymize">Anonymize <span class="kbd">A</span></button>
                <button class="btn btn-sm btn-reject" id="btn-reject">Reject <span class="kbd">R</span></button>
              </div>
            </div>
            <div id="no-selection" style="font-size:0.78rem;color:var(--text-muted);padding:0.25rem 0;">
              Click a highlighted word to review it
            </div>
          </div>
        </div>

        <div class="propagation-prompt" id="propagation-prompt">
          <div class="propagation-title" id="prop-title"></div>
          <div class="propagation-text" id="prop-text"></div>
          <div class="propagation-actions">
            <button class="btn btn-sm btn-primary" id="prop-apply-all">Apply to All</button>
            <button class="btn btn-sm btn-secondary" id="prop-review-each">Review Each</button>
            <button class="btn btn-sm btn-ghost" id="prop-dismiss">Dismiss</button>
          </div>
        </div>

        <div class="sidebar-card">
          <div class="sidebar-card-header">All Spans</div>
          <div class="sidebar-card-body" style="padding:0.4rem;">
            <div class="span-list" id="span-list"></div>
          </div>
        </div>

        <div class="sidebar-card">
          <div class="sidebar-card-header">Shortcuts</div>
          <div class="sidebar-card-body">
            <div class="shortcuts-legend">
              <span><span class="kbd">C</span> Redact</span>
              <span><span class="kbd">A</span> Anonymize</span>
              <span><span class="kbd">R</span> Reject</span>
              <span><span class="kbd">N</span> Next</span>
            </div>
            <div class="manual-flag-hint">Select any text to manually flag it</div>
          </div>
        </div>
      </div>
    </div>

    <div class="spot-check-overlay" id="spot-check-overlay">
      <div class="spot-check-modal">
        <div class="spot-check-header">Spot Check</div>
        <div class="spot-check-progress" id="spot-check-progress"></div>
        <div class="spot-check-span" id="spot-check-span"></div>
        <div class="spot-check-actions">
          <button class="btn btn-confirm" id="spot-check-confirm">Confirm <span class="kbd">C</span></button>
          <button class="btn btn-reject" id="spot-check-reject">Reject <span class="kbd">R</span></button>
        </div>
      </div>
    </div>

    <div class="review-each-overlay" id="review-each-overlay">
      <div class="review-each-modal">
        <div class="spot-check-header" id="review-each-header">Review Propagation</div>
        <div class="spot-check-progress" id="review-each-progress"></div>
        <div class="review-each-doc-title" id="review-each-doc"></div>
        <div class="spot-check-span" id="review-each-span"></div>
        <div class="spot-check-actions">
          <button class="btn btn-confirm" id="review-each-confirm">Apply <span class="kbd">C</span></button>
          <button class="btn btn-reject" id="review-each-skip">Skip <span class="kbd">R</span></button>
        </div>
      </div>
    </div>
  `;

  // ── Render document text with inline spans ────────────────────

  renderDocumentText(doc);
  renderSpanList(doc);
  renderLlmSection(llmSpans, doc);
  updateSpanProgress(doc);
  _attachSelectionListener(doc);

  // ── Event: LLM section toggle ────────────────────────────────

  document.getElementById('llm-toggle').addEventListener('click', (e) => {
    const header = e.currentTarget;
    const body = document.getElementById('llm-body');
    header.classList.toggle('expanded');
    body.classList.toggle('expanded');
  });

  // ── Event: Complete document ──────────────────────────────────

  document.getElementById('complete-doc-btn').addEventListener('click', async () => {
    try {
      await transitionState(docId, 'completed');
      showToast('Document marked as completed', 'success');
      doc.state = 'completed';
      window.location.hash = '#/';
    } catch (err) {
      showToast(`Cannot complete: ${err.message}`, 'error');
    }
  });

  // ── Event: Cluster toggle ────────────────────────────────────

  const clusterToggle = document.getElementById('cluster-toggle');
  if (clusterToggle) {
    clusterToggle.addEventListener('click', () => {
      showToast(`Cluster: ${_clusterInfo.document_count} documents share template "${(doc.template_id || 'uploaded').replace('_', ' ')}"`, 'info');
    });
  }

  // ── Event: Export document ────────────────────────────────────

  document.getElementById('export-doc-btn').addEventListener('click', async () => {
    try {
      const data = await exportDocument(docId);
      
      // Create a blob and trigger download
      const blob = new Blob([data.text], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${doc.title}_redacted.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      showToast('Document exported successfully', 'success');
    } catch (err) {
      showToast(`Export failed: ${err.message}`, 'error');
    }
  });

  // ── Keyboard handler ─────────────────────────────────────────

  _keyHandler = async (e) => {
    // Don't capture if typing in input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

    const key = e.key.toUpperCase();

    // F — Manual flag
    if (key === 'F') {
      e.preventDefault();
      await handleManualFlag(doc);
      return;
    }

    // N — Next undecided span
    if (key === 'N') {
      e.preventDefault();
      selectNextUndecided(doc);
      return;
    }

    // Spot-check active?
    const spotCheckOverlay = document.getElementById('spot-check-overlay');
    if (spotCheckOverlay?.classList.contains('visible')) {
      if (key === 'C') document.getElementById('spot-check-confirm').click();
      if (key === 'R') document.getElementById('spot-check-reject').click();
      return;
    }

    // Review-each active?
    const reviewEachOverlay = document.getElementById('review-each-overlay');
    if (reviewEachOverlay?.classList.contains('visible')) {
      if (key === 'C') document.getElementById('review-each-confirm').click();
      if (key === 'R') document.getElementById('review-each-skip').click();
      return;
    }

    // C/R/A — Confirm(Redact)/Reject/Anonymize selected span
    if ((key === 'C' || key === 'R' || key === 'A') && _selectedSpanId) {
      e.preventDefault();
      const action = key === 'R' ? 'reject' : 'confirm';
      const actionMode = key === 'A' ? 'anonymize' : (key === 'C' ? 'redact' : null);
      await handleDecision(_selectedSpanId, action, actionMode, doc);
    }
  };
  document.addEventListener('keydown', _keyHandler);

  // ── Event: Confirm/Reject buttons ────────────────────────────

  document.getElementById('btn-confirm-redact').addEventListener('click', async () => {
    if (_selectedSpanId) await handleDecision(_selectedSpanId, 'confirm', 'redact', doc);
  });
  document.getElementById('btn-confirm-anonymize').addEventListener('click', async () => {
    if (_selectedSpanId) await handleDecision(_selectedSpanId, 'confirm', 'anonymize', doc);
  });
  document.getElementById('btn-reject').addEventListener('click', async () => {
    if (_selectedSpanId) await handleDecision(_selectedSpanId, 'reject', null, doc);
  });

  // ── Event: Propagation buttons ───────────────────────────────

  document.getElementById('prop-dismiss').addEventListener('click', () => {
    document.getElementById('propagation-prompt').classList.remove('visible');
  });
}


// ══════════════════════════════════════════════════════════════════
// Rendering
// ══════════════════════════════════════════════════════════════════

function renderDocumentText(doc) {
  const textEl = document.getElementById('doc-text');
  const raw = doc.raw_text;
  const spans = [...doc.spans].sort((a, b) => a.char_start - b.char_start);

  // Build HTML with non-overlapping spans
  let html = '';
  let pos = 0;

  // Remove overlapping spans (keep earlier start, or higher confidence)
  const nonOverlapping = [];
  for (const span of spans) {
    if (span.tier === 'llm') continue; // LLM spans shown separately
    const lastEnd = nonOverlapping.length > 0 ? nonOverlapping[nonOverlapping.length - 1].char_end : 0;
    if (span.char_start >= lastEnd) {
      nonOverlapping.push(span);
    }
  }

  for (const span of nonOverlapping) {
    // Text before this span
    if (span.char_start > pos) {
      html += escHtml(raw.slice(pos, span.char_start));
    }
    // The span itself
    const statusClass = span.status !== 'undecided' ? span.status : '';
    const tierClass = span.tier !== 'structured' ? `tier-${span.tier}` : '';
    const isAnonymized = span.status === 'confirmed' && span.action_mode === 'anonymize';
    const pseudonymLabel = isAnonymized && span.pseudonym
      ? `<span class="pseudonym-label">${escHtml(span.pseudonym)}</span>`
      : '';
    html += `<span class="pii-span ${statusClass} ${tierClass} ${isAnonymized ? 'anonymized' : ''}"
      data-span-id="${span.id}"
      data-type="${span.type}"
      data-status="${span.status}"
      data-tier="${span.tier}"
      data-confidence="${span.confidence ?? ''}"
      data-decided-via="${span.decided_via ?? ''}"
      data-source-span="${span.source_span_id ?? ''}"
      data-reasoning="${escAttr(span.reasoning ?? '')}"
      title=""
    >${escHtml(raw.slice(span.char_start, span.char_end))}${pseudonymLabel}</span>`;
    pos = span.char_end;
  }
  // Remaining text
  if (pos < raw.length) {
    html += escHtml(raw.slice(pos));
  }

  textEl.innerHTML = html;

  // Span click handlers
  textEl.querySelectorAll('.pii-span').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      selectSpan(el.dataset.spanId, doc);
    });

    // Tooltip on hover
    el.addEventListener('mouseenter', (e) => showTransparencyTooltip(e, el));
    el.addEventListener('mouseleave', hideTransparencyTooltip);
  });

  // Click outside to deselect
  textEl.addEventListener('click', (e) => {
    if (!e.target.closest('.pii-span')) {
      deselectSpan();
    }
  });
}

function renderSpanList(doc) {
  const listEl = document.getElementById('span-list');
  const spans = doc.spans.filter(s => s.tier !== 'llm');

  listEl.innerHTML = spans.map(span => `
    <div class="span-list-item" data-span-id="${span.id}">
      <div class="span-list-status ${span.status}"></div>
      <span class="type-badge ${span.type}" style="flex-shrink:0;">${span.type}</span>
      <div class="span-list-text">${escHtml(span.text)}</div>
    </div>
  `).join('');

  listEl.querySelectorAll('.span-list-item').forEach(el => {
    el.addEventListener('click', () => {
      selectSpan(el.dataset.spanId, doc);
      // Scroll to span in text
      const textSpan = document.querySelector(`.pii-span[data-span-id="${el.dataset.spanId}"]`);
      if (textSpan) textSpan.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });
}

function renderLlmSection(llmSpans, doc) {
  const body = document.getElementById('llm-body');
  if (!llmSpans.length) {
    document.getElementById('llm-section-card').style.display = 'none';
    return;
  }

  body.innerHTML = llmSpans.map(span => `
    <div class="llm-span-card" data-span-id="${span.id}">
      <div class="llm-span-label">AI Second-Pass — Low Confidence</div>
      <div class="llm-span-text">"${escHtml(span.text)}"</div>
      <div class="llm-span-reasoning">${escHtml(span.reasoning || 'No reasoning provided')}</div>
      <div style="display:flex; gap:0.5rem; align-items:center;">
        <span class="tier-badge llm">LLM</span>
        <span style="font-size:0.75rem; color:var(--text-muted);">
          Confidence: ${span.confidence ? (span.confidence * 100).toFixed(0) + '%' : '—'}
        </span>
        <span style="font-size:0.75rem; margin-left:auto;">
          Status: <span class="action-badge ${span.status === 'confirmed' ? 'confirm' : span.status === 'rejected' ? 'reject' : ''}">${span.status}</span>
        </span>
        ${span.status === 'undecided' ? `
          <button class="btn btn-sm btn-confirm llm-confirm-btn" data-span-id="${span.id}" data-mode="redact">Redact</button>
          <button class="btn btn-sm btn-confirm llm-confirm-btn" data-span-id="${span.id}" data-mode="anonymize">Anonymize</button>
          <button class="btn btn-sm btn-reject llm-reject-btn" data-span-id="${span.id}">✗</button>
        ` : ''}
      </div>
    </div>
  `).join('');

  // LLM span decision buttons
  body.querySelectorAll('.llm-confirm-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      await handleDecision(btn.dataset.spanId, 'confirm', btn.dataset.mode, doc);
    });
  });
  body.querySelectorAll('.llm-reject-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      await handleDecision(btn.dataset.spanId, 'reject', null, doc);
    });
  });
}

function updateSpanProgress(doc) {
  const spans = doc.spans.filter(s => s.tier !== 'llm');
  const decided = spans.filter(s => s.status !== 'undecided').length;
  const el = document.getElementById('span-progress');
  if (el) el.textContent = `${decided}/${spans.length}`;
}


// ══════════════════════════════════════════════════════════════════
// Span selection & decisions
// ══════════════════════════════════════════════════════════════════

function selectSpan(spanId, doc) {
  _selectedSpanId = spanId;

  // Highlight in text
  document.querySelectorAll('.pii-span.selected').forEach(el => el.classList.remove('selected'));
  const textSpan = document.querySelector(`.pii-span[data-span-id="${spanId}"]`);
  if (textSpan) textSpan.classList.add('selected');

  // Highlight in list
  document.querySelectorAll('.span-list-item.active').forEach(el => el.classList.remove('active'));
  const listItem = document.querySelector(`.span-list-item[data-span-id="${spanId}"]`);
  if (listItem) listItem.classList.add('active');

  // Find span data
  const span = doc.spans.find(s => s.id === spanId) || _llmSpans.find(s => s.id === spanId);
  if (!span) return;

  // Show decision panel
  const panel = document.getElementById('decision-panel');
  const noSel = document.getElementById('no-selection');
  panel.classList.add('active');
  noSel.style.display = 'none';

  document.getElementById('decision-text').textContent = span.text;

  const tierBadge = `<span class="tier-badge ${span.tier}">${span.tier}</span>`;
  const typeBadge = `<span class="type-badge ${span.type}">${span.type}</span>`;
  const confText = span.confidence != null ? `${(span.confidence * 100).toFixed(0)}% conf.` : 'No confidence';
  document.getElementById('decision-meta').innerHTML = `${tierBadge} ${typeBadge} · ${confText} · Status: ${span.status}`;

  // Show/hide buttons based on status
  const btns = document.getElementById('decision-btns');
  btns.style.display = span.status === 'undecided' ? 'flex' : 'none';

  // Cluster match button
  if (_clusterInfo && _clusterInfo.document_count > 0 && span.tier !== 'llm') {
    // Could add cluster-apply button here
  }
}

function deselectSpan() {
  _selectedSpanId = null;
  document.querySelectorAll('.pii-span.selected').forEach(el => el.classList.remove('selected'));
  document.querySelectorAll('.span-list-item.active').forEach(el => el.classList.remove('active'));
  const panel = document.getElementById('decision-panel');
  panel.classList.remove('active');
  document.getElementById('no-selection').style.display = '';
}

function selectNextUndecided(doc) {
  const undecided = doc.spans.filter(s => s.status === 'undecided' && s.tier !== 'llm');
  if (!undecided.length) {
    showToast('All spans decided!', 'success');
    return;
  }
  const next = undecided[0];
  selectSpan(next.id, doc);
  const textSpan = document.querySelector(`.pii-span[data-span-id="${next.id}"]`);
  if (textSpan) textSpan.scrollIntoView({ behavior: 'smooth', block: 'center' });
}


// ══════════════════════════════════════════════════════════════════
// Decision handling
// ══════════════════════════════════════════════════════════════════

async function handleDecision(spanId, action, actionMode, doc) {
  try {
    const result = await makeDecision(spanId, action, 'manual', actionMode);

    // Update local span data
    const span = doc.spans.find(s => s.id === spanId);
    if (span) {
      span.status = action === 'confirm' ? 'confirmed' : 'rejected';
      span.decided_via = 'manual';
    }
    const llmSpan = _llmSpans.find(s => s.id === spanId);
    if (llmSpan) {
      llmSpan.status = action === 'confirm' ? 'confirmed' : 'rejected';
      llmSpan.decided_via = 'manual';
    }

    // Update UI
    updateSpanInUI(spanId, action);
    updateSpanProgress(doc);
    showToast(`Span ${action}ed`, 'success');

    // Check for propagation matches
    if (result.propagation_matches && result.propagation_matches.length > 0) {
      showPropagationPrompt(result.propagation_matches, spanId, action, actionMode, doc);
    } else {
      // Also check for cluster matches
      if (_clusterInfo && _clusterInfo.document_count > 0 && span) {
        try {
          const clusterMatches = await fetchClusterMatches(doc.id, spanId);
          if (clusterMatches.length > 0) {
            showClusterPrompt(clusterMatches, spanId, action, actionMode, doc);
          } else {
            selectNextUndecided(doc);
          }
        } catch {
          selectNextUndecided(doc);
        }
      } else {
        selectNextUndecided(doc);
      }
    }
  } catch (err) {
    showToast(`Decision failed: ${err.message}`, 'error');
  }
}

function updateSpanInUI(spanId, action) {
  const status = action === 'confirm' ? 'confirmed' : 'rejected';

  // Update inline span
  const textSpan = document.querySelector(`.pii-span[data-span-id="${spanId}"]`);
  if (textSpan) {
    textSpan.classList.remove('confirmed', 'rejected');
    textSpan.classList.add(status);
    textSpan.dataset.status = status;
  }

  // Update span list
  const listItem = document.querySelector(`.span-list-item[data-span-id="${spanId}"]`);
  if (listItem) {
    const dot = listItem.querySelector('.span-list-status');
    if (dot) {
      dot.classList.remove('undecided', 'confirmed', 'rejected');
      dot.classList.add(status);
    }
  }

  // Update LLM section
  const llmCard = document.querySelector(`.llm-span-card[data-span-id="${spanId}"]`);
  if (llmCard) {
    const statusBadge = llmCard.querySelector('.action-badge');
    if (statusBadge) {
      statusBadge.textContent = status;
      statusBadge.className = `action-badge ${action}`;
    }
    llmCard.querySelectorAll('.llm-confirm-btn, .llm-reject-btn').forEach(b => b.remove());
  }

  // Update decision panel
  if (_selectedSpanId === spanId) {
    const btns = document.getElementById('decision-btns');
    if (btns) btns.style.display = 'none';
  }
}


// ══════════════════════════════════════════════════════════════════
// Propagation & Clustering
// ══════════════════════════════════════════════════════════════════

let _pendingPropMatches = [];
let _pendingPropAction = '';
let _pendingPropActionMode = null;

function showPropagationPrompt(matches, sourceSpanId, action, actionMode, doc) {
  _pendingPropMatches = matches;
  _pendingPropAction = action;
  _pendingPropActionMode = actionMode;
  _pendingPropSourceId = sourceSpanId;

  const prompt = document.getElementById('propagation-prompt');
  const span = doc.spans.find(s => s.id === sourceSpanId) || _llmSpans.find(s => s.id === sourceSpanId);
  const spanText = span ? span.text : '';

  document.getElementById('prop-title').textContent =
    `Entity Propagation: "${spanText}"`;
  document.getElementById('prop-text').textContent =
    `Apply "${action}" to ${matches.length} matching span${matches.length !== 1 ? 's' : ''} in other documents?`;

  prompt.classList.add('visible');

  // Apply All
  const applyAllBtn = document.getElementById('prop-apply-all');
  const newApplyAll = applyAllBtn.cloneNode(true);
  applyAllBtn.parentNode.replaceChild(newApplyAll, applyAllBtn);
  newApplyAll.addEventListener('click', async () => {
    const targetIds = _pendingPropMatches.map(m => m.span_id);
    try {
      const result = await propagateDecision(_pendingPropSourceId, _pendingPropAction, targetIds);
      if (result.spot_check_span_ids && result.spot_check_span_ids.length > 0) {
        prompt.classList.remove('visible');
        showSpotCheckQueue(result.spot_check_span_ids, _pendingPropAction, doc);
      } else {
        showToast(`Applied to ${result.applied_span_ids.length} spans`, 'success');
        prompt.classList.remove('visible');
        selectNextUndecided(doc);
      }
    } catch (err) {
      showToast(`Propagation failed: ${err.message}`, 'error');
    }
  });

  // Review Each
  const reviewBtn = document.getElementById('prop-review-each');
  const newReview = reviewBtn.cloneNode(true);
  reviewBtn.parentNode.replaceChild(newReview, reviewBtn);
  newReview.addEventListener('click', () => {
    prompt.classList.remove('visible');
    showReviewEachQueue(_pendingPropMatches, _pendingPropAction, _pendingPropActionMode, _pendingPropSourceId, doc);
  });

  // Dismiss
  const dismissBtn = document.getElementById('prop-dismiss');
  const newDismiss = dismissBtn.cloneNode(true);
  dismissBtn.parentNode.replaceChild(newDismiss, dismissBtn);
  newDismiss.addEventListener('click', () => {
    prompt.classList.remove('visible');
    selectNextUndecided(doc);
  });
}

function showClusterPrompt(matches, sourceSpanId, action, actionMode, doc) {
  // Reuse propagation prompt UI for cluster matches
  _pendingPropMatches = matches;
  _pendingPropAction = action;
  _pendingPropActionMode = actionMode;
  _pendingPropSourceId = sourceSpanId;

  const prompt = document.getElementById('propagation-prompt');
  const span = doc.spans.find(s => s.id === sourceSpanId);
  const spanText = span ? span.text : '';

  document.getElementById('prop-title').textContent =
    `Cluster Pattern: "${spanText}"`;
  document.getElementById('prop-text').textContent =
    `Apply "${action}" to ${matches.length} similar span${matches.length !== 1 ? 's' : ''} in template cluster?`;

  prompt.classList.add('visible');

  // Same handlers but with cluster decided_via
  const applyAllBtn = document.getElementById('prop-apply-all');
  const newApplyAll = applyAllBtn.cloneNode(true);
  applyAllBtn.parentNode.replaceChild(newApplyAll, applyAllBtn);
  newApplyAll.addEventListener('click', async () => {
    const targetIds = _pendingPropMatches.map(m => m.span_id);
    try {
      const result = await propagateDecision(_pendingPropSourceId, _pendingPropAction, targetIds, 'cluster');
      if (result.spot_check_span_ids && result.spot_check_span_ids.length > 0) {
        prompt.classList.remove('visible');
        showSpotCheckQueue(result.spot_check_span_ids, _pendingPropAction, doc);
      } else {
        showToast(`Cluster applied to ${result.applied_span_ids.length} spans`, 'success');
        prompt.classList.remove('visible');
        selectNextUndecided(doc);
      }
    } catch (err) {
      showToast(`Cluster apply failed: ${err.message}`, 'error');
    }
  });

  const reviewBtn = document.getElementById('prop-review-each');
  const newReview = reviewBtn.cloneNode(true);
  reviewBtn.parentNode.replaceChild(newReview, reviewBtn);
  newReview.addEventListener('click', () => {
    prompt.classList.remove('visible');
    showReviewEachQueue(_pendingPropMatches, _pendingPropAction, _pendingPropActionMode, _pendingPropSourceId, doc, 'cluster');
  });

  const dismissBtn = document.getElementById('prop-dismiss');
  const newDismiss = dismissBtn.cloneNode(true);
  dismissBtn.parentNode.replaceChild(newDismiss, dismissBtn);
  newDismiss.addEventListener('click', () => {
    prompt.classList.remove('visible');
    selectNextUndecided(doc);
  });
}


// ══════════════════════════════════════════════════════════════════
// Review Each Queue
// ══════════════════════════════════════════════════════════════════

function showReviewEachQueue(matches, action, actionMode, sourceSpanId, doc, decidedVia = 'propagated') {
  let idx = 0;
  const overlay = document.getElementById('review-each-overlay');
  overlay.classList.add('visible');

  function showCurrent() {
    if (idx >= matches.length) {
      overlay.classList.remove('visible');
      showToast(`Reviewed ${matches.length} spans`, 'success');
      selectNextUndecided(doc);
      return;
    }
    const m = matches[idx];
    document.getElementById('review-each-progress').textContent = `${idx + 1} of ${matches.length}`;
    document.getElementById('review-each-doc').textContent = `Document: ${m.document_title || m.document_id}`;
    document.getElementById('review-each-span').textContent = `"${m.text}"`;
  }

  showCurrent();

  const confirmBtn = document.getElementById('review-each-confirm');
  const skipBtn = document.getElementById('review-each-skip');

  const newConfirm = confirmBtn.cloneNode(true);
  confirmBtn.parentNode.replaceChild(newConfirm, confirmBtn);
  const newSkip = skipBtn.cloneNode(true);
  skipBtn.parentNode.replaceChild(newSkip, skipBtn);

  newConfirm.addEventListener('click', async () => {
    const m = matches[idx];
    try {
      await propagateDecision(sourceSpanId, action, [m.span_id], decidedVia);
    } catch {}
    idx++;
    showCurrent();
  });

  newSkip.addEventListener('click', () => {
    idx++;
    showCurrent();
  });
}


// ══════════════════════════════════════════════════════════════════
// Spot Check Guard
// ══════════════════════════════════════════════════════════════════

function showSpotCheckQueue(spotCheckIds, action, doc) {
  let idx = 0;
  const overlay = document.getElementById('spot-check-overlay');
  overlay.classList.add('visible');

  function showCurrent() {
    if (idx >= spotCheckIds.length) {
      overlay.classList.remove('visible');
      showToast(`Spot check passed — remaining spans applied`, 'success');
      selectNextUndecided(doc);
      return;
    }
    document.getElementById('spot-check-progress').textContent =
      `Spot check ${idx + 1} of ${spotCheckIds.length} — confirm each to proceed`;
    document.getElementById('spot-check-span').textContent =
      `Span ID: ${spotCheckIds[idx]}`;
  }

  showCurrent();

  const confirmBtn = document.getElementById('spot-check-confirm');
  const rejectBtn = document.getElementById('spot-check-reject');

  const newConfirm = confirmBtn.cloneNode(true);
  confirmBtn.parentNode.replaceChild(newConfirm, confirmBtn);
  const newReject = rejectBtn.cloneNode(true);
  rejectBtn.parentNode.replaceChild(newReject, rejectBtn);

  newConfirm.addEventListener('click', async () => {
    try {
      await spotCheckDecision(spotCheckIds[idx], action);
    } catch {}
    idx++;
    showCurrent();
  });

  newReject.addEventListener('click', async () => {
    try {
      await spotCheckDecision(spotCheckIds[idx], action === 'confirm' ? 'reject' : 'confirm');
    } catch {}
    idx++;
    showCurrent();
  });
}


// ══════════════════════════════════════════════════════════════════
// Manual Flagging
// ══════════════════════════════════════════════════════════════════

// ── Selection toolbar ───────────────────────────────────────────
// Shows a floating "Redact / Anonymize" popup when the user selects
// text inside the document viewer, replacing the old prompt() flow.

function _removeSelectionToolbar() {
  document.getElementById('selection-toolbar')?.remove();
}

function _showSelectionToolbar(doc, selectedText, charStart, charEnd) {
  _removeSelectionToolbar();

  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return;
  const rect = sel.getRangeAt(0).getBoundingClientRect();

  const toolbar = document.createElement('div');
  toolbar.id = 'selection-toolbar';
  toolbar.className = 'selection-toolbar';
  toolbar.style.top  = `${window.scrollY + rect.bottom + 6}px`;
  toolbar.style.left = `${window.scrollX + rect.left}px`;
  toolbar.innerHTML = `
    <div class="sel-toolbar-label">Mark as:</div>
    <select class="sel-toolbar-type" title="PII type">
      <option value="other">other</option>
      <option value="name">name</option>
      <option value="ssn">ssn</option>
      <option value="phone">phone</option>
      <option value="address">address</option>
      <option value="case_number">case number</option>
    </select>
    <button class="btn btn-xs btn-redact"    data-mode="redact">Redact</button>
    <button class="btn btn-xs btn-anonymize" data-mode="anonymize">Anonymize</button>
    <button class="btn btn-xs btn-skip sel-toolbar-cancel">✕</button>
  `;
  document.body.appendChild(toolbar);

  async function commit(actionMode) {
    const type = toolbar.querySelector('.sel-toolbar-type').value;
    _removeSelectionToolbar();
    window.getSelection()?.removeAllRanges();
    try {
      const result = await createManualSpan(doc.id, selectedText, charStart, charEnd, type, actionMode);
      // API now returns { span, propagation_matches }
      const newSpan = result.span ?? result;
      const matches = result.propagation_matches ?? [];
      doc.spans.push(newSpan);
      renderDocumentText(doc);
      renderSpanList(doc);
      updateSpanProgress(doc);
      showToast(`"${selectedText}" marked for ${actionMode}`, 'success');

      // Offer propagation if the same text appears in other documents
      if (matches.length > 0) {
        showPropagationPrompt(matches, newSpan.id, 'confirm', actionMode, doc);
      }
    } catch (err) {
      showToast(`Failed: ${err.message}`, 'error');
    }
  }

  toolbar.querySelector('[data-mode="redact"]').addEventListener('click', () => commit('redact'));
  toolbar.querySelector('[data-mode="anonymize"]').addEventListener('click', () => commit('anonymize'));
  toolbar.querySelector('.sel-toolbar-cancel').addEventListener('click', _removeSelectionToolbar);

  // Dismiss on outside click
  setTimeout(() => {
    document.addEventListener('mousedown', function dismiss(e) {
      if (!toolbar.contains(e.target)) {
        _removeSelectionToolbar();
        document.removeEventListener('mousedown', dismiss);
      }
    });
  }, 0);
}

async function handleManualFlag(doc) {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) {
    showToast('Select text in the document first', 'info');
    return;
  }

  const textContainer = document.getElementById('doc-text');
  if (!textContainer.contains(selection.anchorNode)) {
    showToast('Select text within the document', 'info');
    return;
  }

  const selectedText = selection.toString().trim();
  if (!selectedText || selectedText.length < 2) {
    showToast('Selection too short', 'info');
    return;
  }

  const charStart = doc.raw_text.indexOf(selectedText);
  if (charStart === -1) {
    showToast('Could not map selection to document text', 'error');
    return;
  }

  _showSelectionToolbar(doc, selectedText, charStart, charStart + selectedText.length);
}

// Show the toolbar automatically on mouseup inside the doc viewer
function _attachSelectionListener(doc) {
  const textContainer = document.getElementById('doc-text');
  if (!textContainer) return;
  textContainer.addEventListener('mouseup', () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) { _removeSelectionToolbar(); return; }
    const selectedText = sel.toString().trim();
    if (selectedText.length < 2) { _removeSelectionToolbar(); return; }
    if (!textContainer.contains(sel.anchorNode)) return;
    const charStart = doc.raw_text.indexOf(selectedText);
    if (charStart === -1) return;
    _showSelectionToolbar(doc, selectedText, charStart, charStart + selectedText.length);
  });
}


// ══════════════════════════════════════════════════════════════════
// Transparency Tooltip
// ══════════════════════════════════════════════════════════════════

function showTransparencyTooltip(event, el) {
  hideTransparencyTooltip();

  const tier = el.dataset.tier;
  const type = el.dataset.type;
  const confidence = el.dataset.confidence;
  const status = el.dataset.status;
  const decidedVia = el.dataset.decidedVia;
  const sourceSpan = el.dataset.sourceSpan;
  const reasoning = el.dataset.reasoning;

  let whyText = '';
  if (decidedVia === 'propagated') {
    whyText = `Applied from decision on another document (source: ${sourceSpan || 'unknown'})`;
  } else if (decidedVia === 'cluster') {
    whyText = `Applied via template cluster pattern`;
  } else if (decidedVia === 'spot_check') {
    whyText = `Confirmed via spot-check`;
  } else if (tier === 'manual') {
    whyText = 'Flagged manually by reviewer';
  } else if (tier === 'llm') {
    whyText = reasoning || 'AI second-pass detection';
  } else {
    whyText = `Detected by structured analysis`;
  }
  
  if (_docData.ocr_used) {
    whyText += ` (OCR used)`;
  }

  const confText = confidence ? `${(parseFloat(confidence) * 100).toFixed(0)}% confidence` : 'No confidence score';

  const tooltip = document.createElement('div');
  tooltip.className = 'tooltip';
  tooltip.id = 'span-tooltip';
  tooltip.innerHTML = `
    <div class="tooltip-tier">${tier} · ${type}</div>
    <div>${confText} · ${status}</div>
    <div style="margin-top:0.3rem; font-style:italic;">${whyText}</div>
  `;

  document.body.appendChild(tooltip);

  // Position near the span
  const rect = el.getBoundingClientRect();
  tooltip.style.left = `${rect.left}px`;
  tooltip.style.top = `${rect.bottom + 6}px`;

  // Keep on screen
  const tooltipRect = tooltip.getBoundingClientRect();
  if (tooltipRect.right > window.innerWidth - 10) {
    tooltip.style.left = `${window.innerWidth - tooltipRect.width - 10}px`;
  }
}

function hideTransparencyTooltip() {
  const existing = document.getElementById('span-tooltip');
  if (existing) existing.remove();
}


// ══════════════════════════════════════════════════════════════════
// Utilities
// ══════════════════════════════════════════════════════════════════

function escHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escAttr(str) {
  if (!str) return '';
  return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
