"""Read-only Exoscale advisor MCP server.

Exposes the Exoscale knowledge bundle and list-only live catalogue queries to an
MCP-capable agent. The design is documented in ``docs/mcp-advisor-design.md``;
the server is, by construction, incapable of mutating any cloud resource
(design §6).
"""

__version__ = "0.1.0"
