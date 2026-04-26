"""HTTP API and MCP server for uniprotptmpy.

Optional install: ``pip install uniprotptmpy[server]``.

Run locally::

    uvicorn uniprotptmpy.server.app:app --reload

Endpoints:
    GET  /api/health
    GET  /api/entries
    GET  /api/entries/{id}
    GET  /api/entries/by-name/{name}
    GET  /api/search?q=...
    POST /mcp                          (Model Context Protocol)
"""

from uniprotptmpy.server.app import app, mcp

__all__ = ["app", "mcp"]
