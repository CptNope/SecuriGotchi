document.addEventListener('DOMContentLoaded', () => {
  const el = id => document.getElementById(id);
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let documentState;
  let dirty = false;
  const controls = new Map();
  const groups = ['Monitoring', 'Wi-Fi & discovery', 'Alert rules', 'Storage & privacy', 'Notifications', 'Local AI', 'Dashboard', 'Account & session'];
  async function api(url, options = {}) {
    const response = await fetch(url, options);
    if (response.status === 401) { location.assign('/login'); throw new Error('Sign in again'); }
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Request failed');
    return body;
  }
  function message(text) { el('settings-message').textContent = text; }
  function changed() { dirty = true; el('save-label').textContent = 'Unsaved changes'; message('Changes are not active until saved.'); }
  function readValues() {
    const values = {};
    controls.forEach((control, key) => {
      const kind = documentState.fields[key].type;
      values[key] = kind === 'boolean' ? control.checked :
        ['integer', 'number'].includes(kind) ? (control.value.trim() ? Number(control.value) : null) : control.value;
    });
    return values;
  }
  function fill(values) {
    controls.forEach((control, key) => {
      if (documentState.fields[key].type === 'boolean') control.checked = values[key];
      else control.value = values[key];
    });
  }
  function render(data) {
    documentState = data;
    controls.clear();
    el('settings-fields').replaceChildren();
    el('settings-nav').replaceChildren();
    groups.forEach((group, index) => {
      const section = document.createElement('section');
      section.className = 'panel'; section.id = 'settings-group-' + index;
      const heading = document.createElement('h2'); heading.textContent = group; section.appendChild(heading);
      const link = document.createElement('a'); link.href = '#' + section.id; link.textContent = group; el('settings-nav').appendChild(link);
      data.field_order.map(key => [key, data.fields[key]]).filter(([, spec]) => spec.group === group).forEach(([key, spec]) => {
        const wrapper = document.createElement('div'); wrapper.className = 'setting-field';
        const label = document.createElement('label'); label.htmlFor = 'setting-' + key; label.textContent = spec.label;
        const control = document.createElement(spec.type === 'select' ? 'select' : spec.type === 'text' ? 'textarea' : 'input');
        control.id = 'setting-' + key;
        if (spec.type === 'select') spec.options.forEach(value => control.add(new Option(value, value)));
        else if (spec.type === 'boolean') control.type = 'checkbox';
        else if (['integer', 'number'].includes(spec.type)) { control.type = 'number'; control.min = spec.min; control.max = spec.max; control.step = spec.type === 'number' ? '0.1' : '1'; control.required = true; }
        else { if (spec.type !== 'text') control.type = 'text'; control.maxLength = spec.max_length || 100; }
        if (spec.type === 'boolean') { label.className = 'checklabel'; label.prepend(control); wrapper.appendChild(label); }
        else wrapper.append(label, control);
        if (spec.help) { const hint = document.createElement('p'); hint.className = 'hint'; hint.id = control.id + '-help'; hint.textContent = spec.help; control.setAttribute('aria-describedby', hint.id); wrapper.appendChild(hint); }
        control.addEventListener('input', changed);
        controls.set(key, control); section.appendChild(wrapper);
      });
      if (group === 'Local AI') {
        const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Check Ollama and choose an installed model';
        const output = document.createElement('p'); output.className = 'hint'; output.setAttribute('role', 'status');
        button.addEventListener('click', async () => {
          button.disabled = true;
          try {
            const diagnostics = await api('/api/ai/diagnostics');
            output.textContent = 'Ollama: ' + diagnostics.ollama + ' · Collector: ' + diagnostics.collector;
            section.querySelector('[data-model-picker]')?.remove();
            if (diagnostics.models.length) {
              const label = document.createElement('label'); label.dataset.modelPicker = 'true'; label.textContent = 'Use an installed model';
              const picker = document.createElement('select'); picker.add(new Option('Choose a model…', ''));
              diagnostics.models.forEach(name => picker.add(new Option(name, name)));
              picker.addEventListener('change', () => { if (picker.value) { controls.get('ai_model').value = picker.value; changed(); } });
              label.appendChild(picker); section.appendChild(label);
            }
          } catch (error) { output.textContent = error.message; }
          finally { button.disabled = false; }
        });
        section.append(button, output);
      }
      el('settings-fields').appendChild(section);
    });
    [['Configuration files', 'settings-config'], ['Change password', 'settings-password'], ['Installation', 'settings-deployment']].forEach(([text, id]) => {
      const link = document.createElement('a'); link.href = '#' + id; link.textContent = text; el('settings-nav').appendChild(link);
    });
    fill(data.values);
    el('platform-status').textContent = 'Platform: ' + data.capabilities.os + ' · Wi-Fi adapter: ' + (data.capabilities.wifi ? 'Windows; OS access required' : 'not supported') + ' · Desktop notifications: ' + (data.capabilities.notifications ? 'available; graphical session required' : 'unavailable');
    const runtime = data.collector;
    const age = runtime ? (Date.now() / 1000 - runtime.sampled_at) : Infinity;
    el('runtime-status').textContent = runtime ? (age < Math.max(180, runtime.effective.interval * 3) ? 'Collector last checked settings ' : 'Collector configuration is stale; last check ') + new Date(runtime.sampled_at * 1000).toLocaleString() : 'No settings-aware collector has checked in. Start gotchi_monitor.py watch without overrides.';
    el('runtime-details').textContent = runtime ? JSON.stringify(runtime, null, 2) : 'No runtime configuration yet.';
    el('deployment-values').replaceChildren();
    Object.entries(data.deployment).forEach(([key, value]) => {
      const term = document.createElement('dt'); term.textContent = key.replaceAll('_', ' ');
      const detail = document.createElement('dd'); detail.textContent = String(value); el('deployment-values').append(term, detail);
    });
    el('save-settings').disabled = false;
    el('save-label').textContent = 'Saved configuration · revision ' + data.revision;
    el('authorize-discovery').checked = false;
    dirty = false;
  }
  async function reload() {
    try { render(await api('/api/settings')); message('Configuration loaded. CLI flags and environment variables may override saved preferences.'); }
    catch (error) { message(error.message); }
  }
  el('settings-form').addEventListener('submit', async event => {
    event.preventDefault();
    el('save-settings').disabled = true;
    try {
      const result = await api('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
        body: JSON.stringify({revision: documentState.revision, values: readValues(), authorize_discovery: el('authorize-discovery').checked})});
      documentState.revision = result.revision; documentState.values = result.values;
      dirty = false; el('save-label').textContent = 'Saved · revision ' + result.revision;
      message(result.message); el('authorize-discovery').checked = false;
    } catch (error) { message(error.message); }
    finally { el('save-settings').disabled = false; }
  });
  el('reset-settings').addEventListener('click', () => { if (!documentState) return; fill(Object.fromEntries(Object.entries(documentState.fields).map(([key, spec]) => [key, spec.default]))); changed(); });
  el('reload-settings').addEventListener('click', reload);
  el('refresh-runtime').addEventListener('click', async () => {
    try { const data = await api('/api/settings'); el('runtime-details').textContent = JSON.stringify(data.collector, null, 2); el('runtime-status').textContent = data.collector ? 'Last settings check: ' + new Date(data.collector.sampled_at * 1000).toLocaleString() : 'No collector configuration yet.'; }
    catch (error) { message(error.message); }
  });
  el('export-settings').addEventListener('click', () => {
    if (!documentState) return;
    const blob = new Blob([JSON.stringify({format: 'securigotchi-settings', version: 1, values: readValues()}, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = 'securigotchi-settings.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  el('import-settings').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file || !documentState) return;
    try {
      if (file.size > 16000) throw new Error('Settings file is too large');
      const imported = JSON.parse(await file.text());
      if (imported.format !== 'securigotchi-settings' || imported.version !== 1 || !imported.values || Object.keys(imported.values).sort().join() !== Object.keys(documentState.fields).sort().join()) throw new Error('Unsupported settings export');
      fill(imported.values); changed(); message('Imported into form. Review all values and discovery consent before saving.');
    } catch (error) { message(error.message); }
    finally { event.target.value = ''; }
  });
  el('password-form').addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.target.querySelector('button'); button.disabled = true;
    try {
      const values = Object.fromEntries(new FormData(event.target));
      const data = await api('/api/settings/password', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify(values)});
      event.target.reset(); el('password-message').textContent = data.message; setTimeout(() => location.assign('/login'), 1800);
    } catch (error) { el('password-message').textContent = error.message; }
    finally { button.disabled = false; }
  });
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  reload();
});
