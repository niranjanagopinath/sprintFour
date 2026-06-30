/**
 * Audit Log Page — read-only table of all decisions, filterable.
 */

import { fetchAuditLog } from '../api.js';

export async function renderAuditLog(container) {
  let filters = { documentId: '', type: '', decidedVia: '', limit: 100, offset: 0 };

  container.innerHTML = `
    <a href="#/" class="back-link">← Back to Dashboard</a>
    <div class="audit-header">
      <h2 style="font-size:1.2rem; font-weight:700;">Audit Log</h2>
      <div class="audit-filters">
        <input id="audit-doc-filter" type="text" placeholder="Document ID…" style="width:130px;" />
        <select id="audit-type-filter">
          <option value="">All Types</option>
          <option value="name">Name</option>
          <option value="ssn">SSN</option>
          <option value="phone">Phone</option>
          <option value="address">Address</option>
          <option value="case_number">Case Number</option>
          <option value="other">Other</option>
        </select>
        <select id="audit-via-filter">
          <option value="">All Methods</option>
          <option value="manual">Manual</option>
          <option value="propagated">Propagated</option>
          <option value="cluster">Cluster</option>
          <option value="spot_check">Spot Check</option>
        </select>
        <button class="btn btn-sm" id="audit-apply-btn">Apply</button>
      </div>
    </div>

    <div id="audit-table-container">
      <div class="loading">Loading…</div>
    </div>

    <div class="pagination" id="audit-pagination"></div>
  `;

  async function loadLog() {
    const tableContainer = document.getElementById('audit-table-container');
    tableContainer.innerHTML = '<div class="loading">Loading…</div>';

    try {
      const result = await fetchAuditLog(filters);
      const { decisions, total } = result;

      if (!decisions.length) {
        tableContainer.innerHTML = '<div class="empty-state">No decisions recorded yet</div>';
        document.getElementById('audit-pagination').innerHTML = '';
        return;
      }

      tableContainer.innerHTML = `
        <table class="audit-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Document</th>
              <th>Span Text</th>
              <th>Type</th>
              <th>Tier</th>
              <th>Action</th>
              <th>Via</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            ${decisions.map(d => `
              <tr>
                <td style="font-size:0.8rem; color:var(--text-muted); white-space:nowrap;">${formatTime(d.timestamp)}</td>
                <td style="max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                  <a href="#/document/${d.document_id}" style="color:var(--text-primary); text-decoration:underline dotted;">
                    ${escHtml(d.document_title || d.document_id)}
                  </a>
                </td>
                <td style="font-family:var(--font-mono); font-size:0.8rem; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                  ${escHtml(d.span_text)}
                </td>
                <td><span class="type-badge ${d.span_type}">${d.span_type}</span></td>
                <td><span class="tier-badge ${d.span_tier}">${d.span_tier}</span></td>
                <td><span class="action-badge ${d.action}">${d.action}</span></td>
                <td><span class="via-badge">${d.decided_via.replace('_', ' ')}</span></td>
                <td style="font-variant-numeric:tabular-nums; color:var(--text-muted);">
                  ${d.confidence_at_decision != null ? (d.confidence_at_decision * 100).toFixed(0) + '%' : '—'}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;

      // Pagination
      const totalPages = Math.ceil(total / filters.limit);
      const currentPage = Math.floor(filters.offset / filters.limit) + 1;
      document.getElementById('audit-pagination').innerHTML = `
        <button class="btn btn-sm btn-ghost" id="audit-prev" ${currentPage <= 1 ? 'disabled' : ''}>← Prev</button>
        <span class="page-info">Page ${currentPage} of ${totalPages} (${total} total)</span>
        <button class="btn btn-sm btn-ghost" id="audit-next" ${currentPage >= totalPages ? 'disabled' : ''}>Next →</button>
      `;

      document.getElementById('audit-prev')?.addEventListener('click', () => {
        filters.offset = Math.max(0, filters.offset - filters.limit);
        loadLog();
      });
      document.getElementById('audit-next')?.addEventListener('click', () => {
        filters.offset += filters.limit;
        loadLog();
      });

    } catch (err) {
      tableContainer.innerHTML = `
        <div class="error-state">
          <p>Failed to load audit log: ${err.message}</p>
          <button class="btn btn-primary" onclick="this.closest('.error-state').innerHTML='<div class=\\'loading\\'>Retrying…</div>'">Retry</button>
        </div>
      `;
    }
  }

  // Filter controls
  document.getElementById('audit-apply-btn').addEventListener('click', () => {
    filters.documentId = document.getElementById('audit-doc-filter').value.trim();
    filters.type = document.getElementById('audit-type-filter').value;
    filters.decidedVia = document.getElementById('audit-via-filter').value;
    filters.offset = 0;
    loadLog();
  });

  loadLog();
}

function formatTime(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts + 'Z');
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return ts;
  }
}

function escHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
