/**
 * Batch Review Queue — primary landing screen.
 *
 * One row per distinct entity group (text + type) with undecided spans,
 * sorted by occurrence_count descending.  Resolving an entity propagates
 * the decision to every matching span across all documents in one action.
 */

import {
  fetchEntityQueue,
  previewEntityResolve,
  resolveEntity,
  abortEntitySpotCheck,
  fetchPipelineStatus,
  generateSampleBatch,
} from '../api.js';

// Use the global set by main.js to avoid a circular import
const toast = (msg, type) => window.showToast?.(msg, type);

// ── State ───────────────────────────────────────────────────────

let entities = [];
let showSingletons = false;
let activeRow = null;
let spotCheckQueue = [];
let spotCheckIdx = 0;
let spotCheckMeta = null;
let container = null;
let _pipelineTimer = null;

// ── Public API ──────────────────────────────────────────────────

export async function renderBatchQueue(el) {
  container = el;
  container.innerHTML = '<div class="loading">Loading queue…</div>';
  container.addEventListener('click', onQueueClick);
  await loadQueue();
  startPipelinePolling();
}

function startPipelinePolling() {
  updatePipelineBar();
  if (_pipelineTimer) clearInterval(_pipelineTimer);
  _pipelineTimer = setInterval(async () => {
    await updatePipelineBar();
    // Refresh queue when new docs finish detection
    const bar = document.getElementById('pipeline-bar');
    if (bar && bar.dataset.detecting === 'true') await loadQueue();
  }, 1200);
}

async function updatePipelineBar() {
  const bar = document.getElementById('pipeline-bar');
  if (!bar) return;
  try {
    const s = await fetchPipelineStatus();
    const hasActivity = s.detecting > 0 || s.queued > 0;
    bar.dataset.detecting = hasActivity ? 'true' : 'false';

    if (s.total === 0) { bar.style.display = 'none'; return; }
    bar.style.display = 'flex';

    const pct = Math.round((s.ready / s.total) * 100);
    bar.innerHTML = `
      <div class="pipeline-bar-inner">
        <div class="pipeline-progress-track">
          <div class="pipeline-progress-fill ${hasActivity ? 'pipeline-progress-fill--active' : ''}"
               style="width:${pct}%"></div>
        </div>
        <div class="pipeline-stats">
          <span class="pipeline-stat pipeline-stat--ready">
            <span class="pipeline-dot pipeline-dot--ready"></span>
            ${s.ready} ready
          </span>
          ${s.detecting > 0 ? `
          <span class="pipeline-stat pipeline-stat--detecting">
            <span class="pipeline-dot pipeline-dot--detecting pipeline-dot--pulse"></span>
            ${s.detecting} detecting
          </span>` : ''}
          ${s.queued > 0 ? `
          <span class="pipeline-stat pipeline-stat--queued">
            <span class="pipeline-dot pipeline-dot--queued"></span>
            ${s.queued} queued
          </span>` : ''}
          <span class="pipeline-stat pipeline-timing">
            avg ${s.avg_detection_s}s / doc
          </span>
        </div>
        ${hasActivity ? `<span class="pipeline-live-badge">LIVE</span>` : ''}
      </div>
    `;
  } catch { bar.style.display = 'none'; }
}

export function cleanupBatchQueue() {
  document.removeEventListener('keydown', handleSpotCheckKey);
  if (container) container.removeEventListener('click', onQueueClick);
  if (_pipelineTimer) { clearInterval(_pipelineTimer); _pipelineTimer = null; }
  container = null;
  activeRow = null;
  spotCheckQueue = [];
}

// ── Load & render ───────────────────────────────────────────────

async function loadQueue() {
  try {
    entities = await fetchEntityQueue(showSingletons);
  } catch (e) {
    container.innerHTML = `<div class="error-state"><p>Failed to load queue: ${e.message}</p>
      <button class="btn btn-primary" onclick="location.reload()">Retry</button></div>`;
    return;
  }
  render();
}

