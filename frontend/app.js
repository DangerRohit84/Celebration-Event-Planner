// Client: create event, show status/errors accessibly.
const form = document.getElementById('create-form');
const statusEl = document.getElementById('status');
const errorEl = document.getElementById('errors');

function escapeHtml(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  errorEl.textContent = '';
  statusEl.textContent = 'Creating...';
  const data = Object.fromEntries(new FormData(form));
  data.guest_count = Number(data.guest_count || 0);
  data.budget_total = Number(data.budget_total || 0);
  try {
    const res = await fetch('/events', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
    if (!res.ok) throw new Error('Request failed: ' + res.status);
    const json = await res.json();
    statusEl.textContent = 'Created event ' + escapeHtml(json.event_id);
    statusEl.focus();
  } catch (err) {
    errorEl.textContent = escapeHtml(err.message);
    statusEl.textContent = '';
    errorEl.focus();
  }
});

document.getElementById('askBtn')?.addEventListener('click', async () => {
  const q = document.getElementById('q').value;
  const answerEl = document.getElementById('answer');
  try {
    const res = await fetch('/ask', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({event_id: 'demo', query: q}) });
    const json = await res.json();
    answerEl.textContent = escapeHtml(json.answer || json.ideas_text || '');
    answerEl.focus();
  } catch (err) {
    document.getElementById('errors').textContent = escapeHtml(err.message);
  }
});
