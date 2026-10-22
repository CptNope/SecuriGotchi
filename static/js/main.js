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
  const moodLabels = {sleeping:'Sleeping',calm:'All clear',watchful:'Watchful',alert:'On alert',critical:'High alert'};
  async function loadMonitor() {
    try {
      const data = await api('/api/monitor');
      const mood = moodLabels[data.mood] ? data.mood : 'sleeping';
      el('gotchi-sprite').className = 'gotchi-sprite mood-' + mood;
      el('gotchi-mood').textContent = moodLabels[mood];
      el('collector-state').textContent = data.status === 'running' ? 'Monitoring local system' :
        data.status === 'stale' ? 'Collector stopped or stale' : 'Collector not started';
      el('monitor-failed').textContent = data.events_24h.failed || 0;
      el('monitor-invalid').textContent = data.events_24h.invalid_user || 0;
      el('monitor-disk').textContent = data.health?.disk_percent == null ? 'N/A' : data.health.disk_percent + '%';
      el('monitor-memory').textContent = data.health?.memory_percent == null ? 'N/A' : data.health.memory_percent + '%';
      el('monitor-note').textContent = 'SSH log: ' + data.log_status +
        (data.bytes_skipped ? ' · ' + data.bytes_skipped + ' bytes skipped (log overflow)' : '') +
        '. Collector must run separately.';
      const alerts = el('monitor-alerts');
      alerts.replaceChildren();
      if (!data.alerts.length) alerts.textContent = 'No recent alerts.';
      data.alerts.forEach(item => {
        const line = document.createElement('div');
        line.className = 'monitor-alert level-' + item.severity;
        const label = document.createElement('strong');
        label.textContent = item.severity.toUpperCase() + ' · ' + item.title;
        const detail = document.createElement('span');
        detail.textContent = item.detail;
        line.append(label, detail);
        alerts.appendChild(line);
      });
    } catch (error) {
      el('collector-state').textContent = 'Monitor unavailable';
      el('monitor-note').textContent = error.message;
    }
  }
  el('refresh-monitor').addEventListener('click', loadMonitor);
  async function loadNetwork() {
    try {
      const data = await api('/api/network');
      const wifi = data.wifi || {};
      const discovery = data.discovery || {};
      el('network-state').textContent = 'Sample: ' + data.status + ' · Wi-Fi: ' + (wifi.status || 'not enabled');
      el('network-ssid').textContent = wifi.ssid || 'Unavailable';
      el('network-signal').textContent = wifi.signal_percent == null ? 'Unavailable' : wifi.signal_percent + '%';
      el('network-security').textContent = wifi.authentication || 'Unavailable';
      el('network-ip').textContent = wifi.ip || 'Unavailable';
      el('network-note').textContent = wifi.detail || 'Enable Wi-Fi monitoring in the collector.';
      el('network-discovery').textContent = 'Discovery: ' + (discovery.status || 'disabled') +
        (discovery.scope ? ' · ' + discovery.scope : '') +
        (discovery.sampled_at ? ' · ' + new Date(discovery.sampled_at * 1000).toLocaleString() : '') +
        (discovery.baseline ? ' · Initial baseline' : '') + '. ' + (discovery.detail || '');
      const list = el('network-devices');
      list.replaceChildren();
      const devices = discovery.devices || [];
      if (!devices.length) list.textContent = 'No responding devices recorded in this sample.';
      devices.forEach(device => {
        const row = document.createElement('div');
        row.className = 'logentry';
        row.textContent = device.ip + ' · ' + (device.mac || 'MAC unavailable') + ' · Ping response';
        list.appendChild(row);
      });
    } catch (error) { el('network-state').textContent = error.message; }
  }
  el('refresh-network').addEventListener('click', loadNetwork);
  async function loadTrends() {
    const chart = el('trend-chart');
    try {
      const points = await api('/api/trends');
      const max = Math.max(1, ...points.map(item => item.failed));
      chart.replaceChildren();
      points.forEach(item => {
        const bar = document.createElement('span');
        bar.className = 'trend-bar';
        bar.style.height = Math.max(3, item.failed / max * 76) + 'px';
        bar.title = item.hour + ': ' + item.failed + ' failures';
        chart.appendChild(bar);
      });
      chart.setAttribute('aria-label', 'Failed logins by hour: ' + points.map(p => p.failed).join(', '));
    } catch (err) { chart.textContent = 'Trend unavailable'; }
  }
  async function loadAI() {
    const status = el('ai-diagnostics');
    const select = el('ai-model');
    const run = el('ai-run');
    run.disabled = true;
    select.disabled = true;
    select.replaceChildren();
    try {
      const data = await api('/api/ai/diagnostics');
      status.textContent = 'Collector: ' + data.collector +
        ' · Event source: ' + data.event_source +
        ' · Ollama: ' + data.ollama + ' · MCP SDK: ' + data.mcp_sdk;
      const models = data.models || [];
      if (!models.length) {
        select.add(new Option('No local models detected', ''));
        return;
      }
      models.forEach(name => select.add(new Option(name, name)));
      select.disabled = data.ollama !== 'ready';
      run.disabled = data.collector !== 'running' || data.ollama !== 'ready';
    } catch (error) { status.textContent = 'AI diagnostics unavailable'; }
  }
  el('ai-refresh').addEventListener('click', loadAI);
  el('ai-explain-form').addEventListener('submit', async event => {
    event.preventDefault();
    const report = el('ai-report');
    const run = el('ai-run');
    run.disabled = true;
    report.textContent = 'Asking the selected local Ollama model… Loading a large model can take up to three minutes.';
    try {
      const data = await api('/api/ai/explain', {
        method: 'POST',
        headers: {'Content-Type':'application/json', 'X-CSRF-Token': csrf},
        body: JSON.stringify({model: el('ai-model').value})
      });
      report.textContent = data.analysis + '\n\n' + data.notice;
    } catch(error) { report.textContent = error.message; }
    finally { run.disabled = false; }
  });
  loadStatus();
  loadMonitor();
  loadAI();
  loadTrends();
  loadNetwork();
  setInterval(loadNetwork, 30000);
  setInterval(loadMonitor, 30000);
});
