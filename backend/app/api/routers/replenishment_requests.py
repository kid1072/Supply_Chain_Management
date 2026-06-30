from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
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


def load_outbound_map(db: Session, outbound_ids: list[int | None] | None = None, source_request_ids: list[int] | None = None) -> dict[int, OutboundOrder]:
    valid_ids = [item for item in (outbound_ids or []) if item]
    valid_request_ids = [item for item in (source_request_ids or []) if item]
    if not valid_ids and not valid_request_ids:
        return {}
    query = (
        select(OutboundOrder)
        .options(joinedload(OutboundOrder.source_warehouse), joinedload(OutboundOrder.target_store))
    )
    if valid_ids and valid_request_ids:
        query = query.where(or_(OutboundOrder.id.in_(valid_ids), OutboundOrder.source_request_id.in_(valid_request_ids)))
    elif valid_ids:
        query = query.where(OutboundOrder.id.in_(valid_ids))
    else:
        query = query.where(OutboundOrder.source_request_id.in_(valid_request_ids))
    return {item.id: item for item in db.scalars(query)}


def group_outbounds_by_request(outbound_map: dict[int, OutboundOrder]) -> dict[int, list[OutboundOrder]]:
    grouped: dict[int, list[OutboundOrder]] = {}
    for item in outbound_map.values():
        if not item.source_request_id:
            continue
        grouped.setdefault(item.source_request_id, []).append(item)
    return grouped


def serialize_replenishment_request(
    item: ReplenishmentRequest,
    outbound_map: dict[int, OutboundOrder] | None = None,
    outbounds_by_request: dict[int, list[OutboundOrder]] | None = None,
) -> dict:
    data = ReplenishmentRequestRead.model_validate(item).model_dump()
    outbound = (outbound_map or {}).get(item.generated_outbound_order_id)
    related_outbounds = sorted(
        (outbounds_by_request or {}).get(item.id, []),
        key=lambda current: current.id,
    )
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
    data["outbound_order_ids"] = [current.id for current in related_outbounds]
    data["outbound_order_count"] = len(related_outbounds)
    data["outbound_orders"] = [
        {
            "id": current.id,
            "outbound_no": current.outbound_no,
            "source_warehouse_id": current.source_warehouse_id,
            "source_warehouse_name": current.source_warehouse.name if current.source_warehouse else None,
            "target_store_id": current.target_store_id,
            "target_store_name": current.target_store.name if current.target_store else None,
            "status": current.status,
        }
        for current in related_outbounds
    ]
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
    outbound_map = load_outbound_map(
        db,
        [item.generated_outbound_order_id for item in rows],
        [item.id for item in rows],
    )
    outbounds_by_request = group_outbounds_by_request(outbound_map)
    items = [serialize_replenishment_request(item, outbound_map, outbounds_by_request) for item in rows]
    return page_response(items, total, page, page_size)


@router.get("/{request_id}")
def get_item(request_id: int, db: Session = Depends(get_db_dep)):
    item = db.get(ReplenishmentRequest, request_id)
    if not item:
        raise BusinessException("request not found", 404)
    outbound_map = load_outbound_map(db, [item.generated_outbound_order_id], [item.id])
    return success_response(serialize_replenishment_request(item, outbound_map, group_outbounds_by_request(outbound_map)))


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
        items = convert_to_outbound(db, request_id, source_warehouse_id, handled_by)
        db.commit()
        for item in items:
            db.refresh(item)
        primary = items[0]
        return success_response(
            {
                "outbound_order_id": primary.id,
                "outbound_no": primary.outbound_no,
                "source_warehouse_id": primary.source_warehouse_id,
                "source_warehouse_name": primary.source_warehouse.name if primary.source_warehouse else None,
                "target_store_id": primary.target_store_id,
                "target_store_name": primary.target_store.name if primary.target_store else None,
                "status": primary.status,
                "outbound_order_ids": [item.id for item in items],
                "outbound_order_count": len(items),
                "outbound_orders": [
                    {
                        "id": item.id,
                        "outbound_no": item.outbound_no,
                        "source_warehouse_id": item.source_warehouse_id,
                        "source_warehouse_name": item.source_warehouse.name if item.source_warehouse else None,
                        "target_store_id": item.target_store_id,
                        "target_store_name": item.target_store.name if item.target_store else None,
                        "status": item.status,
                        "quantity": sum(detail.quantity for detail in item.items),
                    }
                    for item in items
                ],
            }
        )
    except Exception:
        db.rollback()
        raise
