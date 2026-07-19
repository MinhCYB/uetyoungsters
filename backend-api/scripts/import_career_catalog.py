"""Import or update the editable career catalog from a taxonomy JSON file."""
import argparse
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    os.environ["DATABASE_URL"] = args.database_url
    sys.path.insert(0, str(BACKEND_ROOT))
    from database import SessionLocal, init_db
    from modules.recommendation.repository import import_catalog
    init_db()
    with SessionLocal() as db:
        count = import_catalog(db, json.loads(args.path.read_text(encoding="utf-8")))
    print(json.dumps({"imported": count, "source": str(args.path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
