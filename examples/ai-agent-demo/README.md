# AI-Agent Demo — Bonito diagnoses a deadlock

This is the launch demo: an **AI agent** diagnosing a database deadlock using
Bonito's MCP tools — the thing no commercial DB observability tool can do.

## Run it (no LLM, no live DB needed)

The script drives the exact 8 MCP tools against a real in-process
`bonito-api` + `bonito-store` (seeded with a synthetic lock chain
1408 → 1412 → 1413), and prints a narrated transcript:

```bash
uv pip install -e bonito-mcp -e bonito-api -e bonito-store
python examples/ai-agent-demo/demo.py
```

You'll see the agent: detect locks → build the blocking tree → ask for
remediation → find slow queries → compare against baseline → give a verdict.

## Live version (real agent + real database)

1. Deploy the stack: `docker compose -f deploy/docker-compose.yml up -d`
2. Connect an agent to the MCP server (SSE on `:8840` or stdio):

```bash
claude mcp add bonito -- bonito-mcp
```

3. Ask the agent:

> "There's a lock on the orders table. Who's blocking whom and what should we do?"

The agent will call `get_active_locks` → `get_blocking_tree` →
`suggest_remediation(issue_type='lock')`, then `get_slow_queries` +
`compare_to_baseline` to spot regressions — and recommend
`pg_terminate_backend(<blocking_pid>)` or `CREATE INDEX`.

## The transcript shape (scripted demo)

```
STEP 1  get_active_locks          → blocking pair (1408 → 1412, wait=transactionid)
STEP 2  get_blocking_tree         → 1408 blocks 1412; 1412 blocks 1413 (chain)
STEP 3  suggest_remediation(lock) → terminate blocking_pid 1408
STEP 4  get_slow_queries          → Seq Scan on orders is #2 slowest
STEP 5  compare_to_baseline       → regression_pct > 0
VERDICT                             kill 1408 + CREATE INDEX on orders(customer_id)
```