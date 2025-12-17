from __future__ import annotations

import sys

from core.db.a6_migrations import (
    default_database_url,
    default_migrations_dir,
    reset_and_migrate,
)


def main() -> int:
    reset_and_migrate(default_database_url(), default_migrations_dir())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
