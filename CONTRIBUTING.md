# Contributing to uniprotptmpy

Bug reports, fixes and new features are welcome. Use the
[issue tracker](https://github.com/tacular-omics/uniprotptmpy/issues) for bugs and
questions, with a minimal example and the uniprotptmpy and Python versions. Report
security problems privately as described in [SECURITY.md](SECURITY.md).

## Development setup

You need Python 3.12 or newer, [uv](https://docs.astral.sh/uv/) and
[just](https://just.systems/).

```bash
git clone https://github.com/tacular-omics/uniprotptmpy.git
cd uniprotptmpy
just install
```

`just --list` shows the other recipes.

`just install` is `uv sync`, which installs the package and the dev group but not the
two optional extras: `server` (the FastAPI app and the MCP server) and `link`
(`entry.resolve("psimod")` and `entry.resolve("unimod")`, which need psimodpy and
unimodpy). The tests for those parts then **skip at import rather than fail**, so a
green summary says nothing about them. Measured on 2026-11-07 against 1.2.0:

| install | collected | passed | skipped |
|---|---|---|---|
| `uv sync` (no extras) | 282 | 282 | 2 |
| `uv sync --all-extras` | 326 | 326 | 0 |

`tests/test_links.py` and `tests/test_server.py` call `pytest.importorskip` at module
scope, so each whole module is skipped as a single unit: those **2** skips stand for the
**44** tests that were never collected. Read the collected total rather than the skip
count, and note that `--collect-only` prints no skip line at all. If you are changing
either part, install the extras as well:

```bash
uv sync --all-extras
```

Install the commit hooks once per clone with `uvx pre-commit install`. On every
commit they run `ruff check`, `ruff format --check` and a few file checks
(`uvx pre-commit run --all-files` runs them on everything). Type checks and
tests are not in the hooks; run `just check` for those.

## Running checks

CI runs these on every pull request. Run them before you push:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run ty check src
uv run pytest tests
python scripts/release_version.py check
```

## Pull requests

- Branch from `main` and keep each pull request to one change.
- Add tests for new behaviour and fixed bugs.
- Add a line under `## [Unreleased]` in `CHANGELOG.md` for user-visible changes.
- Do not change the version number; the maintainers set it when releasing.
- CI must pass: lint, type check, tests on Python 3.12 to 3.14, and the wheel build.

## CLAUDE.md and AI agents

`CLAUDE.md` is the maintained developer guide: commands, architecture,
conventions and known gotchas. `AGENTS.md` points other coding agents to it.
Read it before a larger change, and update it in the same pull request when your
change makes part of it wrong. AI-assisted contributions are welcome; you are
responsible for reviewing and testing what you submit.
