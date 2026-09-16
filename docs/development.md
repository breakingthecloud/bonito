# Development

## Setup

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -e ".[dev]" -e bonito-store -e bonito-api -e bonito-mcp
```

## Tests + lint

```bash
pytest            # 44 tests across the 4 packages
ruff check src
```

The collector is **read-only** and never builds SQL from client input. Keep it
that way: fixed queries over system views, values only via `%s` params.

## Branching & releases

- Work on a `feat/bon-0XX-*` branch; open a PR to `main`.
- Each package has its own version (`bonito-collector`, `bonito-store`,
  `bonito-api`, `bonito-mcp-server`) — see `package-env-standards` for the
  PyPI publish flow (token in macOS Keychain `pypi-token`).
- Git tags follow `bonito-<package>-v<semver>` (e.g. `bonito-collector-v0.2.0`).

## Docs

Docs live in `docs/` (mkdocs-material). Build locally:

```bash
pip install mkdocs-material
mkdocs build
mkdocs serve        # http://localhost:8000
```

Deploy to `bonito-docs.sofe.dev` via Cloudflare Pages (`mkdocs build` →
publish `site/`; CNAME `bonito-docs` → `bonito-docs.pages.dev`).