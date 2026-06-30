from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal, get_database_runtime_profile
from app.services.walmart_import_service import describe_dataset, import_walmart_data, open_walmart_dataset


def _print_dataset_preview(input_path: str) -> None:
    with open_walmart_dataset(input_path) as inspection:
        description = describe_dataset(inspection)
        print("Detected files:")
        for item in description["detected_files"]:
            print(f"  - {item}")
        print("Detected headers:")
        for logical_name, headers in description["file_headers"].items():
            print(f"  - {logical_name}: {headers}")


def _print_runtime_profile() -> None:
    session = SessionLocal()
    try:
        runtime = get_database_runtime_profile(session)
    finally:
        session.close()
    print("Database runtime:")
    print(json.dumps(
        {
            "mode": runtime["mode"],
            "active_dialect": runtime["active_dialect"],
            "preferred_backend": runtime["preferred_backend"],
            "active_database_url_masked": runtime["active_database_url_masked"],
        },
        ensure_ascii=False,
        indent=2,
    ))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Zip archive or extracted Walmart dataset directory")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace-walmart", action="store_true")
    args = parser.parse_args()

    _print_dataset_preview(args.input)
    _print_runtime_profile()

    session = SessionLocal()
    try:
        summary = import_walmart_data(
            session,
            args.input,
            dry_run=args.dry_run,
            replace_walmart=args.replace_walmart,
        )
        if args.dry_run:
            session.rollback()
        else:
            session.commit()
        print("Import summary:")
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        session.rollback()
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
