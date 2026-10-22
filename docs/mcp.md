# SecuriGotchi read-only MCP integration

Install optional dependencies with `python -m pip install -r requirements-mcp.txt`.
For a trusted local MCP client, configure the executable as the absolute path
to this project's virtual environment Python, and arguments as the absolute
path to `gotchi_mcp.py`. Set `SECURIGOTCHI_MCP_ENABLE=1`.

The server uses stdio rather than HTTP and offers two tools:
`security_status` and `security_trends`. Both provide aggregate data
without raw logs, IP addresses, or usernames. No scan execution or
system changes are supported.

The connected desktop MCP host inherits your OS account's read access.
Flask administrator sessions do not apply to MCP. Do not configure this
server in an untrusted AI client or expose it over a network.
Model selection and remote-cloud connectors are not provided by this server.

## SDK compatibility and validation

This integration targets the official MCP Python SDK v2, using
`from mcp.server import MCPServer`. It includes a separate CI job testing
tool listing and invocation through an in-memory client and a real stdio
subprocess. The MCP server runs only when `SECURIGOTCHI_MCP_ENABLE=1`.

**Privacy:** an MCP host can forward returned aggregates to its selected
model or service, potentially including a cloud model. Use a trusted host and
review its data handling. No login to SecuriGotchi is required by the local
stdio host; it inherits the configured operating-system user's permissions.
