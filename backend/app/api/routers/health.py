from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep
from app.core.config import get_settings
from app.core.database import get_database_runtime_profile
from app.core.response import error_response, success_response

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health(db: Session = Depends(get_db_dep)):
    db.execute(text("SELECT 1"))
    return success_response(
        {
            "status": "running",
            "database": "connected",
            "app": get_settings().app_name,
        }
    )


@router.get("/db")
def health_db(db: Session = Depends(get_db_dep)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content=error_response(f"database connection failed: {exc.__class__.__name__}"),
        )
    runtime_profile = get_database_runtime_profile(db)
    return success_response(
        {
            "status": "connected",
            "dialect": runtime_profile["active_dialect"],
            "database_url_masked": runtime_profile["active_database_url_masked"],
            "preferred_database_url_masked": runtime_profile["preferred_database_url_masked"],
            "mode": runtime_profile["mode"],
            "preferred_backend": runtime_profile["preferred_backend"],
        }
    )
