"""Opt-in read-only MCP stdio server for trusted local AI clients."""
import os
from gotchi_insights import snapshot, trends

def security_status() -> dict:
    """Return aggregate security counts, health, and alert titles without IPs or raw logs."""
    return snapshot()

def security_trends(hours: int = 24) -> list[dict]:
    """Return hourly aggregate authentication counts, limited to 72 hours."""
    return trends(hours)

def main():
    if os.environ.get("SECURIGOTCHI_MCP_ENABLE") != "1":
        raise SystemExit("Set SECURIGOTCHI_MCP_ENABLE=1 to opt in to local MCP access.")
    from mcp.server.fastmcp import FastMCP
    app = FastMCP("SecuriGotchi Read-Only")
    app.tool()(security_status)
    app.tool()(security_trends)
    app.run(transport="stdio")

if __name__ == "__main__":
    main()
