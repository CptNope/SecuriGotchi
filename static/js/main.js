/* Only textContent for untrusted memory. */
document.addEventListener('DOMContentLoaded', () => {
  const el = id => document.getElementById(id);
  async function api(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Request failed');
    return payload;
  }
  async function loadStatus() {
    try {
      const [brain, chain, memory] = await Promise.all([
        api('/api/brain'), api('/api/chain_verify'), api('/api/memory')
      ]);
      el('brain-xp').textContent = brain.xp;
      el('brain-level').textContent = brain.level;
      el('brain-mode').textContent = brain.mode;
      el('brain-count').textContent = brain.memory_count;
      const status = el('chain-status');
      status.textContent = chain.valid ? '✓ Signed ledger verified' :
        chain.blocks_valid ? '⚠ Ledger unsigned' : '⚠ Ledger invalid';
      status.classList.add(chain.valid ? 'valid' : 'invalid');
      const log = el('memory-entries');
      log.replaceChildren();
      if (!memory.length) log.textContent = 'No activity recorded yet.';
      memory.slice(-20).reverse().forEach(line => {
        const item = document.createElement('div');
        item.className = 'logentry';
        item.textContent = line;
        log.appendChild(item);
      });
    } catch (error) {
      el('chain-status').textContent = 'Unavailable';
      el('memory-entries').textContent = error.message;
    }
  }
  el('query-form').addEventListener('submit', async event => {
    event.preventDefault();
    const output = el('query-results');
    output.textContent = 'Searching…';
    try {
      const results = await api('/api/query', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
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
  loadStatus();
});
