from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep
from app.core.response import success_response
from app.services.distributed_service import complete_transfer, create_transfer, get_sync_logs, overview, run_reconciliation

router = APIRouter(prefix="/api/distributed", tags=["distributed"])


@router.get("/overview")
def distributed_overview(db: Session = Depends(get_db_dep)):
    return success_response(overview(db))


@router.post("/reconciliation/run")
def reconciliation(db: Session = Depends(get_db_dep)):
    result = run_reconciliation(db)
    db.commit()
    return success_response(result)


@router.get("/sync-logs")
def sync_logs(db: Session = Depends(get_db_dep)):
    items = get_sync_logs(db)
    return success_response(
        [
            {
                "id": item.id,
                "node_name": item.node_name,
                "node_type": item.node_type,
                "status": item.status,
                "checked_records": item.checked_records,
                "mismatch_records": item.mismatch_records,
                "message": item.message,
            }
            for item in items
        ]
    )
