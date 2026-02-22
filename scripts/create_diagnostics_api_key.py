#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.diagnostics_api_key_registry import create_api_client_key  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a diagnostics API key (stores hash only, prints raw key once)."
    )
    parser.add_argument("--name", required=True, help="Client display name")
    parser.add_argument(
        "--scopes",
        required=True,
        help="Comma-separated scopes, e.g. diagnostics:read,diagnostics:operate",
    )
    parser.add_argument("--created-by", default="local_admin", help="Audit creator identity")
    parser.add_argument("--notes", default=None, help="Optional notes")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    scopes = [scope.strip() for scope in str(args.scopes).split(",") if scope.strip()]

    record, raw_key = create_api_client_key(
        name=args.name,
        scopes=scopes,
        created_by=args.created_by,
        notes=args.notes,
        database_url=args.database_url,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "client": record,
                    "api_key": raw_key,
                    "warning": "Store this API key securely. It is shown only once.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print("Diagnostics API key created successfully.")
    print(f"client_id : {record['client_id']}")
    print(f"name      : {record['name']}")
    print(f"scopes    : {', '.join(record.get('scopes', []))}")
    print(f"created_at: {record['created_at']}")
    print("")
    print("Raw API key (displayed once):")
    print(raw_key)
    print("")
    print("Store this key securely. Only the hash is persisted in the database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
