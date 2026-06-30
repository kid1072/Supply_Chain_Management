from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep
from app.core.response import success_response
from app.services.walmart_import_service import get_walmart_status

router = APIRouter(prefix="/api/external-data", tags=["external-data"])


@router.get("/walmart/status")
def walmart_status(db: Session = Depends(get_db_dep)):
    return success_response(get_walmart_status(db))
