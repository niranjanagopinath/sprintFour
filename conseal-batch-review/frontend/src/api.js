/**
 * Conseal Batch Review — API Client
 * Centralized fetch wrapper with error handling and retry.
 */

const BASE = ''; // uses Vite proxy in dev

async function request(path, options = {}) {
  const { method = 'GET', body, retries = 0, timeout = 5000 } = options;

  const fetchOpts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) fetchOpts.body = JSON.stringify(body);

  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      try {
        const resp = await fetch(`${BASE}${path}`, { ...fetchOpts, signal: controller.signal });
        clearTimeout(timer);
        if (!resp.ok) {
          const errBody = await resp.text().catch(() => '');
          throw new Error(`HTTP ${resp.status}: ${errBody}`);
        }
        return await resp.json();
      } finally {
        clearTimeout(timer);
      }
    } catch (err) {
      lastError = err.name === 'AbortError'
        ? new Error('Request timed out — is the backend running on port 8000?')
        : err;
      if (attempt < retries) await new Promise(r => setTimeout(r, 400));
    }
  }
  throw lastError;
}

// ── Documents ──────────────────────────────────────────────────

export function fetchDocuments(state = null, limit = 50, offset = 0) {
  let url = `/documents?limit=${limit}&offset=${offset}`;
  if (state) url += `&state=${state}`;
  return request(url);
}

export function loadSampleBatch() {
  return request('/documents/load-sample', { method: 'POST' });
}

export async function uploadDocuments(files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  
  const resp = await fetch(`${BASE}/documents/upload`, {
    method: 'POST',
    body: formData
  });
  if (!resp.ok) {
    const errBody = await resp.text().catch(() => '');
    throw new Error(`Upload failed HTTP ${resp.status}: ${errBody}`);
  }
  return resp.json();
}

export function fetchDocument(docId) {
  return request(`/documents/${docId}`);
}

export function transitionState(docId, state) {
  return request(`/documents/${docId}/state`, {
    method: 'POST',
    body: { state },
  });
}

export function fetchLlmReview(docId) {
  return request(`/documents/${docId}/llm-review`);
}

export function exportDocument(docId) {
  return request(`/documents/${docId}/export`);
}

// ── Spans ──────────────────────────────────────────────────────

export function makeDecision(spanId, action, decidedVia = 'manual') {
  return request(`/spans/${spanId}/decision`, {
    method: 'POST',
    body: { action, decided_via: decidedVia },
  });
}

export function fetchPropagationMatches(spanId) {
  return request(`/spans/${spanId}/propagation`);
}

export function propagateDecision(sourceSpanId, action, targetSpanIds, decidedVia = 'propagated') {
  return request('/spans/propagate', {
    method: 'POST',
    body: {
      source_span_id: sourceSpanId,
      action,
      target_span_ids: targetSpanIds,
      decided_via: decidedVia,
    },
  });
}

export function spotCheckDecision(spanId, action) {
  return request(`/spans/spot-check/${spanId}`, {
    method: 'POST',
    body: { action, decided_via: 'spot_check' },
  });
}

export function createManualSpan(documentId, text, charStart, charEnd, type = 'other', actionMode = 'redact') {
  return request('/spans/manual', {
    method: 'POST',
    body: {
      document_id: documentId,
      text,
      char_start: charStart,
      char_end: charEnd,
      type,
      action_mode: actionMode,
    },
  });
}

// ── Batch ──────────────────────────────────────────────────────

export function fetchBatchProgress() {
  return request('/batch/progress');
}

export function fetchPipelineStatus() {
  return request('/batch/pipeline-status', { timeout: 8000 });
}

export function generateSampleBatch(count = 20) {
  return request(`/batch/generate-sample?count=${count}`, { method: 'POST', timeout: 15000 });
}

export function fetchCluster(docId) {
  return request(`/batch/clusters/${docId}`);
}

export function fetchClusterMatches(docId, spanId) {
  return request(`/batch/clusters/${docId}/spans/${spanId}/matches`);
}

export function clusterApply(sourceDocId, sourceSpanId, action, targetSpanIds) {
  return request('/batch/cluster-apply', {
    method: 'POST',
    body: {
      source_document_id: sourceDocId,
      source_span_id: sourceSpanId,
      action,
      target_document_ids: targetSpanIds,
      decided_via: 'cluster',
    },
  });
}

export function fetchCategoryStats() {
  return request('/batch/category-stats');
}

// ── Entity Queue ───────────────────────────────────────────────

export function fetchEntityQueue(showSingletons = false) {
  return request(`/entity-queue?show_singletons=${showSingletons}`);
}

export function previewEntityResolve(entityText, entityType, action, actionMode) {
  return request('/entity-queue/preview', {
    method: 'POST',
    body: { entity_text: entityText, entity_type: entityType, action, action_mode: actionMode },
  });
}

export function resolveEntity(entityText, entityType, action, actionMode) {
  return request('/entity-queue/resolve', {
    method: 'POST',
    body: { entity_text: entityText, entity_type: entityType, action, action_mode: actionMode },
  });
}

export function abortEntitySpotCheck(entityText, entityType, reason) {
  return request('/entity-queue/spot-check-abort', {
    method: 'POST',
    body: { entity_text: entityText, entity_type: entityType, reason },
  });
}

// ── Audit ──────────────────────────────────────────────────────

export function fetchAuditLog({ documentId, type, decidedVia, limit = 100, offset = 0 } = {}) {
  let url = `/audit/log?limit=${limit}&offset=${offset}`;
  if (documentId) url += `&document_id=${documentId}`;
  if (type) url += `&type=${type}`;
  if (decidedVia) url += `&decided_via=${decidedVia}`;
  return request(url);
}
