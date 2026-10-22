// Client: create event, show status/errors accessibly.
//
// Safety: every DOM write goes through textContent / createElement - this
// file never uses innerHTML, so user-supplied text can never be parsed as
// markup. escapeHtml() is kept as defence in depth for any future
// string-building helper.
const form = document.getElementById('create-form');
const statusEl = document.getElementById('status');
const errorEl = document.getElementById('errors');

let lastEventId = null;

function escapeHtml(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

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
    statusEl.textContent = 'Created event ' + escapeHtml(json.event_id);
    statusEl.focus();
  } catch (err) {
    errorEl.textContent = escapeHtml(err.message);
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
  const answerEl = document.getElementById('answer');
  const citationsEl = document.getElementById('citations');
  const askBtn = document.getElementById('askBtn');
  errorEl.textContent = '';
  if (!lastEventId) {
    answerEl.textContent = 'Create an event first, then ask for personalized ideas.';
    answerEl.focus();
    if (citationsEl) citationsEl.textContent = '';
    return;
  }
  answerEl.textContent = '';
  if (citationsEl) citationsEl.textContent = '';
  setLoading(askBtn, true);
  try {
    const res = await fetch('/ask', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({event_id: lastEventId, query: q}) });
    if (!res.ok) throw new Error('Request failed: ' + res.status);
    const json = await res.json();
    answerEl.textContent = escapeHtml(json.answer || json.ideas_text || '');
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
    errorEl.textContent = escapeHtml(err.message);
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
    errorEl.textContent = escapeHtml(err.message);
    errorEl.focus();
  } finally {
    setLoading(exportBtn, false);
  }
});
