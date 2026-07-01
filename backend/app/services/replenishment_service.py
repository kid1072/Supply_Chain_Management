from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.outbound import OutboundOrder
from app.models.product import Product
from app.models.replenishment import ReplenishmentRequest
from app.models.store import Store
from app.models.user import User
from app.schemas.outbound import OutboundOrderCreate
from app.schemas.replenishment import ReplenishmentRequestCreate
from app.services.inventory_service import allocate_source_warehouses, ensure_source_warehouse_has_stock, generate_doc_no, reserve_stock
from app.services.outbound_service import create_outbound_order
from app.utils.datetime_utils import now_local


def create_replenishment_request(db: Session, payload: ReplenishmentRequestCreate) -> ReplenishmentRequest:
    if payload.request_quantity <= 0:
        raise BusinessException("request_quantity must be greater than 0")
    if not db.get(Store, payload.store_id):
        raise BusinessException("store not found", 404)
    if not db.get(Product, payload.product_id):
        raise BusinessException("product not found", 404)
    total = db.scalar(select(func.count(ReplenishmentRequest.id))) or 0
    request = ReplenishmentRequest(
        request_no=generate_doc_no("REQ", total + 1),
        store_id=payload.store_id,
        product_id=payload.product_id,
        request_quantity=payload.request_quantity,
        request_reason=payload.request_reason,
        created_by=payload.created_by,
        audit_status="pending",
    )
    db.add(request)
    db.flush()
    return request


def approve_request(db: Session, request_id: int, audited_by: int) -> ReplenishmentRequest:
    request = db.get(ReplenishmentRequest, request_id)
    if not request:
        raise BusinessException("request not found", 404)
    if request.audit_status != "pending":
        raise BusinessException("only pending request can be approved")
    if not db.get(User, audited_by):
        raise BusinessException("auditor not found", 404)
    request.audit_status = "approved"
    request.audited_by = audited_by
    request.audit_time = now_local()
    db.flush()
    return request


def reject_request(db: Session, request_id: int, audited_by: int) -> ReplenishmentRequest:
    request = db.get(ReplenishmentRequest, request_id)
    if not request:
        raise BusinessException("request not found", 404)
    if request.audit_status != "pending":
        raise BusinessException("only pending request can be rejected")
    request.audit_status = "rejected"
    request.audited_by = audited_by
    request.audit_time = now_local()
    db.flush()
    return request


def invalidate_request(db: Session, request_id: int) -> ReplenishmentRequest | None:
    request = db.get(ReplenishmentRequest, request_id)
    if not request or request.audit_status != "approved" or request.generated_outbound_order_id is not None:
        return request
    request.audit_status = "invalidated"
    request.generated_outbound_order_id = None
    db.flush()
    return request


def convert_to_outbound(
    db: Session,
    request_id: int,
    source_warehouse_id: int | None = None,
    handled_by: int = 1,
) -> list[OutboundOrder]:
    request = db.get(ReplenishmentRequest, request_id)
    if not request:
        raise BusinessException("request not found", 404)
    if request.audit_status != "approved":
        raise BusinessException("only approved request can be converted")

    if source_warehouse_id is None:
        allocations = allocate_source_warehouses(
            db,
            product_id=request.product_id,
            request_quantity=request.request_quantity,
        )
    else:
        selected_inventory = ensure_source_warehouse_has_stock(
            db,
            product_id=request.product_id,
            request_quantity=request.request_quantity,
            source_warehouse_id=source_warehouse_id,
        )
        allocations = [(selected_inventory, request.request_quantity)]

    outbounds: list[OutboundOrder] = []
    for inventory, allocated_quantity in allocations:
        reserve_stock(
            db,
            product_id=request.product_id,
            warehouse_id=inventory.warehouse_id,
            quantity=allocated_quantity,
        )
        outbound = create_outbound_order(
            db,
            OutboundOrderCreate(
                source_warehouse_id=inventory.warehouse_id,
                target_store_id=request.store_id,
                handled_by=handled_by,
                source_request_id=request.id,
                remark=request.request_reason,
                items=[{"product_id": request.product_id, "quantity": allocated_quantity, "batch_no": None}],
            ),
        )
        outbounds.append(outbound)

    request.audit_status = "converted"
    request.generated_outbound_order_id = outbounds[0].id if outbounds else None
    db.flush()
    return outbounds
