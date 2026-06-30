from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import invalidate_business_cache
from app.core.exceptions import BusinessException
from app.models.inbound import InboundItem, InboundOrder
from app.models.product import Product
from app.models.purchase import PurchaseOrder
from app.models.supplier import Supplier, SupplierProduct
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.inbound import InboundOrderCreate
from app.services.inventory_service import generate_doc_no, increase_stock


def create_inbound_order(db: Session, payload: InboundOrderCreate) -> InboundOrder:
    if not db.get(Supplier, payload.supplier_id):
        raise BusinessException("supplier not found", 404)
    if not db.get(Warehouse, payload.warehouse_id):
        raise BusinessException("warehouse not found", 404)
    if not db.get(User, payload.handled_by):
        raise BusinessException("handler not found", 404)
    total = db.scalar(select(func.count(InboundOrder.id))) or 0
    order = InboundOrder(
        inbound_no=generate_doc_no("IN", total + 1),
        purchase_order_id=payload.purchase_order_id,
        supplier_id=payload.supplier_id,
        warehouse_id=payload.warehouse_id,
        handled_by=payload.handled_by,
        status=payload.status,
        remark=payload.remark,
    )
    for item in payload.items:
        if item.quantity <= 0:
            raise BusinessException("quantity must be greater than 0")
        if not db.get(Product, item.product_id):
            raise BusinessException(f"product {item.product_id} not found", 404)
        relation = db.scalar(
            select(SupplierProduct.id).where(
                SupplierProduct.supplier_id == payload.supplier_id,
                SupplierProduct.product_id == item.product_id,
            )
        )
        if not relation:
            raise BusinessException("所选供应商不供应当前商品")
        order.items.append(
            InboundItem(
                product_id=item.product_id,
                quantity=item.quantity,
                batch_no=item.batch_no,
                production_date=item.production_date,
                expiry_date=item.expiry_date,
            )
        )
    db.add(order)
    db.flush()
    return order


def create_from_purchase(db: Session, purchase_order_id: int, handled_by: int, warehouse_id: int) -> InboundOrder:
    order = db.get(PurchaseOrder, purchase_order_id)
    if not order:
        raise BusinessException("purchase order not found", 404)
    if order.status in {"cancelled"}:
        raise BusinessException("cancelled order cannot create inbound")
    payload = InboundOrderCreate(
        purchase_order_id=order.id,
        supplier_id=order.supplier_id,
        warehouse_id=warehouse_id,
        handled_by=handled_by,
        items=[
            {
                "product_id": item.product_id,
                "quantity": item.purchase_quantity,
                "batch_no": None,
                "production_date": None,
                "expiry_date": None,
            }
            for item in order.items
        ],
    )
    return create_inbound_order(db, payload)


def complete_inbound_order(db: Session, inbound_order_id: int) -> InboundOrder:
    order = db.get(InboundOrder, inbound_order_id)
    if not order:
        raise BusinessException("inbound order not found", 404)
    if order.status != "pending":
        raise BusinessException("only pending inbound order can be completed")
    for item in order.items:
        increase_stock(
            db,
            product_id=item.product_id,
            location_type="warehouse",
            warehouse_id=order.warehouse_id,
            quantity=item.quantity,
            operator_id=order.handled_by,
            transaction_type="purchase_inbound",
            related_doc_type="inbound_order",
            related_doc_id=order.id,
            remark=order.remark,
        )
    order.status = "completed"
    if order.purchase_order_id:
        purchase_order = db.get(PurchaseOrder, order.purchase_order_id)
        if purchase_order:
            received_map = {
                row[0]: row[1]
                for row in db.execute(
                    select(InboundItem.product_id, func.sum(InboundItem.quantity))
                    .join(InboundOrder, InboundOrder.id == InboundItem.inbound_order_id)
                    .where(
                        InboundOrder.purchase_order_id == purchase_order.id,
                        InboundOrder.status == "completed",
                    )
                    .group_by(InboundItem.product_id)
                ).all()
            }
            fully_received = all(received_map.get(item.product_id, 0) >= item.purchase_quantity for item in purchase_order.items)
            purchase_order.status = "completed" if fully_received else "partially_arrived"
    invalidate_business_cache()
    db.flush()
    return order
