from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()
preferred_database_url = settings.database_url


def _build_connect_args(database_url: str) -> dict[str, object]:
    backend_name = make_url(database_url).get_backend_name()
    if backend_name == "sqlite":
        return {"check_same_thread": False}
    if backend_name == "mysql":
        return {"connect_timeout": settings.database_connect_timeout_seconds}
    return {}


def _build_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        connect_args=_build_connect_args(database_url),
        pool_pre_ping=True,
        future=True,
    )


def _probe_engine(candidate_engine: Engine) -> None:
    with candidate_engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _resolve_runtime_engine() -> tuple[Engine, str, bool]:
    candidate_engine = _build_engine(preferred_database_url)
    preferred_backend = make_url(preferred_database_url).get_backend_name()
    if preferred_backend == "sqlite":
        return candidate_engine, preferred_database_url, False
    try:
        _probe_engine(candidate_engine)
        return candidate_engine, preferred_database_url, False
    except Exception:
        candidate_engine.dispose()
        fallback_engine = _build_engine(settings.sqlite_fallback_url)
        _probe_engine(fallback_engine)
        return fallback_engine, settings.sqlite_fallback_url, True


engine, active_database_url, using_sqlite_fallback = _resolve_runtime_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


def get_database_dialect_name(bind: Session | Engine | None = None) -> str:
    target = bind.get_bind() if isinstance(bind, Session) else bind or engine
    return target.dialect.name


def is_sqlite_bind(bind: Session | Engine | None = None) -> bool:
    return get_database_dialect_name(bind) == "sqlite"


def mask_database_url(database_url: str | None = None) -> str:
    return make_url(database_url or active_database_url).render_as_string(hide_password=True)


def get_preferred_database_url() -> str:
    return preferred_database_url


def get_active_database_url() -> str:
    return active_database_url


def is_using_sqlite_fallback() -> bool:
    return using_sqlite_fallback


def get_database_runtime_profile(bind: Session | Engine | None = None) -> dict[str, str | bool]:
    active_dialect = get_database_dialect_name(bind)
    preferred_backend = make_url(preferred_database_url).get_backend_name()
    mode = "sqlite-fallback" if using_sqlite_fallback else "oceanbase-primary" if preferred_backend == "mysql" else f"{preferred_backend}-primary"
    return {
        "mode": mode,
        "preferred_backend": "oceanbase" if preferred_backend == "mysql" else preferred_backend,
        "active_dialect": active_dialect,
        "using_sqlite_fallback": using_sqlite_fallback,
        "preferred_database_url_masked": mask_database_url(preferred_database_url),
        "active_database_url_masked": mask_database_url(active_database_url),
    }


def set_sqlite_foreign_keys(session: Session, enabled: bool) -> None:
    if is_sqlite_bind(session):
        pragma_value = "ON" if enabled else "OFF"
        session.execute(text(f"PRAGMA foreign_keys={pragma_value}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
