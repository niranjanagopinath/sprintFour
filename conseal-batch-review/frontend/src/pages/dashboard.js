/**
 * Dashboard Page — batch progress, document list, filtering.
 */

import { fetchDocuments, fetchBatchProgress, transitionState, loadSampleBatch, uploadDocuments } from '../api.js';

export async function renderDashboard(container) {
  const [progress, docs] = await Promise.all([
    fetchBatchProgress(),
    fetchDocuments(null, 200),
  ]);

  let currentFilter = null;

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
      <div>
        <h2 style="font-size:1.3rem; font-weight:700;">Browse Documents</h2>
        <p style="font-size:0.85rem; color:var(--text-muted); margin-top:2px;">
          For entity-first batch review, use the
          <a href="#/queue" style="color:var(--border-focus);">Review Queue</a>.
        </p>
      </div>
      <div style="display: flex; gap: 10px;">
        <button id="btn-load-sample" class="btn btn-secondary">Load Sample Batch</button>
        <label for="upload-files" class="btn btn-primary" style="cursor: pointer; margin: 0;">Upload PDFs / ZIP</label>
        <input type="file" id="upload-files" multiple accept=".pdf,.zip" style="display: none;" />
      </div>
    </div>

    <div class="dashboard-stats">
      <div class="stat-card">
        <div class="stat-label">Total</div>
        <div class="stat-value">${progress.total}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Pending</div>
        <div class="stat-value pending">${progress.pending}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">In Review</div>
        <div class="stat-value in_review">${progress.in_review}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Completed</div>
        <div class="stat-value completed">${progress.completed}</div>
      </div>
    </div>

    <div class="progress-bar-full">
      <div class="progress-bar-fill" style="width: ${progress.completion_pct}%"></div>
    </div>

    <div class="doc-list-header">
      <h2>Documents</h2>
      <div class="filter-bar">
        <button class="filter-btn active" data-filter="">All</button>
        <button class="filter-btn" data-filter="pending">Pending</button>
        <button class="filter-btn" data-filter="in_review">In Review</button>
        <button class="filter-btn" data-filter="completed">Completed</button>
      </div>
    </div>

    <table class="doc-table">
      <thead>
        <tr>
          <th>Title</th>
          <th>Template</th>
          <th>State</th>
          <th>Progress</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="doc-list-body"></tbody>
    </table>
  `;

  function renderRows(filter) {
    const filtered = filter ? docs.filter(d => d.state === filter) : docs;
    const tbody = document.getElementById('doc-list-body');
    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No documents found</td></tr>`;
      return;
    }
    tbody.innerHTML = filtered.map(doc => {
      const pct = doc.span_count > 0 ? Math.round((doc.decided_count / doc.span_count) * 100) : 0;
      return `
        <tr data-doc-id="${doc.id}">
          <td style="font-weight:500; max-width:400px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escHtml(doc.title)}</td>
          <td><span class="type-badge">${(doc.template_id || 'uploaded').replace('_', ' ')}</span></td>
          <td><span class="state-badge ${doc.state}">${doc.state.replace('_', ' ')}</span></td>
          <td>
            <div class="span-count-bar">
              <div class="span-count-mini">
                <div class="span-count-fill" style="width:${pct}%"></div>
              </div>
              <span style="font-size:0.8rem; color:var(--text-muted);">${doc.decided_count}/${doc.span_count}</span>
            </div>
          </td>
          <td>
            <button class="btn btn-sm btn-primary start-review-btn" data-doc-id="${doc.id}">
              ${doc.state === 'completed' ? 'View' : 'Review'}
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  renderRows(currentFilter);

  // Filter buttons
  container.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter || null;
      renderRows(currentFilter);
    });
  });

  // Load sample batch
  const btnLoadSample = container.querySelector('#btn-load-sample');
  if (btnLoadSample) {
    btnLoadSample.addEventListener('click', async () => {
      btnLoadSample.disabled = true;
      btnLoadSample.textContent = 'Loading...';
      try {
        await loadSampleBatch();
        window.location.reload();
      } catch (e) {
        alert('Failed to load sample batch');
        btnLoadSample.disabled = false;
        btnLoadSample.textContent = 'Load Sample Batch';
      }
    });
  }

  // Upload PDFs
  const uploadFiles = container.querySelector('#upload-files');
  const uploadLabel = container.querySelector('label[for="upload-files"]');
  if (uploadFiles && uploadLabel) {
    uploadFiles.addEventListener('change', async (e) => {
      if (!e.target.files.length) return;
      
      uploadLabel.textContent = 'Uploading...';
      uploadLabel.style.pointerEvents = 'none';
      uploadLabel.style.opacity = '0.7';
      
      try {
        await uploadDocuments(e.target.files);
        window.location.reload();
      } catch (err) {
        alert('Upload failed: ' + err.message);
        uploadLabel.textContent = 'Upload PDFs';
        uploadLabel.style.pointerEvents = 'auto';
        uploadLabel.style.opacity = '1';
      }
    });
  }

  // Row click → navigate to document
  container.addEventListener('click', async (e) => {
    const row = e.target.closest('tr[data-doc-id]');
    const btn = e.target.closest('.start-review-btn');
    if (row || btn) {
      const docId = (btn || row).dataset.docId || row.dataset.docId;
      // Transition to in_review if pending
      const doc = docs.find(d => d.id === docId);
      if (doc && doc.state === 'pending') {
        try {
          await transitionState(docId, 'in_review');
        } catch (e) {
          // Continue anyway — might already be in_review
        }
      }
      window.location.hash = `#/document/${docId}`;
    }
  });
}

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
