# Bonito v0.1.0 — bonito-mcp

The **killer differentiator** of Bonito (BON-004): an MCP server that gives any
AI agent (Claude, Bedrock, Strands) native access to deep database
observability — slow queries, lock/blocking trees, wait analysis, execution
plans, baselines and remediation advice. No commercial DB observability tool
(Datadog DB Monitoring, DBmarlin, Percona PMM) exposes MCP; Bonito does.

It is a thin wrapper over the `bonito-api` REST layer — business logic lives in
the store/API, not here.

## Run it

```bash
uv pip install -e bonito-mcp
export BONITO_API_URL=http://localhost:8100
export BONITO_API_KEY=change-me
bonito-mcp                         # stdio (default)
bonito-mcp --transport sse         # SSE on :8840 (for remote agents)
```

| Env var | Default | Description |
|---------|---------|-------------|
| `BONITO_API_URL` | `http://localhost:8100` | Base URL of `bonito-api` |
| `BONITO_API_KEY` | *(required)* | API key matching the API's `BONITO_API_KEY` |

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

**Claude CLI:**

```bash
claude mcp add bonito -- bonito-mcp
```

**Bedrock / Strands:** same server over stdio/SSE — register it as a tool
provider and the agent gets all 8 tools.

## Tools

| Tool | Question the agent can now answer |
|------|-------------------------------------|
| `get_slow_queries` | "which queries are slow?" |
| `get_active_locks` | "are there locks right now?" |
| `get_blocking_tree` | "who is blocking whom?" |
| `explain_query` | "what's the execution plan for this query?" |
| `get_wait_analysis` | "what are the sessions waiting on?" |
| `compare_to_baseline` | "is this query slower than its 7-day baseline?" |
| `suggest_remediation` | "what should I do about a lock / slow query / bloat?" |
| `get_db_health_summary` | "give me a health summary of the database" |

Tool descriptions are written for LLM routing ("AI-first UX"): rich, with
example invocations.

## Token governance

`query_text` is truncated to 500 chars before returning to the LLM. No
secrets are ever included in tool output.

## Demo flow (deadlock)

1. Agent sees `get_active_locks` → a blocking pair.
2. Agent calls `get_blocking_tree` → PID 1408 blocks 1412.
3. Agent calls `suggest_remediation(issue_type="lock")` → "terminate blocking_pid
   with `pg_terminate_backend`".
4. Agent calls `get_slow_queries` + `compare_to_baseline` → finds a regression
   and suggests `CREATE INDEX`.