function render() {
  if (!container) return;

  const pending = entities;
  const isEmpty = pending.length === 0;

  container.innerHTML = `
    <div class="queue-page">
      <div id="pipeline-bar" class="pipeline-bar" style="display:none"></div>

      <div class="queue-page-header">
        <div>
          <h2 class="queue-title">Entity Review Queue</h2>
          <p class="queue-subtitle">
            ${pending.length} ${pending.length === 1 ? 'entity' : 'entities'} pending —
            resolve each to propagate across all matching documents
          </p>
        </div>
        <div class="queue-controls">
          <label class="singleton-toggle">
            <input type="checkbox" id="toggle-singletons" ${showSingletons ? 'checked' : ''}>
            <span>Show one-off mentions</span>
          </label>
          <button id="btn-generate" class="btn btn-secondary btn-sm">Generate Sample Batch</button>
          <a href="#/dashboard" class="btn btn-secondary btn-sm">Browse Documents</a>
        </div>
      </div>

      ${isEmpty ? renderEmptyState() : renderTable(pending)}
    </div>
  `;

  // Singleton toggle
  container.querySelector('#toggle-singletons')?.addEventListener('change', async (e) => {
    showSingletons = e.target.checked;
    await loadQueue();
  });

  // Generate sample batch
  container.querySelector('#btn-generate')?.addEventListener('click', async () => {
    const btn = container.querySelector('#btn-generate');
    btn.disabled = true;
    btn.textContent = 'Generating…';
    try {
      const r = await generateSampleBatch(20);
      toast(`Generated ${r.count} docs — detection running in background`, 'success');
      await updatePipelineBar();
      await loadQueue();
    } catch (e) {
      toast(`Failed: ${e.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Generate Sample Batch';
    }
  });
}

function renderEmptyState() {
  return `
    <div class="queue-empty">
      <div class="queue-empty-icon">✓</div>
      <h3>All entities resolved</h3>
      <p>Every entity group has been reviewed. Use <a href="#/dashboard">Browse Documents</a>
         to review any remaining one-off mentions or inspect individual documents.</p>
    </div>
  `;
}

function renderTable(items) {
  const rows = items.map(e => renderEntityRow(e)).join('');
  return `
    <div class="queue-hint">
      Select an action to apply it across every document where this entity appears.
      To review a specific document instead, click <strong>Open Doc</strong>.
    </div>
    <table class="entity-queue-table">
      <thead>
        <tr>
          <th style="width:28%">Entity</th>
          <th style="width:9%">Type</th>
          <th style="width:7%" title="Documents with undecided spans">Docs</th>
          <th style="width:28%">Context snippet</th>
          <th style="width:28%">Actions</th>
        </tr>
      </thead>
      <tbody id="queue-tbody">
        ${rows}
      </tbody>
    </table>
  `;
}

function renderEntityRow(e) {
  const isActive = activeRow &&
    activeRow.entityText === e.entity_text &&
    activeRow.entityType === e.entity_type;

  const statusBadge = e.status === 'partially_decided'
    ? `<span class="entity-status partial" title="Some spans already decided">partial</span>`
    : '';

  const noteHtml = e.note
    ? `<div class="entity-note">⚠ Spot-check aborted: ${escHtml(e.note)}</div>`
    : '';

  const typeColor = `var(--color-${e.entity_type}, var(--color-other))`;

  return `
    <tr class="entity-row ${isActive ? 'entity-row--active' : ''} ${e.status === 'partially_decided' ? 'entity-row--partial' : ''}"
        data-entity-text="${escAttr(e.entity_text)}"
        data-entity-type="${escAttr(e.entity_type)}">
      <td class="entity-cell">
        <div class="entity-text" style="color:${typeColor}">${escHtml(e.entity_text)}</div>
        ${statusBadge}
        ${noteHtml}
      </td>
      <td>
        <span class="type-badge" style="background:var(--color-${e.entity_type}-bg, rgba(251,191,36,.1)); color:${typeColor}">
          ${e.entity_type}
        </span>
      </td>
      <td class="occurrence-cell">
        <span class="occurrence-count">${e.occurrence_count}</span>
        <span class="occurrence-label">doc${e.occurrence_count !== 1 ? 's' : ''}</span>
      </td>
      <td class="snippet-cell">
        <span class="snippet-text">${escHtml(trimSnippet(e.snippet, e.entity_text))}</span>
      </td>
      <td class="action-cell">
        ${isActive ? renderActiveRowContent(e) : renderActionButtons(e.first_doc_id)}
      </td>
    </tr>
  `;
}

function renderActionButtons(firstDocId) {
  const docLink = firstDocId
    ? `<a href="#/document/${firstDocId}" class="btn btn-xs btn-open-doc" title="Review this document individually">Open Doc</a>`
    : '';
  return `
    <div class="action-buttons">
      <button class="btn btn-xs btn-redact"    data-action="confirm" data-mode="redact"    title="Confirm and redact across all matching documents">Confirm+Redact</button>
      <button class="btn btn-xs btn-anonymize" data-action="confirm" data-mode="anonymize" title="Confirm and anonymize across all matching documents">Confirm+Anon</button>
      <button class="btn btn-xs btn-reject"    data-action="reject"  data-mode=""          title="Reject this entity across all matching documents">Reject All</button>
      <button class="btn btn-xs btn-skip"      data-action="skip"    title="Skip for now">Skip</button>
      ${docLink}
    </div>
  `;
}

function renderActiveRowContent(e) {
  if (activeRow.state === 'preview') {
    return `<div class="preview-loading">Previewing…</div>`;
  }
  if (activeRow.state === 'confirm') {
    return `
      <div class="inline-confirm">
        <span class="confirm-msg">Will affect <strong>${activeRow.affectedCount}</strong> doc${activeRow.affectedCount !== 1 ? 's' : ''}</span>
        <div class="confirm-buttons">
          <button class="btn btn-xs btn-primary" id="btn-commit">Apply</button>
          <button class="btn btn-xs btn-secondary" id="btn-cancel">Cancel</button>
        </div>
      </div>
    `;
  }
  if (activeRow.state === 'spotcheck') {
    const sample = spotCheckQueue[spotCheckIdx];
    if (!sample) return '<div class="preview-loading">Processing…</div>';
    return `
      <div class="spot-check-panel">
        <div class="spot-check-header">
          Spot-check ${spotCheckIdx + 1} of ${spotCheckQueue.length}
        </div>
        <div class="spot-check-doc">${escHtml(sample.document_title)}</div>
        <div class="spot-check-snippet">"${escHtml(sample.snippet)}"</div>
        <div class="spot-check-hint">Press <kbd>Y</kbd> to approve, <kbd>N</kbd> to abort</div>
        <div class="spot-check-buttons">
          <button class="btn btn-xs btn-primary" id="btn-sc-approve">Approve (Y)</button>
          <button class="btn btn-xs btn-reject"  id="btn-sc-reject">Abort (N)</button>
        </div>
      </div>
    `;
  }
  return renderActionButtons();
}

// ── Click handler ───────────────────────────────────────────────

async function onQueueClick(e) {
  // Commit
  if (e.target.id === 'btn-commit') {
    await commitResolve();
    return;
  }
  // Cancel
  if (e.target.id === 'btn-cancel') {
    clearActiveRow();
    return;
  }
  // Spot-check approve / reject
  if (e.target.id === 'btn-sc-approve') {
    advanceSpotCheck(true);
    return;
  }
  if (e.target.id === 'btn-sc-reject') {
    await rejectSpotCheck();
    return;
  }

  // Action buttons on a row
  const btn = e.target.closest('[data-action]');
  if (!btn) return;

  const row = btn.closest('tr[data-entity-text]');
  if (!row) return;

  const entityText = row.dataset.entityText;
  const entityType = row.dataset.entityType;
  const action = btn.dataset.action;
  const mode = btn.dataset.mode || null;

  if (action === 'skip') {
    toast(`Skipped "${entityText}"`, 'info');
    return;
  }

  await startAction(entityText, entityType, action, mode);
}

// ── Action flow ─────────────────────────────────────────────────

async function startAction(entityText, entityType, action, actionMode) {
  activeRow = { entityText, entityType, action, actionMode, state: 'preview' };
  rerenderRow(entityText, entityType);

  let preview;
  try {
    preview = await previewEntityResolve(entityText, entityType, action, actionMode);
  } catch (err) {
    toast('Preview failed: ' + err.message, 'error');
    clearActiveRow();
    return;
  }

  if (preview.needs_spot_check) {
    spotCheckQueue = preview.sample_spans;
    spotCheckIdx = 0;
    spotCheckMeta = { entityText, entityType, action, actionMode };
    activeRow.state = 'spotcheck';
    activeRow.affectedCount = preview.affected_count;
    rerenderRow(entityText, entityType);
    document.addEventListener('keydown', handleSpotCheckKey);
  } else {
    activeRow.state = 'confirm';
    activeRow.affectedCount = preview.affected_count;
    rerenderRow(entityText, entityType);
  }
}

async function commitResolve() {
  const { entityText, entityType, action, actionMode } = activeRow;
  const rowEl = findRowEl(entityText, entityType);
  if (rowEl) rowEl.style.opacity = '0.5';

  try {
    const result = await resolveEntity(entityText, entityType, action, actionMode);
    entities = entities.filter(
      e => !(e.entity_text === entityText && e.entity_type === entityType)
    );
    clearActiveRow();
    toast(
      `"${entityText}" — ${action === 'confirm' ? actionMode : 'rejected'} across ${result.applied_count} span${result.applied_count !== 1 ? 's' : ''}`,
      'success'
    );
    window.updateProgressBadge?.();
  } catch (err) {
    toast('Resolve failed: ' + err.message, 'error');
    if (rowEl) rowEl.style.opacity = '1';
    clearActiveRow();
  }
}

function advanceSpotCheck(approved) {
  if (!approved) {
    rejectSpotCheck();
    return;
  }
  spotCheckIdx++;
  if (spotCheckIdx >= spotCheckQueue.length) {
    // All samples approved — proceed to final confirm
    activeRow.state = 'confirm';
    document.removeEventListener('keydown', handleSpotCheckKey);
  }
  rerenderRow(activeRow.entityText, activeRow.entityType);
}

async function rejectSpotCheck() {
  document.removeEventListener('keydown', handleSpotCheckKey);
  const { entityText, entityType } = spotCheckMeta;
  const reason = `Spot-check sample rejected at ${new Date().toLocaleTimeString()}`;

  try {
    await abortEntitySpotCheck(entityText, entityType, reason);
  } catch (_) {/* best-effort */}

  toast(`Spot-check failed — "${entityText}" left for manual review`, 'warning');

  // Reload entity (it now has a note attached)
  await loadQueue();
}

function handleSpotCheckKey(e) {
  if (e.key === 'y' || e.key === 'Y') {
    e.preventDefault();
    advanceSpotCheck(true);
  } else if (e.key === 'n' || e.key === 'N') {
    e.preventDefault();
    rejectSpotCheck();
  }
}

// ── Helpers ─────────────────────────────────────────────────────

function clearActiveRow() {
  activeRow = null;
  spotCheckQueue = [];
  spotCheckIdx = 0;
  render();
}

function rerenderRow(entityText, entityType) {
  const entity = entities.find(
    e => e.entity_text === entityText && e.entity_type === entityType
  );
  const rowEl = findRowEl(entityText, entityType);
  if (!entity || !rowEl) {
    render(); // fallback
    return;
  }
  rowEl.outerHTML = renderEntityRow(entity);
  // Re-bind click (already delegated on container so no extra work needed)
}

function findRowEl(entityText, entityType) {
  return container?.querySelector(
    `tr[data-entity-text="${CSS.escape(entityText)}"][data-entity-type="${CSS.escape(entityType)}"]`
  );
}

function trimSnippet(snippet, entityText) {
  if (!snippet) return '';
  const clean = snippet.replace(/\s+/g, ' ').trim();
  return clean.length > 100 ? clean.slice(0, 100) + '…' : clean;
}

function escHtml(str = '') {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function escAttr(str = '') {
  return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
