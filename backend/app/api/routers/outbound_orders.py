from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db_dep
from app.core.exceptions import BusinessException
from app.core.response import page_response, success_response
from app.models.outbound import OutboundOrder
from app.schemas.outbound import OutboundOrderCreate, OutboundOrderRead
from app.services.outbound_service import cancel_outbound_order, create_outbound_order, ship_outbound_order, sign_outbound_order
from app.utils.pagination import normalize_pagination

router = APIRouter(prefix="/api/outbound-orders", tags=["outbound-orders"])


def serialize_outbound_order(item: OutboundOrder) -> dict:
    data = OutboundOrderRead.model_validate(item).model_dump()
    data["source_warehouse_name"] = item.source_warehouse.name if item.source_warehouse else None
    data["target_store_name"] = item.target_store.name if item.target_store else None
    return data


@router.post("")
def create(payload: OutboundOrderCreate, db: Session = Depends(get_db_dep)):
    order = create_outbound_order(db, payload)
    db.commit()
    db.refresh(order)
    return success_response(serialize_outbound_order(order))


@router.get("")
def list_orders(page: int = 1, page_size: int = 20, keyword: str | None = None, db: Session = Depends(get_db_dep)):
    page, page_size = normalize_pagination(page, page_size)
    query = select(OutboundOrder).options(
        joinedload(OutboundOrder.items),
        joinedload(OutboundOrder.source_warehouse),
        joinedload(OutboundOrder.target_store),
    )
    if keyword:
        query = query.where(OutboundOrder.outbound_no.contains(keyword))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    result = db.execute(query.offset((page - 1) * page_size).limit(page_size))
    items = [serialize_outbound_order(item) for item in result.unique().scalars().all()]
    return page_response(items, total, page, page_size)


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db_dep)):
    item = (
        db.execute(
            select(OutboundOrder)
            .options(
                joinedload(OutboundOrder.items),
                joinedload(OutboundOrder.source_warehouse),
                joinedload(OutboundOrder.target_store),
            )
            .where(OutboundOrder.id == order_id)
        )
        .unique()
        .scalar_one_or_none()
    )
    if not item:
        raise BusinessException("outbound order not found", 404)
    return success_response(serialize_outbound_order(item))


@router.post("/{order_id}/ship")
def ship(order_id: int, db: Session = Depends(get_db_dep)):
    try:
        item = ship_outbound_order(db, order_id)
        db.commit()
        db.refresh(item)
        return success_response(serialize_outbound_order(item))
    except Exception:
        db.rollback()
        raise


@router.post("/{order_id}/sign")
def sign(order_id: int, db: Session = Depends(get_db_dep)):
    try:
        item = sign_outbound_order(db, order_id)
        db.commit()
        db.refresh(item)
        return success_response(serialize_outbound_order(item))
    except Exception:
        db.rollback()
        raise


@router.post("/{order_id}/cancel")
def cancel(order_id: int, db: Session = Depends(get_db_dep)):
    item = cancel_outbound_order(db, order_id)
    db.commit()
    return success_response(serialize_outbound_order(item))
