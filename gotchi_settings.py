"""Validated, versioned local settings. Credentials are never exported here."""
from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import sqlite3
import stat
import time

from gotchi_auth import data_dir


def field(group, label, default, kind, help='', **kwargs):
    return dict(group=group, label=label, default=default, type=kind, help=help, **kwargs)


FIELDS = {
    'monitor_enabled': field('Monitoring', 'Collect monitoring samples', True, 'boolean', 'Pause/resume the separately running collector. This page does not start OS processes.'),
    'interval': field('Monitoring', 'Poll interval (seconds)', 60, 'integer', min=10, max=3600),
    'source': field('Monitoring', 'Security event source', 'auto', 'select', options=['auto', 'file', 'journal', 'windows', 'macos']),
    'auth_log': field('Monitoring', 'SSH text log path', '', 'string', 'Optional absolute path to a regular file you may read. Environment override takes precedence.', max_length=1024),
    'network_enabled': field('Wi-Fi & discovery', 'Monitor Wi-Fi connection health', False, 'boolean', 'Windows adapter; unavailable OS fields remain unknown.'),
    'discovery_enabled': field('Wi-Fi & discovery', 'Discover local devices', False, 'boolean', 'Active ping probes only. Requires authorization for the selected local subnet.'),
    'discovery_cidr': field('Wi-Fi & discovery', 'Authorized IPv4 subnet', '', 'string', 'Directly connected RFC1918 /24–/30, for example 192.168.0.0/24.', max_length=32),
    'discovery_interval': field('Wi-Fi & discovery', 'Discovery interval (seconds)', 300, 'integer', min=300, max=86400),
    'wifi_signal_warning': field('Wi-Fi & discovery', 'Weak signal below (%)', 30, 'integer', min=1, max=100),
    'failure_high': field('Alert rules', 'Failures from one IP for high severity', 5, 'integer', min=2, max=1000),
    'failure_critical': field('Alert rules', 'Failures from one IP for critical severity', 10, 'integer', min=3, max=10000),
    'failure_window': field('Alert rules', 'Failure observation window (seconds)', 300, 'integer', min=30, max=3600),
    'alert_cooldown': field('Alert rules', 'Alert cooldown (seconds)', 900, 'integer', 'Severity escalation bypasses cooldown.', min=0, max=86400),
    'usage_warning': field('Alert rules', 'Disk/memory warning (%)', 80, 'integer', min=1, max=99),
    'usage_high': field('Alert rules', 'Disk/memory high (%)', 90, 'integer', min=2, max=100),
    'usage_critical': field('Alert rules', 'Disk/memory critical (%)', 97, 'integer', min=3, max=100),
    'event_retention_days': field('Storage & privacy', 'Event/health retention (days)', 7, 'integer', 'Lowering retention permanently prunes older observations on the next poll.', min=1, max=90),
    'alert_retention_days': field('Storage & privacy', 'Alert retention (days)', 30, 'integer', min=1, max=365),
    'device_retention_days': field('Storage & privacy', 'Device identity retention (days)', 30, 'integer', 'Expired identities may be flagged as new when seen again.', min=1, max=365),
    'notifications_enabled': field('Notifications', 'Enable local desktop notifications', False, 'boolean', 'Linux graphical session with notify-send and D-Bus only. No email or cloud notifications.'),
    'notification_level': field('Notifications', 'Minimum notification severity', 'high', 'select', options=['warning', 'high', 'critical']),
    'ai_enabled': field('Local AI', 'Enable advisory Ollama explanations', True, 'boolean', 'Loopback only. No automatic generation or security actions.'),
    'ai_model': field('Local AI', 'Preferred local model', '', 'string', 'Choose an installed model below, or enter its exact name. Blank uses existing CLI config / dashboard selection.', max_length=80),
    'ai_temperature': field('Local AI', 'Temperature', 0.2, 'number', min=0, max=1),
    'ai_timeout': field('Local AI', 'Generation timeout (seconds)', 180, 'integer', min=10, max=300),
    'ai_tokens': field('Local AI', 'Maximum generated tokens', 500, 'integer', min=100, max=2000),
    'ai_thinking': field('Local AI', 'Allow model thinking', False, 'boolean', 'Thinking models can consume the token budget without producing an answer.'),
    'ai_system_prompt': field('Local AI', 'CLI chat system prompt', 'You are a helpful cybersecurity assistant.', 'text', 'Used by interactive CLI chat. Incident explanations retain their fixed advisory safety instructions.', max_length=2000),
    'refresh_seconds': field('Dashboard', 'Auto-refresh interval (seconds)', 30, 'integer', 'Applies after reloading the dashboard.', min=10, max=300),
    'session_minutes': field('Account & session', 'Session lifetime (minutes)', 15, 'integer', 'Applied to requests immediately; existing sessions renew on activity.', min=5, max=120),
}


