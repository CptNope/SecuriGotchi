"""Disposable local smoke check; no scans, native probes or model calls."""
import http.cookiejar
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request


def main():
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent / '.securigotchi') as folder:
        os.environ['SECURIGOTCHI_DATA_DIR'] = folder
        from gotchi_monitor import run_once, overview
        log = Path(folder) / 'fixture.log'
        log.write_text('', encoding='utf-8')
        assert run_once(log_path=str(log))['events_added'] == 0
        line = 'fixture sshd[123]: Failed password for invalid user demo from 192.0.2.10 port 2222 ssh2\n'
        for severity in ('high', 'critical'):
            with log.open('a', encoding='utf-8') as handle:
                handle.write(line * 5)
            assert run_once(log_path=str(log))['events_added'] == 5
            assert any(a['category'] == 'ssh' and a['severity'] == severity for a in overview()['alerts'])
        print('PASS: file baseline, five failures, high alert, critical escalation')

        from gotchi_auth import create_admin
        password = secrets.token_urlsafe(24)
        create_admin(password)
        from gotchi_webui import app
        from werkzeug.serving import make_server
        server = make_server('127.0.0.1', 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        try:
            try:
                client.open(base + '/api/monitor')
                raise AssertionError('Unauthenticated API allowed')
            except urllib.error.HTTPError as error:
                assert error.code == 401
            page = client.open(base + '/login').read().decode()
            token = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
            body = urllib.parse.urlencode({'csrf': token, 'username': 'admin', 'password': password}).encode()
            response = client.open(base + '/login', body)
            assert response.status == 200 and response.url == base + '/'
            for path in ('/api/monitor', '/api/brain', '/api/trends', '/api/network'):
                assert client.open(base + path).status == 200
            try:
                client.open(base + '/api/ai/explain', b'{}')
                raise AssertionError('CSRF bypass')
            except urllib.error.HTTPError as error:
                assert error.code == 403
            print('PASS: real loopback HTTP, unauthenticated denial, CSRF login, authenticated APIs, CSRF denial')
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == '__main__':
    main()
