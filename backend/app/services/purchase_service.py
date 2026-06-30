from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.product import Product
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.supplier import Supplier, SupplierProduct
from app.models.user import User
from app.schemas.purchase import PurchaseOrderCreate
from app.services.inventory_service import generate_doc_no


def create_purchase_order(db: Session, payload: PurchaseOrderCreate) -> PurchaseOrder:
    if not db.get(Supplier, payload.supplier_id):
        raise BusinessException("supplier not found", 404)
    if not db.get(User, payload.created_by):
        raise BusinessException("creator not found", 404)
    if not payload.items:
        raise BusinessException("purchase order items cannot be empty")
    total = db.scalar(select(func.count(PurchaseOrder.id))) or 0
    order = PurchaseOrder(
        order_no=generate_doc_no("PO", total + 1),
        supplier_id=payload.supplier_id,
        expected_arrival_date=payload.expected_arrival_date,
        created_by=payload.created_by,
        status="pending",
        remark=payload.remark,
        total_amount=Decimal("0.00"),
    )
    total_amount = Decimal("0.00")
    for item in payload.items:
        if item.purchase_quantity <= 0:
            raise BusinessException("purchase_quantity must be greater than 0")
        if item.purchase_price < 0:
            raise BusinessException("purchase_price must be greater than or equal to 0")
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
        subtotal = item.purchase_price * item.purchase_quantity
        total_amount += subtotal
        order.items.append(
            PurchaseOrderItem(
                product_id=item.product_id,
                purchase_quantity=item.purchase_quantity,
                purchase_price=item.purchase_price,
                subtotal_amount=subtotal,
            )
        )
    order.total_amount = total_amount
    db.add(order)
    db.flush()
    return order


def confirm_purchase_order(db: Session, purchase_order_id: int) -> PurchaseOrder:
    order = db.get(PurchaseOrder, purchase_order_id)
    if not order:
        raise BusinessException("purchase order not found", 404)
    if order.status == "cancelled":
        raise BusinessException("cancelled order cannot be confirmed")
    order.status = "confirmed"
    db.flush()
    return order


def cancel_purchase_order(db: Session, purchase_order_id: int) -> PurchaseOrder:
    order = db.get(PurchaseOrder, purchase_order_id)
    if not order:
        raise BusinessException("purchase order not found", 404)
    if order.status == "completed":
        raise BusinessException("completed order cannot be cancelled")
    order.status = "cancelled"
    db.flush()
    return order
