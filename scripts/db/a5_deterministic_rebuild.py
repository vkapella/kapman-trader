from __future__ import annotations

import argparse
import os

from core.db.a6_migrations import (
    default_database_url,
    default_migrations_dir,
    list_sql_migrations,
    reset_and_migrate,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A5 deterministic DB rebuild orchestrator (reuses A6 wipe-and-migrate)."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=int(os.getenv("KAPMAN_REBUILD_ITERATIONS", "1")),
        help="Number of rebuild iterations (default: env KAPMAN_REBUILD_ITERATIONS or 1).",
    )
    parser.add_argument(
        "--print-migrations",
        action="store_true",
        help="Print migrations in deterministic apply order and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    migrations_dir = default_migrations_dir()
    if args.print_migrations:
        for path in list_sql_migrations(migrations_dir):
            print(path.name)
        return 0

    db_url = default_database_url()
    for _ in range(args.iterations):
        reset_and_migrate(db_url, migrations_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
