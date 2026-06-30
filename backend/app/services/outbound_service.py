from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import invalidate_business_cache
from app.core.exceptions import BusinessException
from app.models.outbound import OutboundItem, OutboundOrder
from app.models.replenishment import ReplenishmentRequest
from app.models.store import Store
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.outbound import OutboundOrderCreate
from app.services.inventory_service import decrease_stock, generate_doc_no, get_or_create_inventory, increase_stock, release_reserved_stock


def create_outbound_order(db: Session, payload: OutboundOrderCreate) -> OutboundOrder:
    if not db.get(Warehouse, payload.source_warehouse_id):
        raise BusinessException("warehouse not found", 404)
    if not db.get(Store, payload.target_store_id):
        raise BusinessException("store not found", 404)
    if not db.get(User, payload.handled_by):
        raise BusinessException("handler not found", 404)
    total = db.scalar(select(func.count(OutboundOrder.id))) or 0
    order = OutboundOrder(
        outbound_no=generate_doc_no("OUT", total + 1),
        source_warehouse_id=payload.source_warehouse_id,
        target_store_id=payload.target_store_id,
        handled_by=payload.handled_by,
        source_request_id=payload.source_request_id,
        remark=payload.remark,
        status="pending",
    )
    for item in payload.items:
        if item.quantity <= 0:
            raise BusinessException("quantity must be greater than 0")
        order.items.append(OutboundItem(product_id=item.product_id, quantity=item.quantity, batch_no=item.batch_no))
    db.add(order)
    db.flush()
    return order


def ship_outbound_order(db: Session, outbound_order_id: int) -> OutboundOrder:
    order = db.get(OutboundOrder, outbound_order_id)
    if not order:
        raise BusinessException("outbound order not found", 404)
    if order.status != "pending":
        raise BusinessException("only pending outbound order can be shipped")
    for item in order.items:
        source_inventory = get_or_create_inventory(
            db,
            product_id=item.product_id,
            location_type="warehouse",
            warehouse_id=order.source_warehouse_id,
        )
        if int(source_inventory.frozen_quantity or 0) >= item.quantity:
            release_reserved_stock(
                db,
                product_id=item.product_id,
                warehouse_id=order.source_warehouse_id,
                quantity=item.quantity,
            )
        decrease_stock(
            db,
            product_id=item.product_id,
            location_type="warehouse",
            warehouse_id=order.source_warehouse_id,
            quantity=item.quantity,
            operator_id=order.handled_by,
            transaction_type="store_outbound",
            related_doc_type="outbound_order",
            related_doc_id=order.id,
            remark=order.remark,
            target_location_type="store",
            target_store_id=order.target_store_id,
        )
    order.status = "shipped"
    if order.source_request_id:
        request = db.get(ReplenishmentRequest, order.source_request_id)
        if request:
            request.audit_status = "converted"
            request.generated_outbound_order_id = order.id
    invalidate_business_cache()
    db.flush()
    return order


def sign_outbound_order(db: Session, outbound_order_id: int) -> OutboundOrder:
    order = db.get(OutboundOrder, outbound_order_id)
    if not order:
        raise BusinessException("outbound order not found", 404)
    if order.status != "shipped":
        raise BusinessException("only shipped outbound order can be signed")
    for item in order.items:
        source_inventory = get_or_create_inventory(
            db,
            product_id=item.product_id,
            location_type="warehouse",
            warehouse_id=order.source_warehouse_id,
        )
        increase_stock(
            db,
            product_id=item.product_id,
            location_type="store",
            store_id=order.target_store_id,
            quantity=item.quantity,
            operator_id=order.handled_by,
            transaction_type="store_inbound",
            related_doc_type="outbound_order",
            related_doc_id=order.id,
            remark=order.remark,
            safety_stock=source_inventory.safety_stock,
            max_stock=max(source_inventory.max_stock, source_inventory.safety_stock * 4),
            source_location_type="warehouse",
            source_warehouse_id=order.source_warehouse_id,
        )
    order.status = "signed"
    invalidate_business_cache()
    db.flush()
    return order


def cancel_outbound_order(db: Session, outbound_order_id: int) -> OutboundOrder:
    order = db.get(OutboundOrder, outbound_order_id)
    if not order:
        raise BusinessException("outbound order not found", 404)
    if order.status == "shipped":
        raise BusinessException("shipped outbound order cannot be cancelled")
    if order.status == "pending":
        for item in order.items:
            source_inventory = get_or_create_inventory(
                db,
                product_id=item.product_id,
                location_type="warehouse",
                warehouse_id=order.source_warehouse_id,
            )
            if int(source_inventory.frozen_quantity or 0) >= item.quantity:
                release_reserved_stock(
                    db,
                    product_id=item.product_id,
                    warehouse_id=order.source_warehouse_id,
                    quantity=item.quantity,
                )
    order.status = "cancelled"
    db.flush()
    return order
