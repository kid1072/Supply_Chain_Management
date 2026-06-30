from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db_dep
from app.core.exceptions import BusinessException
from app.core.response import page_response, success_response
from app.models.outbound import OutboundOrder
from app.models.replenishment import ReplenishmentRequest
from app.schemas.replenishment import ReplenishmentRequestCreate, ReplenishmentRequestRead
from app.services.replenishment_service import approve_request, convert_to_outbound, create_replenishment_request, reject_request
from app.utils.pagination import normalize_pagination

router = APIRouter(prefix="/api/replenishment-requests", tags=["replenishment-requests"])


def load_outbound_map(db: Session, outbound_ids: list[int | None]) -> dict[int, OutboundOrder]:
    valid_ids = [item for item in outbound_ids if item]
    if not valid_ids:
        return {}
    query = (
        select(OutboundOrder)
        .options(joinedload(OutboundOrder.source_warehouse), joinedload(OutboundOrder.target_store))
        .where(OutboundOrder.id.in_(valid_ids))
    )
    return {item.id: item for item in db.scalars(query)}


def serialize_replenishment_request(
    item: ReplenishmentRequest,
    outbound_map: dict[int, OutboundOrder] | None = None,
) -> dict:
    data = ReplenishmentRequestRead.model_validate(item).model_dump()
    outbound = (outbound_map or {}).get(item.generated_outbound_order_id)
    if outbound:
        data["outbound_no"] = outbound.outbound_no
        data["source_warehouse_id"] = outbound.source_warehouse_id
        data["source_warehouse_name"] = outbound.source_warehouse.name if outbound.source_warehouse else None
        data["target_store_id"] = outbound.target_store_id
        data["target_store_name"] = outbound.target_store.name if outbound.target_store else None
        data["outbound_status"] = outbound.status
    else:
        data["outbound_no"] = None
        data["source_warehouse_id"] = None
        data["source_warehouse_name"] = None
        data["target_store_id"] = None
        data["target_store_name"] = None
        data["outbound_status"] = None
    return data


@router.post("")
def create(payload: ReplenishmentRequestCreate, db: Session = Depends(get_db_dep)):
    item = create_replenishment_request(db, payload)
    db.commit()
    db.refresh(item)
    return success_response(serialize_replenishment_request(item))


@router.get("")
def list_items(page: int = 1, page_size: int = 20, keyword: str | None = None, db: Session = Depends(get_db_dep)):
    page, page_size = normalize_pagination(page, page_size)
    query = select(ReplenishmentRequest)
    if keyword:
        query = query.where(ReplenishmentRequest.request_no.contains(keyword))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
    outbound_map = load_outbound_map(db, [item.generated_outbound_order_id for item in rows])
    items = [serialize_replenishment_request(item, outbound_map) for item in rows]
    return page_response(items, total, page, page_size)


@router.get("/{request_id}")
def get_item(request_id: int, db: Session = Depends(get_db_dep)):
    item = db.get(ReplenishmentRequest, request_id)
    if not item:
        raise BusinessException("request not found", 404)
    outbound_map = load_outbound_map(db, [item.generated_outbound_order_id])
    return success_response(serialize_replenishment_request(item, outbound_map))


@router.post("/{request_id}/approve")
def approve(request_id: int, audited_by: int, db: Session = Depends(get_db_dep)):
    item = approve_request(db, request_id, audited_by)
    db.commit()
    return success_response(serialize_replenishment_request(item))


@router.post("/{request_id}/reject")
def reject(request_id: int, audited_by: int, db: Session = Depends(get_db_dep)):
    item = reject_request(db, request_id, audited_by)
    db.commit()
    return success_response(serialize_replenishment_request(item))


@router.post("/{request_id}/convert-to-outbound")
def convert(
    request_id: int,
    handled_by: int,
    source_warehouse_id: int | None = None,
    db: Session = Depends(get_db_dep),
):
    try:
        item = convert_to_outbound(db, request_id, source_warehouse_id, handled_by)
        db.commit()
        db.refresh(item)
        return success_response(
            {
                "outbound_order_id": item.id,
                "outbound_no": item.outbound_no,
                "source_warehouse_id": item.source_warehouse_id,
                "source_warehouse_name": item.source_warehouse.name if item.source_warehouse else None,
                "target_store_id": item.target_store_id,
                "target_store_name": item.target_store.name if item.target_store else None,
                "status": item.status,
            }
        )
    except Exception:
        db.rollback()
        raise
