/* All server-provided data is rendered with textContent. */
document.addEventListener('DOMContentLoaded', () => {
  const el = id => document.getElementById(id);
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  async function api(url, options) {
    const response = await fetch(url, options);
    if (response.status === 401) {
      location.assign('/login');
      throw new Error('Login required');
    }
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Request failed');
    return payload;
  }
  async function loadStatus() {
    try {
      const [brain, chain, memory, threats] = await Promise.all([
        api('/api/brain'), api('/api/chain_verify'), api('/api/memory'), api('/api/threats')
      ]);
      el('brain-xp').textContent = brain.xp;
      el('brain-level').textContent = brain.level;
      el('brain-mode').textContent = brain.mode;
      el('brain-count').textContent = brain.memory_count;
      const status = el('chain-status');
      status.textContent = chain.valid ? '✓ Signed ledger verified' :
        chain.blocks_valid ? '⚠ Ledger unsigned' : '⚠ Ledger invalid';
      status.classList.toggle('valid', chain.valid);
      status.classList.toggle('invalid', !chain.valid);
      const log = el('memory-entries');
      log.replaceChildren();
      if (!memory.length) log.textContent = 'No activity recorded yet.';
      memory.slice(-20).reverse().forEach(line => {
        const item = document.createElement('div');
        item.className = 'logentry';
        item.textContent = line;
        log.appendChild(item);
      });
      el('threat-availability').textContent = threats.status === 'available' ?
        'Source: ' + threats.source + ' · sampled ' + threats.sample_lines + ' lines' :
        'SSH authentication log unavailable';
      el('threat-failed').textContent = threats.failed_logins;
      el('threat-invalid').textContent = threats.invalid_user_events;
      el('threat-accepted').textContent = threats.successful_logins;
      el('threat-sources').textContent = threats.unique_failure_sources;
      el('threat-note').textContent = threats.note;
    } catch (error) {
      el('chain-status').textContent = 'Unavailable';
      el('memory-entries').textContent = error.message;
      el('threat-note').textContent = error.message;
    }
  }
  el('query-form').addEventListener('submit', async event => {
    event.preventDefault();
    const output = el('query-results');
    output.textContent = 'Searching…';
    try {
      const results = await api('/api/query', {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
        body: JSON.stringify({query: el('query-input').value.trim()})
      });
      output.replaceChildren();
      if (!results.length) output.textContent = 'No matching memories.';
      results.forEach(item => {
        const entry = document.createElement('div');
        entry.className = 'result';
        entry.textContent = item.content;
        output.appendChild(entry);
      });
    } catch (error) { output.textContent = error.message; }
  });
  el('refresh-threats').addEventListener('click', loadStatus);
  loadStatus();
});
