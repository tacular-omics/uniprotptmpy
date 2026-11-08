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

`just install` is `uv sync`, which installs the package and the dev group but **not**
either optional extra:

- `server` - the FastAPI app and the MCP server (`uniprotptmpy.server`), from fastapi,
  uvicorn, mcp and pydantic.
- `link` - `entry.resolve("psimod")` and `entry.resolve("unimod")`, from psimodpy and
  unimodpy.

So a default install cannot exercise either part, and `tests/test_server.py` and
`tests/test_links.py` **skip at import rather than fail**: a green summary from that
install is no evidence that those parts work.

To tell the two installs apart, read the **passed** count, and `uv pip list` to see what
is actually installed. The pass count is the only one of pytest's three numbers that
always moves in the right direction. Both of those modules call `pytest.importorskip` at
**module** scope, so the collected total drops as well here - but it would not move at
all for a gate inside a test or a fixture, as in `tests/test_data_agreement.py`, and the
skip count is worth less than it looks either way, because a module skipped at import
counts as **one** skip however many tests it hides. `--collect-only` prints no skip line
at all.

`tests/test_data_agreement.py` is the fixture-scope case, and it guards a dev-group
sibling rather than an extra, so `uv sync` does cover it. Set
`TACULAR_REQUIRE_SIBLINGS=1` to make it fail instead of skip if that sibling is ever
missing. The collected total is identical either way.

If you are changing either part, install the extras as well:

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
