"""Opt-in Windows Wi-Fi health and bounded IPv4 discovery. No port scans."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import ipaddress
import json
import platform
import re
import subprocess
import time

from gotchi_auth import data_dir


def command(argv, timeout=8):
    result = subprocess.run(argv, capture_output=True, text=True, errors='replace',
                            timeout=timeout, shell=False)
    if result.returncode:
        raise RuntimeError('OS network reader unavailable')
    if len(result.stdout) > 131072:
        raise RuntimeError('OS network response too large')
    return result.stdout


def parse_wlan(text):
    """English netsh output only; never interpret missing fields as disconnected."""
    values = {}
    for line in text.splitlines():
        if ':' in line:
            key, value = line.strip().split(':', 1)
            values.setdefault(key.strip().lower(), value.strip())
    state = values.get('state', '').lower()
    if state not in ('connected', 'disconnected'):
        return {'status': 'unavailable', 'detail': 'Wi-Fi details unavailable (permissions, language or adapter support)'}
    signal = values.get('signal', '')
    match = re.fullmatch(r'(\d{1,3})%', signal)
    percent = int(match[1]) if match and int(match[1]) <= 100 else None
    return {'status': state, 'interface': values.get('name'),
            'ssid': values.get('ssid') if state == 'connected' else None,
            'signal_percent': percent if state == 'connected' else None,
            'authentication': values.get('authentication') if state == 'connected' else None,
            'detail': 'Wi-Fi radio details sampled locally'}


def interfaces():
    import psutil
    result = []
    stats = psutil.net_if_stats()
    for name, addresses in psutil.net_if_addrs().items():
        for addr in addresses:
            try:
                ip = ipaddress.ip_address(addr.address)
                if ip.version != 4 or not addr.netmask or ip.is_loopback or ip.is_link_local:
                    continue
                net = ipaddress.ip_network(f'{ip}/{addr.netmask}', strict=False)
            except ValueError:
                continue
            result.append({'interface': name, 'ip': str(ip), 'cidr': str(net),
                           'up': bool(stats.get(name) and stats[name].isup)})
    return result


def wifi_health():
    if platform.system() != 'Windows':
        return {'status': 'unsupported', 'detail': 'Wi-Fi radio adapter currently supports Windows only'}
    try:
        result = parse_wlan(command(['netsh', 'wlan', 'show', 'interfaces']))
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        result = {'status': 'unavailable', 'detail': 'Windows Wi-Fi details unavailable; check OS access/location settings'}
    try:
        candidates = interfaces()
        matching = [a for a in candidates if a['interface'] == result.get('interface')]
        if not matching:
            matching = [a for a in candidates if a['interface'].lower() in ('wi-fi', 'wifi', 'wireless network connection')]
        if len(matching) == 1:
            result.update(matching[0])
            if result['status'] == 'unavailable':
                result['detail'] += '; interface/IP available, SSID/signal/security unknown'
    except (ImportError, OSError):
        pass
    return result


def validate_network(cidr, adapters=None):
    net = ipaddress.ip_network(cidr, strict=True)
    private = [ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
    if net.version != 4 or net.prefixlen < 24 or net.prefixlen > 30 or not any(net.subnet_of(n) for n in private):
        raise ValueError('Discovery requires an RFC1918 IPv4 subnet between /24 and /30')
    adapters = interfaces() if adapters is None else adapters
    if not any(a['up'] and ipaddress.ip_address(a['ip']) in net and
               net.subnet_of(ipaddress.ip_network(a['cidr'])) for a in adapters):
        raise ValueError('Discovery subnet must match an active directly connected interface')
    return net


def ping(ip):
    try:
        result = subprocess.run(['ping', '-n', '1', '-w', '700', str(ip)],
                                capture_output=True, timeout=2, shell=False)
        # Windows can deny the IP driver entirely in a restricted runtime.
        if b'Unable to contact IP driver' in result.stdout or b'General failure' in result.stdout:
            return None
        # Windows may exit 0 for an ICMP destination-unreachable response.
        return result.returncode == 0 and re.search(rb'\bTTL=\d+', result.stdout, re.IGNORECASE) is not None
    except OSError:
        return None
    except subprocess.TimeoutExpired:
        return False


def parse_arp(text, network):
    found = {}
    for line in text.splitlines():
        match = re.match(r'\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+(dynamic|static)\s*$', line)
        if not match:
            continue
        ip, mac, kind = match.groups()
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            continue
        mac = mac.lower().replace('-', ':')
        if address in network and address not in (network.network_address, network.broadcast_address) and mac not in ('ff:ff:ff:ff:ff:ff', '00:00:00:00:00:00'):
            found[ip] = mac
    return found


def discover(cidr):
    if platform.system() != 'Windows':
        raise ValueError('Active discovery currently supports Windows only')
    network = validate_network(cidr)
    targets = list(network.hosts())  # At most 254; no DNS lookups or port probes.
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(ping, targets))
        reachable = [str(ip) for ip, responds in zip(targets, results) if responds]
    if all(result is None for result in results):
        raise RuntimeError('Windows denied ping access. Run the collector from a regular local PowerShell terminal.')
    try:
        neighbors = parse_arp(command(['arp', '-a']), network)
        neighbor_status = 'available'
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        neighbors, neighbor_status = {}, 'unavailable'
    return {'scope': str(network), 'status': 'sampled', 'neighbor_status': neighbor_status,
            'devices': [{'ip': ip, 'mac': neighbors.get(ip), 'evidence': 'ping_reply'} for ip in reachable],
            'detail': 'Only ping responders listed. Quiet/firewalled devices may be missed; neighbor entries alone do not prove presence.'}


def collect(conn, now, emit, active_cidr=None):
    """Called inside the monitor transaction; first samples establish baselines."""
    pending_alerts = []
    emit_alert = emit
    emit = lambda *args: pending_alerts.append(args)
    schema = '''
        CREATE TABLE IF NOT EXISTS network_state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS network_devices (
            scope TEXT NOT NULL, identity TEXT NOT NULL, ip TEXT NOT NULL, mac TEXT,
            first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
            PRIMARY KEY(scope,identity));
        CREATE TABLE IF NOT EXISTS network_baselines (scope TEXT PRIMARY KEY);
    '''
    for statement in schema.split(';'):
        if statement.strip():
            conn.execute(statement)
    previous = conn.execute('SELECT payload FROM network_state WHERE id=1').fetchone()
    old = json.loads(previous[0]) if previous else {}
    wifi = wifi_health()
    prior = old.get('wifi', {})
    if wifi['status'] in ('connected', 'disconnected') and prior.get('status') in ('connected', 'disconnected'):
        if wifi['status'] != prior['status']:
            emit(conn, now, 'network', 'warning', 'Wi-Fi connection changed',
                 'Wi-Fi is now ' + wifi['status'], 'wifi:connection')
        elif wifi.get('ssid') and prior.get('ssid') and wifi['ssid'] != prior['ssid']:
            emit(conn, now, 'network', 'warning', 'Wi-Fi network changed',
                 'The connected Wi-Fi network name changed; review locally.', 'wifi:network')
    if wifi.get('signal_percent') is not None and wifi['signal_percent'] < 30:
        emit(conn, now, 'network', 'warning', 'Weak Wi-Fi signal',
             'Signal strength is below 30%.', 'wifi:signal')
    if (wifi.get('authentication') or '').lower() in ('open', 'shared', 'wep'):
        emit(conn, now, 'network', 'high', 'Weak Wi-Fi authentication',
             'Wi-Fi reports open or legacy authentication; review router settings.', 'wifi:security')
    discovery = {'status': 'disabled', 'devices': [], 'detail': 'Active discovery is off; enable an authorized subnet in the collector CLI.'}
    if active_cidr:
        previous_discovery = old.get('discovery', {})
        if previous_discovery.get('scope') == active_cidr and now - previous_discovery.get('sampled_at', 0) < 300:
            discovery = previous_discovery
        else:
            try:
                discovery = discover(active_cidr)
                baseline = conn.execute('SELECT 1 FROM network_baselines WHERE scope=?', (active_cidr,)).fetchone()
                for item in discovery['devices']:
                    identity = item['mac'] or item['ip']
                    # Upgrade an IP-only observation when MAC access becomes available.
                    known = conn.execute('SELECT 1 FROM network_devices WHERE scope=? AND (identity=? OR (ip=? AND mac IS NULL))',
                                         (active_cidr, identity, item['ip'])).fetchone()
                    if baseline and not known:
                        emit(conn, now, 'network', 'warning', 'Newly observed network device',
                             'A device responded on the authorized subnet. Review the network panel; this is not evidence of an intruder.',
                             'network:new:' + active_cidr + ':' + identity)
                    conn.execute('INSERT INTO network_devices VALUES (?,?,?,?,?,?) ON CONFLICT(scope,identity) DO UPDATE SET ip=excluded.ip,mac=excluded.mac,last_seen=excluded.last_seen',
                                 (active_cidr, identity, item['ip'], item['mac'], now, now))
                conn.execute('INSERT OR IGNORE INTO network_baselines VALUES (?)', (active_cidr,))
                discovery['sampled_at'] = now
                discovery['baseline'] = not bool(baseline)
            except (ValueError, OSError, RuntimeError) as error:
                discovery = {'status': 'unavailable', 'scope': active_cidr, 'devices': [], 'detail': str(error), 'sampled_at': now}
    conn.execute('DELETE FROM network_devices WHERE last_seen < ?', (now - 30 * 86400,))
    payload = {'sampled_at': now, 'wifi': wifi, 'discovery': discovery}
    conn.execute('INSERT OR REPLACE INTO network_state VALUES (1,?)', (json.dumps(payload),))
    for args in pending_alerts:
        emit_alert(*args)


def overview():
    path = data_dir() / 'monitor.sqlite3'
    if not path.exists():
        return {'status': 'not_started', 'wifi': {}, 'discovery': {'status': 'disabled', 'devices': []}}
    import sqlite3
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)) as conn:
        try:
            row = conn.execute('SELECT payload FROM network_state WHERE id=1').fetchone()
        except sqlite3.OperationalError:
            row = None
    if row is None:
        return {'status': 'disabled', 'wifi': {}, 'discovery': {'status': 'disabled', 'devices': []}}
    result = json.loads(row[0])
    result['status'] = 'current' if time.time() - result['sampled_at'] <= 180 else 'stale'
    return result
