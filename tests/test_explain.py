import unittest
from unittest.mock import patch
from gotchi_explain import explain

class ExplainTests(unittest.TestCase):
    def test_generation_timeout_is_actionable(self):
        from unittest.mock import Mock
        client = Mock()
        client.open.side_effect = TimeoutError('timed out')
        with patch('gotchi_explain.snapshot', return_value={'status': 'running'}), patch('gotchi_explain.trends', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'timed out after 180 seconds'):
                explain(opener=client)
        self.assertEqual(client.open.call_args.kwargs['timeout'], 180)
        import json
        payload = json.loads(client.open.call_args.args[0].data)
        self.assertIs(payload['think'], False)

    def test_offline_monitor_rejected(self):
        with patch("gotchi_explain.snapshot", return_value={"status": "stale"}):
            with self.assertRaises(ValueError):
                explain()
    def test_model_validation(self):
        with self.assertRaises(ValueError):
            explain("bad model")
