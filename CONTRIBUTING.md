# Contributing to Bonito OSS

Thanks for contributing to Bonito — deep database observability, free.

## Project layout

```
bonito/
├── Dockerfile              # bonito-collector image
├── src/bonito_collector/   # collector package (BON-001)
├── bonito-store/           # SQLite event store (BON-002)
├── bonito-api/             # FastAPI query layer (BON-003)
├── bonito-mcp/             # MCP server, 8 tools (BON-004)
├── deploy/                 # docker compose + fixture (BON-005)
├── docs/                   # user documentation (mkdocs)
└── examples/               # compose, env templates, ai-agent-demo
```

## Development

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]" -e bonito-store -e bonito-api -e bonito-mcp
python -m pytest          # all tests
ruff check .              # linter
```

## Golden rule

The collector is **read-only** and never builds SQL from client input. Keep it
that way: fixed queries over system views, values only via `%s` params.

## Branching & releases

- Work on a `feat/bon-0XX-*` branch; open a PR to `main`.
- Each package has its own version (`bonito-collector`, `bonito-store`,
  `bonito-api`, `bonito-mcp-server`) — see `package-env-standards` for the
  PyPI publish flow (token in macOS Keychain `pypi-token`).

## Code of conduct

Be respectful and constructive. Deep observability is a public good.