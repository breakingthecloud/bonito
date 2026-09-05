"""bonito-api CLI — serve the API or dump the public OpenAPI contract."""
from __future__ import annotations

import argparse
import os

import uvicorn
import yaml

from .app import create_app


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def main() -> None:
    ap = argparse.ArgumentParser(prog="bonito-api")
    sub = ap.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the FastAPI query layer")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=_env_int("BONITO_API_PORT", 8100))
    serve.add_argument("--db", default=os.environ.get("BONITO_DB", "bonito.db"))

    spec = sub.add_parser("spec", help="dump the public OpenAPI contract to a file")
    spec.add_argument("--out", default="openapi.yaml")

    args = ap.parse_args()
    app = create_app(getattr(args, "db", None))
    if args.command == "serve":
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            yaml.safe_dump(app.openapi(), f, sort_keys=False)
        print(f"openapi contract written to {args.out}")


if __name__ == "__main__":
    main()