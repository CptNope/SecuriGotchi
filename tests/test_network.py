import json
import sqlite3
import unittest
from unittest.mock import patch

import gotchi_network as network


class NetworkTests(unittest.TestCase):
    def test_radio_fields_and_missing_state(self):
        parsed = network.parse_wlan('Name : Wi-Fi\nState : connected\nSSID : <untrusted>\nSignal : 42%\nAuthentication : WPA3-Personal')
        self.assertEqual(parsed['ssid'], '<untrusted>')
        self.assertEqual(parsed['signal_percent'], 42)
        self.assertEqual(network.parse_wlan('permission denied')['status'], 'unavailable')
        self.assertIsNone(network.parse_wlan('State : disconnected\nSignal : 50%')['signal_percent'])

    def test_restricts_discovery_to_connected_private_bounded_subnet(self):
        adapters = [{'ip': '192.168.0.2', 'cidr': '192.168.0.0/24', 'up': True}]
        self.assertEqual(str(network.validate_network('192.168.0.0/24', adapters)), '192.168.0.0/24')
        for cidr in ('8.8.8.0/24', '10.0.0.0/8', '192.168.1.0/24', '192.168.0.1/24', '127.0.0.0/24', '::/0', '192.168.0.0/31'):
            with self.subTest(cidr=cidr), self.assertRaises(ValueError):
                network.validate_network(cidr, adapters)

    def test_arp_filters_outside_subnet_and_broadcast(self):
        from ipaddress import ip_network
        text = '192.168.0.2  aa-bb-cc-dd-ee-02 dynamic\n8.8.8.8 aa-bb-cc-dd-ee-03 dynamic\n192.168.0.255 ff-ff-ff-ff-ff-ff static'
        self.assertEqual(network.parse_arp(text, ip_network('192.168.0.0/24')), {'192.168.0.2': 'aa:bb:cc:dd:ee:02'})

    def test_no_historical_device_alert_and_new_device_review(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        emit = unittest.mock.Mock()
        wifi = {'status': 'connected', 'ssid': 'home', 'signal_percent': 80}
        sample = {'status': 'sampled', 'scope': '192.168.0.0/24', 'devices': [{'ip': '192.168.0.2', 'mac': 'aa:bb:cc:dd:ee:02'}]}
        with patch.object(network, 'wifi_health', return_value=wifi), patch.object(network, 'discover', return_value=sample) as discover:
            network.collect(conn, 1000, emit, '192.168.0.0/24')
            emit.assert_not_called()
            network.collect(conn, 1060, emit, '192.168.0.0/24')
            self.assertEqual(discover.call_count, 1)
            sample = {**sample, 'devices': sample['devices'] + [{'ip': '192.168.0.3', 'mac': None}]}
            discover.return_value = sample
            network.collect(conn, 1301, emit, '192.168.0.0/24')
            self.assertEqual(emit.call_count, 1)
            self.assertEqual(emit.call_args.args[4], 'Newly observed network device')
            network.collect(conn, 1602, emit, '192.168.0.0/24')
            self.assertEqual(emit.call_count, 1)

    def test_failed_discovery_does_not_establish_baseline(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        with patch.object(network, 'wifi_health', return_value={'status': 'unavailable'}), patch.object(network, 'discover', side_effect=RuntimeError('denied')):
            network.collect(conn, 1000, unittest.mock.Mock(), '192.168.0.0/24')
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM network_baselines').fetchone()[0], 0)
        saved = json.loads(conn.execute('SELECT payload FROM network_state').fetchone()[0])
        self.assertEqual(saved['discovery']['status'], 'unavailable')

    def test_wifi_disconnect_low_signal_and_open_network(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        emit = unittest.mock.Mock()
        with patch.object(network, 'wifi_health', return_value={'status': 'connected', 'ssid': 'home', 'signal_percent': 80}):
            network.collect(conn, 1000, emit)
        with patch.object(network, 'wifi_health', return_value={'status': 'disconnected'}):
            network.collect(conn, 1060, emit)
        self.assertEqual(emit.call_args.args[4], 'Wi-Fi connection changed')
        with patch.object(network, 'wifi_health', return_value={'status': 'connected', 'signal_percent': 20, 'authentication': 'Open'}):
            network.collect(conn, 1120, emit)
        titles = [call.args[4] for call in emit.call_args_list]
        self.assertIn('Weak Wi-Fi signal', titles)
        self.assertIn('Weak Wi-Fi authentication', titles)

    def test_network_api_requires_authentication(self):
        from gotchi_webui import app
        with patch('gotchi_webui.has_admin', return_value=True):
            self.assertEqual(app.test_client().get('/api/network').status_code, 401)

    def test_denied_ping_does_not_report_empty_network_as_success(self):
        from ipaddress import ip_network
        with patch('gotchi_network.platform.system', return_value='Windows'), patch.object(network, 'validate_network', return_value=ip_network('192.168.0.0/30')), patch.object(network, 'ping', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'denied ping access'):
                network.discover('192.168.0.0/30')
