"""SDK v2 integration; runs only when optional MCP dependency is installed."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from gotchi_mcp import create_server

try:
    from mcp import Client, StdioServerParameters
except ImportError:
    Client = None
    StdioServerParameters = None


@unittest.skipIf(Client is None, "optional MCP v2 SDK not installed")
class MCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_in_memory_registration_and_redaction(self):
        fake = {
            "status": "running",
            "mood": "watchful",
            "source_status": "available",
            "counts": {"failed": 2, "accepted": 1, "invalid_user": 0},
            "health": {"disk_percent": 20},
            "alerts": [{"severity": "high", "title": "Repeated SSH login failures"}],
            "notice": "Sampled",
        }
        with patch("gotchi_mcp.snapshot", return_value=fake), patch(
            "gotchi_mcp.trends", return_value=[{"hour": "2026-10-22T12:00Z", "failed": 2}]
        ):
            async with Client(create_server(), raise_exceptions=True) as client:
                listing = await client.list_tools()
                self.assertEqual(
                    {tool.name for tool in listing.tools},
                    {"security_status", "security_trends"},
                )
                status = await client.call_tool("security_status", {})
                self.assertFalse(status.is_error)
                self.assertIn("running", str(status))
                trend = await client.call_tool("security_trends", {"hours": 1})
                self.assertFalse(trend.is_error)
                self.assertIn("failed", str(trend))

    async def test_real_stdio_subprocess(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ)
            env.update({
                "SECURIGOTCHI_MCP_ENABLE": "1",
                "SECURIGOTCHI_DATA_DIR": directory,
            })
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(root / "gotchi_mcp.py")],
                env=env,
                cwd=str(root),
            )
            async with Client(params, raise_exceptions=True) as client:
                listing = await client.list_tools()
                self.assertEqual(
                    {tool.name for tool in listing.tools},
                    {"security_status", "security_trends"},
                )
                response = await client.call_tool("security_status", {})
                self.assertFalse(response.is_error)
                self.assertIn("not_started", str(response))
