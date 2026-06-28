from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.schema import CreateTable

from app.core.config import get_settings
from app.core.database import SessionLocal, engine, get_active_database_url
from app.models import Base
from app.models.user import User
from app.utils.hash_utils import hash_password


def export_schema_sql(schema_path: Path) -> None:
    statements = []
    for table in Base.metadata.sorted_tables:
        statements.append(str(CreateTable(table).compile(engine)).strip() + ";\n")
    schema_path.write_text("\n".join(statements), encoding="utf-8")


def export_seed_sql(seed_path: Path) -> None:
    users = [
        ("admin", "admin123", "系统管理员", "admin"),
        ("buyer", "buyer123", "采购专员", "buyer"),
        ("warehouse", "warehouse123", "仓库主管", "warehouse_manager"),
        ("store", "store123", "门店员工", "store_staff"),
        ("manager", "manager123", "运营经理", "manager"),
    ]
    lines = []
    for username, password, real_name, role in users:
        lines.append(
            "INSERT INTO users (username, password_hash, real_name, role, is_active) VALUES "
            f"('{username}', '{hash_password(password)}', '{real_name}', '{role}', 1);"
        )
    seed_path.write_text("\n".join(lines), encoding="utf-8")


def init_db(rebuild: bool = False) -> None:
    settings = get_settings()
    settings.schema_dir_path.mkdir(parents=True, exist_ok=True)
    active_database_url = get_active_database_url()
    active_is_sqlite = active_database_url.startswith("sqlite")
    if active_is_sqlite:
        database_path = settings.resolve_sqlite_path(active_database_url)
        if rebuild and database_path.exists():
            engine.dispose()
            database_path.unlink()
    elif rebuild:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    if active_is_sqlite:
        export_schema_sql(settings.schema_dir_path / "schema.sql")
        export_seed_sql(settings.schema_dir_path / "seed.sql")
    session = SessionLocal()
    try:
        existing = {row.username for row in session.query(User).all()}
        seed_users = [
            {"username": "admin", "password": "admin123", "real_name": "系统管理员", "role": "admin"},
            {"username": "buyer", "password": "buyer123", "real_name": "采购专员", "role": "buyer"},
            {"username": "warehouse", "password": "warehouse123", "real_name": "仓库主管", "role": "warehouse_manager"},
            {"username": "store", "password": "store123", "real_name": "门店员工", "role": "store_staff"},
            {"username": "manager", "password": "manager123", "real_name": "运营经理", "role": "manager"},
        ]
        for item in seed_users:
            if item["username"] not in existing:
                session.add(
                    User(
                        username=item["username"],
                        password_hash=hash_password(item["password"]),
                        real_name=item["real_name"],
                        role=item["role"],
                        is_active=True,
                    )
                )
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    init_db(rebuild=args.rebuild)