def defaults():
    return {key: spec['default'] for key, spec in FIELDS.items()}


@contextmanager
def connection():
    path = data_dir() / 'settings.sqlite3'
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or (os.name != 'nt' and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077)):
            raise RuntimeError('Settings database must be a private user-owned regular file')
    finally:
        os.close(fd)
    with closing(sqlite3.connect(path, timeout=5)) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, payload TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS collector_config (id INTEGER PRIMARY KEY CHECK(id=1), ts INTEGER NOT NULL, payload TEXT NOT NULL)')
        yield conn


def load_document():
    # No settings yet: avoid creating state simply to read defaults.
    if not (data_dir() / 'settings.sqlite3').exists():
        return {'revision': 0, 'values': defaults()}
    with connection() as conn:
        row = conn.execute('SELECT revision,payload FROM settings WHERE id=1').fetchone()
    if row is None:
        return {'revision': 0, 'values': defaults()}
    values = defaults()
    values.update(json.loads(row[1]))
    return {'revision': row[0], 'values': values}


def load():
    return load_document()['values']


def validate(values):
    if not isinstance(values, dict) or set(values) != set(FIELDS):
        raise ValueError('Provide exactly the supported settings fields')
    for key, spec in FIELDS.items():
        value = values[key]
        kind = spec['type']
        if kind == 'boolean':
            valid = type(value) is bool
        elif kind == 'integer':
            valid = type(value) is int and spec['min'] <= value <= spec['max']
        elif kind == 'number':
            valid = type(value) in (int, float) and spec['min'] <= value <= spec['max']
        else:
            valid = isinstance(value, str) and len(value) <= spec.get('max_length', 100) and '\x00' not in value
            if kind == 'select':
                valid = valid and value in spec['options']
        if not valid:
            raise ValueError('Invalid value for ' + spec['label'])
    if not values['usage_warning'] < values['usage_high'] < values['usage_critical']:
        raise ValueError('Disk/memory thresholds must increase: warning < high < critical')
    if values['failure_high'] >= values['failure_critical']:
        raise ValueError('Critical failure threshold must exceed high threshold')
    if values['discovery_enabled'] and not values['network_enabled']:
        raise ValueError('Enable Wi-Fi/network monitoring before discovery')
    if values['auth_log'] and not Path(values['auth_log']).is_absolute():
        raise ValueError('SSH log path must be absolute')
    if values['auth_log'] and Path(values['auth_log']).exists() and not Path(values['auth_log']).is_file():
        raise ValueError('SSH log path must identify a regular file')
    if values['ai_model']:
        from gotchi_ai_ops import valid_model_name
        if not valid_model_name(values['ai_model']):
            raise ValueError('Invalid preferred model name')
    if values['notifications_enabled']:
        import platform
        import shutil
        if platform.system() != 'Linux' or not shutil.which('notify-send'):
            raise ValueError('Desktop notifications require Linux and notify-send')
    if values['discovery_enabled']:
        from gotchi_network import validate_network
        validate_network(values['discovery_cidr'])


class ConflictError(ValueError):
    pass


def save(values, revision, authorize_discovery=False):
    validate(values)
    if type(revision) is not int or revision < 0:
        raise ValueError('Invalid settings revision')
    with connection() as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT revision,payload FROM settings WHERE id=1').fetchone()
        current_revision = row[0] if row else 0
        old = json.loads(row[1]) if row else defaults()
        if current_revision != revision:
            raise ConflictError('Settings changed in another tab. Reload before saving.')
        if values['discovery_enabled'] and (not old['discovery_enabled'] or values['discovery_cidr'] != old['discovery_cidr']) and authorize_discovery is not True:
            raise ValueError('Confirm you own or may inspect the discovery subnet')
        conn.execute('INSERT OR REPLACE INTO settings VALUES (1,?,?)', (revision + 1, json.dumps(values)))
    return {'revision': revision + 1, 'values': values}


def record_runtime(overrides, effective):
    with connection() as conn, conn:
        conn.execute('INSERT OR REPLACE INTO collector_config VALUES (1,?,?)', (int(time.time()), json.dumps({'overrides': overrides, 'effective': effective})))


def runtime():
    with connection() as conn:
        row = conn.execute('SELECT ts,payload FROM collector_config WHERE id=1').fetchone()
    return dict(json.loads(row[1]), sampled_at=row[0]) if row else None
