# Copilot instructions

The canonical guide for AI agents in this repo is [`CLAUDE.md`](../CLAUDE.md). Read it
first. The rules that matter most:

1. Use the `justfile` (`just check`, `just test`, `just lint`, `just ty`), falling back
   to `uv run ...`. Never install with pip, npm or any other package manager.
2. The core package has no runtime dependencies. Only `uniprotptmpy/server/` may import
   `fastapi`, `pydantic` or `mcp` (the `server` extra); core modules never import it.
3. A `PtmEntry` field change touches both the dataclass in `models.py` and the pydantic
   model in `server/models.py`, plus the TSV, ptmlist and dashboard writers.
4. Keep the per-request `MCPServer` in `server/app.py`: Vercel fires no ASGI lifespan
   events.
5. Do not bump the version, tag or publish; only the tacular-omics overseer releases.
