"""bonito-mcp CLI — run the MCP server over stdio (or SSE)."""
from __future__ import annotations

import argparse

from .client import BonitoClient
from .server import build_mcp


def main() -> None:
    ap = argparse.ArgumentParser(prog="bonito-mcp", description="Bonito MCP server")
    ap.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport (default stdio)",
    )
    ap.add_argument("--sse-port", type=int, default=8840, help="port for SSE transport")
    args = ap.parse_args()

    client = BonitoClient.from_env()
    server = build_mcp(client)
    server.run(transport=args.transport, host="0.0.0.0", port=args.sse_port)


if __name__ == "__main__":
    main()