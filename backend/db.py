"""Manage Supabase storage: python -m backend.db init|migrate|status."""
import argparse
import json
import sys

from dotenv import load_dotenv
import psycopg

from backend.config import ROOT, Settings
from backend.data.postgres import migrate
from backend.data.postgres_repository import PostgresRepository
from backend.errors import AppError


def main():
    parser = argparse.ArgumentParser(description="Initialize and inspect Career Quest in Supabase")
    parser.add_argument("command", choices=("init", "migrate", "status"))
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    try:
        settings = Settings.from_env()
        if not settings.database_url:
            parser.error("Set DATABASE_URL in .env to the PostgreSQL URL from Supabase Connect")
        repository = PostgresRepository(settings.database_url)
        result = {}
        if args.command in {"init", "migrate"}:
            result["migrations_applied"] = migrate(settings.database_url)
        if args.command == "init":
            result["seeded"] = repository.initialize(settings.data_dir, settings.runtime_state_path)
        if args.command in {"init", "status"}:
            view = repository.view()
            result.update(version=view.version, as_of_date=view.as_of_date.isoformat(), counts=view.counts())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except AppError as exc:
        print(exc.message, file=sys.stderr)
    except psycopg.Error:
        print("Database operation failed. Check DATABASE_URL, credentials, network and schema permissions.",
              file=sys.stderr)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
