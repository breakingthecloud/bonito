# bonito-mcp

The **killer differentiator** of Bonito (BON-004): an MCP server that gives any
AI agent (Claude, Bedrock, Strands) native access to deep database
observability. No Datadog DB Monitoring, DBmarlin or Percona PMM expose MCP —
Bonito does.

It is a thin wrapper over the `bonito-api` REST layer (business logic lives in
store/API, not duplicated here).

## Run

```bash
uv pip install -e bonito-mcp          # local (repo checkout)
pip install bonito-mcp-server         # from PyPI
export BONITO_API_URL=http://localhost:8100
export BONITO_API_KEY=change-me
bonito-mcp                      # stdio transport
```

> **PyPI name note:** the distribution is `bonito-mcp-server` — the bare name
> `bonito-mcp` is already taken on PyPI by an unrelated project. The console
> command is still `bonito-mcp`. With `uvx`, use
> `uvx --from bonito-mcp-server bonito-mcp`.

## Connect to an agent

**Claude Desktop** — `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bonito": {
      "command": "bonito-mcp",
      "env": { "BONITO_API_URL": "http://localhost:8100", "BONITO_API_KEY": "change-me" }
    }
  }
}
```

**Claude CLI**:

```bash
claude mcp add bonito -- bonito-mcp
```

**Bedrock / Strands:** the same server runs over stdio/SSE — wire it as a
tool provider and the agent gets all 8 tools.

## Tools

| Tool | What the agent asks |
|------|---------------------|
| `get_slow_queries` | "which queries are slow?" |
| `get_active_locks` | "are there locks right now?" |
| `get_blocking_tree` | "who is blocking whom?" |
| `explain_query` | "what's the execution plan for this query?" |
| `get_wait_analysis` | "what are the sessions waiting on?" |
| `compare_to_baseline` | "is this query slower than usual?" |
| `suggest_remediation` | "what should I do about a lock / slow query / bloat?" |
| `get_db_health_summary` | "give me a health summary of the database" |

## Config

| Env var | Default | Description |
|---------|---------|-------------|
| `BONITO_API_URL` | `http://localhost:8100` | Base URL of `bonito-api` |
| `BONITO_API_KEY` | *(required)* | API key matching the API's `BONITO_API_KEY` |

## Token governance

`query_text` is truncated to 500 chars before returning to the LLM; no
secrets are ever included in tool output.