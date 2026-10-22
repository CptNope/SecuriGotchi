import io
import json
import unittest
from unittest.mock import patch
from gotchi_ai_ops import parse_models, local_models, analyze, diagnostics


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self.payload[:size]


class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.url = None

    def open(self, request, timeout):
        self.url = request.full_url
        return FakeResponse(self.payload)


class AIOpsTests(unittest.TestCase):
    def test_filters_untrusted_model_names(self):
        source = {
            "models": [
                {"name": "llama3:8b"}, {"name": "qwen3:4b"},
                {"name": "bad\nname"}, {"name": "../bad"},
                {"name": "llama3:8b"}, {"name": 123}
            ]
        }
        names = parse_models(json.dumps(source))
        self.assertEqual(names, ["llama3:8b", "qwen3:4b"])

    def test_localhost_only_model_lookup(self):
        client = FakeOpener(b'{"models":[{"name":"qwen3:4b"}]}')
        self.assertEqual(local_models(opener=client), ["qwen3:4b"])
        self.assertEqual(client.url, "http://127.0.0.1:11434/api/tags")

    def test_oversized_model_list_rejected(self):
        with self.assertRaises(RuntimeError):
            local_models(opener=FakeOpener(b"x" * (128*1024 + 2)))

    def test_refuses_offline_collector(self):
        with patch("gotchi_ai_ops.snapshot", return_value={"status": "stale"}):
            with self.assertRaisesRegex(ValueError, "collector"):
                analyze("llama3:8b")

    def test_refuses_noninstalled_model(self):
        with patch("gotchi_ai_ops.snapshot", return_value={"status": "running"}):
            with patch("gotchi_ai_ops.local_models", return_value=["qwen3:4b"]):
                with self.assertRaisesRegex(ValueError, "not installed"):
                    analyze("llama3:8b")

    def test_requires_explicit_local_model(self):
        with patch("gotchi_ai_ops.snapshot", return_value={"status": "running"}):
            with patch("gotchi_ai_ops.local_models", return_value=["qwen3:4b"]):
                with patch("gotchi_ai_ops.explain", return_value={"analysis":"Test"}) as mock:
                    self.assertEqual(analyze("qwen3:4b")["analysis"], "Test")
                    mock.assert_called_once_with(model="qwen3:4b")

    def test_diagnostics_no_event_details(self):
        with patch("gotchi_ai_ops.snapshot", return_value={
            "status": "running", "source_status": "available", "mood": "calm",
            "alerts": [{"detail": "SECRET"}],
        }):
            with patch("gotchi_ai_ops.local_models", return_value=["qwen3:4b"]):
                data = diagnostics()
        self.assertNotIn("SECRET", str(data))
        self.assertEqual(data["ollama"], "ready")
