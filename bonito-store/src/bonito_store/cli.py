"""bonito-store CLI — serve the API or run retention pruning."""
from __future__ import annotations

import argparse
import os

import uvicorn

from .api import create_app
from .store import BonitoStore


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def main() -> None:
    ap = argparse.ArgumentParser(prog="bonito-store")
    sub = ap.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the FastAPI receiver")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=_env_int("BONITO_STORE_PORT", 8000))
    serve.add_argument("--db", default=os.environ.get("BONITO_DB", "bonito.db"))
    serve.add_argument(
        "--retention-days", type=int, default=_env_int("BONITO_RETENTION_DAYS", 7)
    )

    prune = sub.add_parser("prune", help="apply retention pruning once")
    prune.add_argument("--db", default=os.environ.get("BONITO_DB", "bonito.db"))
    prune.add_argument("--days", type=int, default=_env_int("BONITO_RETENTION_DAYS", 7))

    args = ap.parse_args()
    if args.command == "serve":
        app = create_app(args.db, args.retention_days)
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        store = BonitoStore(args.db, args.days)
        print(store.prune(args.days))


if __name__ == "__main__":
    main()