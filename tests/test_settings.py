from argparse import Namespace
from contextlib import closing
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

import gotchi_settings as settings
from gotchi_webui import app


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'SECURIGOTCHI_DATA_DIR': self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        from gotchi_auth import create_admin
        create_admin('Disposable-current-password')
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session.update(admin='admin', csrf='settings-csrf', auth_epoch=0)
        self.headers = {'X-CSRF-Token': 'settings-csrf'}
        from gotchi_webui import FAILED
        FAILED.clear()

    def save(self, values, revision=0, **kwargs):
        return self.client.post('/api/settings', json={'values': values, 'revision': revision, **kwargs}, headers=self.headers)

    def test_auth_csrf_and_page(self):
        self.assertEqual(app.test_client().get('/api/settings').status_code, 401)
        self.assertEqual(self.client.post('/api/settings', json={}).status_code, 403)
        self.assertEqual(self.client.get('/settings').status_code, 200)
        self.assertNotIn('password_hash', self.client.get('/api/settings').get_data(as_text=True))

    def test_atomic_save_and_conflicting_tabs(self):
        values = settings.defaults()
        values.update(interval=45, ai_temperature=0.4)
        self.assertEqual(self.save(values).status_code, 200)
        self.assertEqual(settings.load()['interval'], 45)
        self.assertEqual(self.save(values).status_code, 409)
        self.assertEqual(settings.load_document()['revision'], 1)
        invalid = {**values, 'usage_critical': 70}
        self.assertEqual(self.save(invalid, 1).status_code, 400)
        self.assertEqual(settings.load()['usage_critical'], 97)

    def test_rejects_wrong_types_unknown_fields_and_thresholds(self):
        for changes in ({'interval': True}, {'interval': 0}, {'ai_temperature': float('nan')},
                        {'monitor_enabled': 'false'}, {'source': 'shell'}, {'extra': 1},
                        {'auth_log': '../private'}, {'failure_high': 20}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                settings.validate({**settings.defaults(), **changes})

    def test_discovery_requires_local_scope_and_new_consent(self):
        values = {**settings.defaults(), 'network_enabled': True, 'discovery_enabled': True, 'discovery_cidr': '192.168.0.0/24'}
        with patch('gotchi_network.validate_network'):
            self.assertEqual(self.save(values).status_code, 400)
            self.assertEqual(self.save(values, authorize_discovery=True).status_code, 200)
            self.assertEqual(self.save(values, 1).status_code, 200)
            values['discovery_cidr'] = '192.168.1.0/24'
            self.assertEqual(self.save(values, 2).status_code, 400)
        with patch('gotchi_network.validate_network', side_effect=ValueError('Not directly connected')):
            self.assertEqual(self.save(values, 2, authorize_discovery=True).status_code, 400)

    def test_cli_overrides_and_settings_aware_options(self):
        from gotchi_monitor import collector_options
        values = {**settings.defaults(), 'interval': 25, 'network_enabled': True}
        self.assertEqual(collector_options(Namespace(), values)['interval'], 25)
        self.assertEqual(collector_options(Namespace(interval=90), values)['interval'], 90)
        self.assertTrue(collector_options(Namespace(), values)['network_enabled'])

    def test_saved_thresholds_affect_actual_health_alerts(self):
        from gotchi_monitor import run_once, overview
        values = {**settings.defaults(), 'usage_warning': 60, 'usage_high': 70, 'usage_critical': 90}
        settings.save(values, 0)
        path = Path(self.temp.name) / 'fixture.log'
        path.touch()
        run_once(now=1000, log_path=str(path), health={'disk_percent': 75, 'memory_percent': 10, 'load_avg': None})
        self.assertEqual(overview(now=1000)['alerts'][0]['severity'], 'high')
        settings.save({**values, 'monitor_enabled': False}, 1)
        self.assertEqual(overview(now=1000)['status'], 'paused')

    def test_disabled_ai_prevents_generation(self):
        from gotchi_explain import explain
        settings.save({**settings.defaults(), 'ai_enabled': False}, 0)
        with self.assertRaisesRegex(ValueError, 'disabled'):
            explain()

    def test_custom_ai_values_reach_request(self):
        from gotchi_explain import explain
        from unittest.mock import Mock
        import json
        settings.save({**settings.defaults(), 'ai_timeout': 75, 'ai_tokens': 900, 'ai_thinking': True}, 0)
        opener = Mock()
        opener.open.side_effect = TimeoutError()
        with patch('gotchi_explain.snapshot', return_value={'status': 'running'}), patch('gotchi_explain.trends', return_value={}):
            with self.assertRaisesRegex(RuntimeError, '75 seconds'):
                explain(opener=opener)
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 75)
        payload = json.loads(opener.open.call_args.args[0].data)
        self.assertTrue(payload['think'])
        self.assertEqual(payload['options']['num_predict'], 900)

    def test_password_change_checks_current_and_invalidates_other_sessions(self):
        from gotchi_auth import verify_admin
        other = app.test_client()
        with other.session_transaction() as session:
            session.update(admin='admin', csrf='other', auth_epoch=0)
        payload = {'current': 'wrong', 'password': 'Disposable-new-password', 'confirm': 'Disposable-new-password'}
        self.assertEqual(self.client.post('/api/settings/password', json=payload, headers=self.headers).status_code, 400)
        payload['current'] = 'Disposable-current-password'
        response = self.client.post('/api/settings/password', json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(verify_admin('admin', 'Disposable-new-password'))
        self.assertFalse(verify_admin('admin', 'Disposable-current-password'))
        self.assertEqual(other.get('/api/settings').status_code, 401)
        self.assertEqual(self.client.get('/api/settings').status_code, 401)

    def test_password_changes_require_csrf_and_are_rate_limited(self):
        self.assertEqual(self.client.post('/api/settings/password', json={}).status_code, 403)
        for _ in range(5):
            self.assertEqual(self.client.post('/api/settings/password', json={}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/settings/password', json={}, headers=self.headers).status_code, 429)
