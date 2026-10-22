"""Opt-in, local, read-only MCP server for trusted desktop AI hosts.

The host starts this process over stdio. The host may send returned aggregates
to its selected model; do not configure an untrusted or cloud-enabled host if
those aggregates must remain private.
"""
import os

from gotchi_insights import snapshot, trends


def security_status() -> dict:
    """Read aggregated local security state; no source IPs or raw log messages."""
    return snapshot()


def security_trends(hours: int = 24) -> list[dict]:
    """Read hourly authentication counts for the last 1 to 72 hours."""
    return trends(hours)


def create_server():
    """Build the v2 MCP server without starting a transport on import."""
    from mcp.server import MCPServer

    server = MCPServer("SecuriGotchi Read-Only")
    server.tool()(security_status)
    server.tool()(security_trends)
    return server


def main():
    if os.environ.get("SECURIGOTCHI_MCP_ENABLE") != "1":
        raise SystemExit(
            "SecuriGotchi MCP is disabled. Configure SECURIGOTCHI_MCP_ENABLE=1 "
            "in a trusted local client."
        )
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
