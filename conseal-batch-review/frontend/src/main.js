/**
 * Conseal Batch Review — Main Entry / Router
 *
 * Routes:
 *   #/        → Batch Review Queue (default landing)
 *   #/queue   → Batch Review Queue
 *   #/dashboard  → Browse Documents
 *   #/document/:id → Document Review
 *   #/audit   → Audit Log
 */

import { renderBatchQueue, cleanupBatchQueue } from './pages/batch-queue.js';
import { renderDashboard } from './pages/dashboard.js';
import { renderDocumentReview, cleanupDocumentReview } from './pages/document-review.js';
import { renderAuditLog } from './pages/audit-log.js';
import { fetchBatchProgress } from './api.js';

const main = document.getElementById('app-main');
let currentCleanup = null;

// ── Toast system ───────────────────────────────────────────────

export function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ── Batch Progress Panel (persistent header) ───────────────────

export async function updateProgressBadge() {
  try {
    const p = await fetchBatchProgress();
    const badge = document.getElementById('progress-badge');
    const docPct = p.completion_pct ?? 0;
    const entityResolved = p.resolved_entities ?? 0;
    const entityTotal = p.total_entities ?? 0;
    const entityPct = entityTotal > 0 ? Math.round((entityResolved / entityTotal) * 100) : 0;
    const propagated = p.propagated_decisions ?? 0;
    const manual = p.manual_decisions ?? 0;

    badge.innerHTML = `
      <div class="progress-panel">
        <div class="progress-panel-section">
          <span class="progress-panel-label">Docs</span>
          <div class="progress-mini-bar">
            <div class="progress-mini-fill" style="width:${docPct}%"></div>
          </div>
          <span class="progress-panel-value">${p.completed}/${p.total}</span>
        </div>
        <div class="progress-panel-divider"></div>
        <div class="progress-panel-section">
          <span class="progress-panel-label">Entities</span>
          <div class="progress-mini-bar">
            <div class="progress-mini-fill" style="width:${entityPct}%; background:var(--color-name)"></div>
          </div>
          <span class="progress-panel-value">${entityResolved}/${entityTotal}</span>
        </div>
        <div class="progress-panel-divider"></div>
        <div class="progress-panel-section">
          <span class="progress-panel-label">Propagated</span>
          <span class="progress-panel-value accent">${propagated}</span>
        </div>
        <div class="progress-panel-section">
          <span class="progress-panel-label">Manual</span>
          <span class="progress-panel-value">${manual}</span>
        </div>
      </div>
    `;
  } catch (e) {
    // silent fail — badge is non-critical
  }
}

// ── Backend health banner ──────────────────────────────────────

let _backendOk = false;

async function checkBackend() {
  const banner = document.getElementById('backend-banner');
  try {
    const r = await fetch('/health', { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      _backendOk = true;
      if (banner) banner.style.display = 'none';
      return true;
    }
  } catch {}
  if (banner) {
    banner.style.display = 'flex';
    banner.innerHTML = `
      <span>⚠ Backend not running —</span>
      <span>double-click</span>
      <code style="background:#2a1515;padding:1px 6px;border-radius:3px;">run-backend.bat</code>
      <span>in the project folder, wait for "Application startup complete", then</span>
      <button onclick="window.checkBackend()" style="margin-left:auto;background:none;border:1px solid #555;color:#aaa;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:0.75rem;">Retry</button>
    `;
  }
  return false;
}

window.checkBackend = checkBackend;

// ── Router ─────────────────────────────────────────────────────

function parseHash() {
  const hash = window.location.hash || '#/';
  const parts = hash.slice(1).split('/').filter(Boolean);

  if (parts[0] === 'document' && parts[1]) return { page: 'document', id: parts[1] };
  if (parts[0] === 'audit')     return { page: 'audit' };
  if (parts[0] === 'dashboard') return { page: 'dashboard' };
  return { page: 'queue' };
}

function updateNav(page) {
  document.querySelectorAll('.nav-link').forEach(link => {
    const route = link.dataset.route;
    link.classList.toggle('active',
      (route === 'queue'     && page === 'queue') ||
      (route === 'dashboard' && page === 'dashboard') ||
      (route === 'audit'     && page === 'audit')
    );
  });
}

async function route() {
  if (currentCleanup) { currentCleanup(); currentCleanup = null; }

  const { page, id } = parseHash();
  updateNav(page);
  main.innerHTML = '<div class="loading">Loading…</div>';

  try {
    switch (page) {
      case 'queue':
        await renderBatchQueue(main);
        currentCleanup = cleanupBatchQueue;
        break;
      case 'document':
        await renderDocumentReview(main, id);
        currentCleanup = cleanupDocumentReview;
        break;
      case 'audit':
        await renderAuditLog(main);
        break;
      default:
        await renderDashboard(main);
        break;
    }
  } catch (err) {
    main.innerHTML = `
      <div class="error-state">
        <p>Failed to load page: ${err.message}</p>
        <button class="btn btn-primary" onclick="location.reload()">Retry</button>
      </div>
    `;
  }

  updateProgressBadge();
}

// ── Init ───────────────────────────────────────────────────────

window.addEventListener('hashchange', route);
window.addEventListener('load', async () => {
  await checkBackend();
  route();
  setInterval(updateProgressBadge, 30000);
  setInterval(checkBackend, 15000);
});

// Global access for inline handlers and child pages
window.showToast = showToast;
window.updateProgressBadge = updateProgressBadge;
