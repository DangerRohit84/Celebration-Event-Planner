// Client: create event, ask for grounded ideas, export the plan.
//
// Safety: every DOM write goes through textContent / createElement - this
// file never injects markup through a raw-HTML setter, so user-supplied
// text can never be parsed as markup, and no HTML escaping pass is needed.
const form = document.getElementById('create-form');
const statusEl = document.getElementById('status');
const errorEl = document.getElementById('errors');
// Belt and braces: the markup already carries tabindex="-1" on #errors, but
// focus() only works on a focusable element, so set it here too in case the
// attribute is ever dropped from the template.
errorEl?.setAttribute('tabindex', '-1');

let lastEventId = null;

function setLoading(btn, loading) {
  if (!btn) return;
  btn.disabled = loading;
  if (loading) {
    btn.dataset.prevText = btn.textContent;
    btn.textContent = '';
    const spinner = document.createElement('span');
    spinner.className = 'spinner';
    spinner.setAttribute('aria-hidden', 'true');
    btn.appendChild(spinner);
    btn.appendChild(document.createTextNode(' Loading...'));
  } else if (btn.dataset.prevText) {
    btn.textContent = btn.dataset.prevText;
  }
}

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  errorEl.textContent = '';
  statusEl.textContent = 'Creating...';
  const data = Object.fromEntries(new FormData(form));
  data.guest_count = Number(data.guest_count || 0);
  data.budget_total = Number(data.budget_total || 0);
  const submitBtn = form.querySelector('button[type="submit"]');
  setLoading(submitBtn, true);
  try {
    const res = await fetch('/events', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
    if (!res.ok) throw new Error('Request failed: ' + res.status);
    const json = await res.json();
    lastEventId = json.event_id;
    try { localStorage.setItem('lastEventId', lastEventId); } catch (e) {}
    statusEl.textContent = 'Created event ' + json.event_id;
    statusEl.focus();
  } catch (err) {
    errorEl.textContent = err.message;
    statusEl.textContent = '';
    errorEl.focus();
  } finally {
    setLoading(submitBtn, false);
  }
});

// Restore last event id if present
try {
  const stored = localStorage.getItem('lastEventId');
  if (stored) lastEventId = stored;
} catch (e) {}

document.getElementById('askBtn')?.addEventListener('click', async () => {
  const q = document.getElementById('q').value;
  const plainBox = document.getElementById('plain');
  const plainLanguage = Boolean(plainBox && plainBox.checked);
  const answerEl = document.getElementById('answer');
  const answerModeEl = document.getElementById('answerMode');
  const citationsEl = document.getElementById('citations');
  const askBtn = document.getElementById('askBtn');
  errorEl.textContent = '';
  if (!lastEventId) {
    answerEl.textContent = 'Create an event first, then ask for personalized ideas.';
    answerEl.focus();
    if (citationsEl) citationsEl.textContent = '';
    if (answerModeEl) answerModeEl.textContent = '';
    return;
  }
  answerEl.textContent = '';
  if (citationsEl) citationsEl.textContent = '';
  if (answerModeEl) answerModeEl.textContent = '';
  setLoading(askBtn, true);
  try {
    const res = await fetch('/ask', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({event_id: lastEventId, query: q, plain_language: plainLanguage}) });
    if (!res.ok) throw new Error('Request failed: ' + res.status);
    const json = await res.json();
    answerEl.textContent = json.answer || json.ideas_text || '';
    if (answerModeEl) {
      answerModeEl.textContent = json.plain_language
        ? 'Answered in simple language.'
        : 'Answered in standard language.';
    }
    const cites = Array.isArray(json.citations) ? json.citations : [];
    if (citationsEl) {
      if (cites.length === 0) {
        citationsEl.textContent = 'No citations returned.';
      } else {
        citationsEl.textContent = '';
        cites.forEach((c) => {
          const div = document.createElement('div');
          div.className = 'citation';
          div.textContent = c.text || c.id || '';
          citationsEl.appendChild(div);
        });
      }
    }
    answerEl.focus();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.focus();
  } finally {
    setLoading(askBtn, false);
  }
});

document.getElementById('exportBtn')?.addEventListener('click', async () => {
  const exportBtn = document.getElementById('exportBtn');
  errorEl.textContent = '';
  if (!lastEventId) {
    statusEl.textContent = 'Create an event first, then export the plan.';
    statusEl.focus();
    return;
  }
  setLoading(exportBtn, true);
  try {
    const res = await fetch('/export', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({event_id: lastEventId}) });
    if (!res.ok) throw new Error('Request failed: ' + res.status);
    const json = await res.json();
    const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const safeId = String(lastEventId || '').replace(/[^A-Za-z0-9_-]/g, '');
    a.download = 'event-plan-' + (safeId || 'event') + '.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    statusEl.textContent = 'Exported plan.';
    statusEl.focus();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.focus();
  } finally {
    setLoading(exportBtn, false);
  }
});

// Upload a PDF document (contract, venue quote) for extra grounded context.
// The FormData body is passed without a Content-Type header so the browser
// sets the multipart boundary itself.
document.getElementById('uploadBtn')?.addEventListener('click', async () => {
  const uploadBtn = document.getElementById('uploadBtn');
  const fileInput = document.getElementById('docfile');
  const uploadStatusEl = document.getElementById('uploadStatus');
  errorEl.textContent = '';
  if (!uploadStatusEl) return;
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    uploadStatusEl.textContent = 'Choose a PDF file first.';
    return;
  }
  const body = new FormData();
  body.append('file', fileInput.files[0]);
  setLoading(uploadBtn, true);
  try {
    const res = await fetch('/upload', { method: 'POST', body });
    if (!res.ok) throw new Error('Upload failed: ' + res.status);
    const json = await res.json();
    uploadStatusEl.textContent = 'Uploaded ' + json.filename + ' ('
      + json.pages + ' pages, ' + json.chunks + ' chunks).';
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.focus();
  } finally {
    setLoading(uploadBtn, false);
  }
});
