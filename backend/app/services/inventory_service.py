from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.cache import invalidate_business_cache
from app.core.exceptions import BusinessException
from app.models.distributed import CrossWarehouseTransferOrder
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.store import Store
from app.models.transaction import StockTransaction
from app.models.warehouse import Warehouse
from app.utils.datetime_utils import now_local


def generate_doc_no(prefix: str, count: int) -> str:
    return f"{prefix}{now_local():%Y%m%d}{count:04d}"


def generate_transaction_no(db: Session) -> str:
    total = db.scalar(select(func.count(StockTransaction.id))) or 0
    return generate_doc_no("TX", total + 1)


def get_available_quantity(inventory: Inventory) -> int:
    return int(inventory.current_quantity or 0) - int(inventory.frozen_quantity or 0)


def reserve_stock(
    db: Session,
    *,
    product_id: int,
    warehouse_id: int,
    quantity: int,
) -> Inventory:
    if quantity <= 0:
        raise BusinessException("quantity must be greater than 0")
    inventory = get_or_create_inventory(
        db,
        product_id=product_id,
        location_type="warehouse",
        warehouse_id=warehouse_id,
    )
    if get_available_quantity(inventory) < quantity:
        raise BusinessException("warehouse available stock is insufficient for reservation")
    inventory.frozen_quantity += quantity
    inventory.last_updated_at = now_local()
    db.flush()
    return inventory


def release_reserved_stock(
    db: Session,
    *,
    product_id: int,
    warehouse_id: int,
    quantity: int,
) -> Inventory:
    if quantity <= 0:
        raise BusinessException("quantity must be greater than 0")
    inventory = get_or_create_inventory(
        db,
        product_id=product_id,
        location_type="warehouse",
        warehouse_id=warehouse_id,
    )
    if int(inventory.frozen_quantity or 0) < quantity:
        raise BusinessException("reserved stock is insufficient to release")
    inventory.frozen_quantity -= quantity
    inventory.last_updated_at = now_local()
    db.flush()
    return inventory


def get_or_create_inventory(
    db: Session,
    *,
    product_id: int,
    location_type: str,
    warehouse_id: int | None = None,
    store_id: int | None = None,
    safety_stock: int = 0,
    max_stock: int = 0,
) -> Inventory:
    query = select(Inventory).where(
        Inventory.product_id == product_id,
        Inventory.location_type == location_type,
        Inventory.warehouse_id == warehouse_id,
        Inventory.store_id == store_id,
    )
    inventory = db.scalar(query)
    if inventory:
        return inventory
    if location_type == "warehouse" and not warehouse_id:
        raise BusinessException("warehouse inventory requires warehouse_id")
    if location_type == "store" and not store_id:
        raise BusinessException("store inventory requires store_id")
    inventory = Inventory(
        product_id=product_id,
        location_type=location_type,
        warehouse_id=warehouse_id,
        store_id=store_id,
        safety_stock=safety_stock,
        max_stock=max_stock,
        current_quantity=0,
        frozen_quantity=0,
        last_updated_at=now_local(),
    )
    db.add(inventory)
    db.flush()
    return inventory


def create_stock_transaction(db: Session, **kwargs: Any) -> StockTransaction:
    transaction = StockTransaction(transaction_no=generate_transaction_no(db), transaction_time=now_local(), **kwargs)
    db.add(transaction)
    db.flush()
    return transaction


def increase_stock(
    db: Session,
    *,
    product_id: int,
    location_type: str,
    quantity: int,
    warehouse_id: int | None = None,
    store_id: int | None = None,
    operator_id: int | None = None,
    transaction_type: str,
    related_doc_type: str | None = None,
    related_doc_id: int | None = None,
    remark: str | None = None,
    safety_stock: int = 0,
    max_stock: int = 0,
    source_location_type: str | None = None,
    source_warehouse_id: int | None = None,
    source_store_id: int | None = None,
) -> Inventory:
    if quantity <= 0:
        raise BusinessException("quantity must be greater than 0")
    inventory = get_or_create_inventory(
        db,
        product_id=product_id,
        location_type=location_type,
        warehouse_id=warehouse_id,
        store_id=store_id,
        safety_stock=safety_stock,
        max_stock=max_stock,
    )
    before_quantity = inventory.current_quantity
    inventory.current_quantity += quantity
    inventory.last_updated_at = now_local()
    create_stock_transaction(
        db,
        product_id=product_id,
        transaction_type=transaction_type,
        source_location_type=source_location_type,
        source_warehouse_id=source_warehouse_id,
        source_store_id=source_store_id,
        target_location_type=location_type,
        target_warehouse_id=warehouse_id,
        target_store_id=store_id,
        change_quantity=quantity,
        before_quantity=before_quantity,
        after_quantity=inventory.current_quantity,
        operated_by=operator_id,
        related_doc_type=related_doc_type,
        related_doc_id=related_doc_id,
        remark=remark,
    )
    return inventory


def decrease_stock(
    db: Session,
    *,
    product_id: int,
    location_type: str,
    quantity: int,
    warehouse_id: int | None = None,
    store_id: int | None = None,
    operator_id: int | None = None,
    transaction_type: str,
    related_doc_type: str | None = None,
    related_doc_id: int | None = None,
    remark: str | None = None,
    target_location_type: str | None = None,
    target_warehouse_id: int | None = None,
    target_store_id: int | None = None,
) -> Inventory:
    if quantity <= 0:
        raise BusinessException("quantity must be greater than 0")
    inventory = get_or_create_inventory(
        db,
        product_id=product_id,
        location_type=location_type,
        warehouse_id=warehouse_id,
        store_id=store_id,
    )
    available_quantity = inventory.current_quantity - inventory.frozen_quantity
    if available_quantity < quantity:
        raise BusinessException("库存不足，禁止出库")
    before_quantity = inventory.current_quantity
    inventory.current_quantity -= quantity
    inventory.last_updated_at = now_local()
    create_stock_transaction(
        db,
        product_id=product_id,
        transaction_type=transaction_type,
        source_location_type=location_type,
        source_warehouse_id=warehouse_id,
        source_store_id=store_id,
        target_location_type=target_location_type,
        target_warehouse_id=target_warehouse_id,
        target_store_id=target_store_id,
        change_quantity=-quantity,
        before_quantity=before_quantity,
        after_quantity=inventory.current_quantity,
        operated_by=operator_id,
        related_doc_type=related_doc_type,
        related_doc_id=related_doc_id,
        remark=remark,
    )
    return inventory


def transfer_stock(
    db: Session,
    *,
    product_id: int,
    source_warehouse_id: int,
    target_warehouse_id: int,
    quantity: int,
    operator_id: int | None = None,
    related_doc_id: int | None = None,
    remark: str | None = None,
) -> None:
    if source_warehouse_id == target_warehouse_id:
        raise BusinessException("source_warehouse_id cannot equal target_warehouse_id")
    decrease_stock(
        db,
        product_id=product_id,
        location_type="warehouse",
        warehouse_id=source_warehouse_id,
        quantity=quantity,
        operator_id=operator_id,
        transaction_type="cross_warehouse_transfer",
        related_doc_type="cross_warehouse_transfer",
        related_doc_id=related_doc_id,
        remark=remark,
        target_location_type="warehouse",
        target_warehouse_id=target_warehouse_id,
    )
    increase_stock(
        db,
        product_id=product_id,
        location_type="warehouse",
        warehouse_id=target_warehouse_id,
        quantity=quantity,
        operator_id=operator_id,
        transaction_type="cross_warehouse_transfer",
        related_doc_type="cross_warehouse_transfer",
        related_doc_id=related_doc_id,
        remark=remark,
        source_location_type="warehouse",
        source_warehouse_id=source_warehouse_id,
    )


def adjust_stock(
    db: Session,
    *,
    product_id: int,
    location_type: str,
    new_quantity: int,
    warehouse_id: int | None = None,
    store_id: int | None = None,
    operator_id: int | None = None,
    remark: str | None = None,
) -> Inventory:
    if new_quantity < 0:
        raise BusinessException("new_quantity cannot be negative")
    inventory = get_or_create_inventory(
        db,
        product_id=product_id,
        location_type=location_type,
        warehouse_id=warehouse_id,
        store_id=store_id,
    )
    before_quantity = inventory.current_quantity
    inventory.current_quantity = new_quantity
    inventory.last_updated_at = now_local()
    create_stock_transaction(
        db,
        product_id=product_id,
        transaction_type="inventory_adjustment",
        source_location_type=location_type,
        source_warehouse_id=warehouse_id,
        source_store_id=store_id,
        target_location_type=location_type,
        target_warehouse_id=warehouse_id,
        target_store_id=store_id,
        change_quantity=new_quantity - before_quantity,
        before_quantity=before_quantity,
        after_quantity=new_quantity,
        operated_by=operator_id,
        related_doc_type="inventory_adjustment",
        related_doc_id=inventory.id,
        remark=remark,
    )
    invalidate_business_cache()
    return inventory


def list_inventory(db: Session, page: int, page_size: int, keyword: str | None = None) -> tuple[list[Inventory], int]:
    query: Select[tuple[Inventory]] = select(Inventory).options(
        joinedload(Inventory.product),
        joinedload(Inventory.warehouse),
        joinedload(Inventory.store),
    ).order_by(
        Inventory.id.desc(),
        Inventory.location_type.asc(),
        Inventory.warehouse_id.asc(),
        Inventory.store_id.asc(),
        Inventory.product_id.asc(),
    )
    if keyword:
        query = query.join(Product).where(Product.name.contains(keyword))
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
    return items, total


def pick_best_source_warehouse(
    db: Session,
    *,
    product_id: int,
    request_quantity: int,
) -> Inventory:
    inventories = list(
        db.scalars(
            select(Inventory)
            .options(joinedload(Inventory.warehouse))
            .where(
                Inventory.product_id == product_id,
                Inventory.location_type == "warehouse",
                Inventory.warehouse_id.is_not(None),
            )
        )
    )
    candidates = [
        inventory
        for inventory in inventories
        if get_available_quantity(inventory) >= request_quantity
    ]
    if not candidates:
        raise BusinessException("所有仓库库存不足，无法生成出库单")
    candidates.sort(
        key=lambda inventory: (
            -(get_available_quantity(inventory) - request_quantity),
            inventory.warehouse_id or 0,
        )
    )
    return candidates[0]


def ensure_source_warehouse_has_stock(
    db: Session,
    *,
    product_id: int,
    request_quantity: int,
    source_warehouse_id: int,
) -> Inventory:
    warehouse = db.get(Warehouse, source_warehouse_id)
    if not warehouse:
        raise BusinessException("warehouse not found", 404)
    inventory = db.scalar(
        select(Inventory)
        .options(joinedload(Inventory.warehouse))
        .where(
            Inventory.product_id == product_id,
            Inventory.location_type == "warehouse",
            Inventory.warehouse_id == source_warehouse_id,
        )
    )
    if not inventory or get_available_quantity(inventory) < request_quantity:
        raise BusinessException("指定仓库库存不足，无法生成出库单")
    return inventory


def allocate_source_warehouses(
    db: Session,
    *,
    product_id: int,
    request_quantity: int,
) -> list[tuple[Inventory, int]]:
    if request_quantity <= 0:
        raise BusinessException("request_quantity must be greater than 0")
    inventories = list(
        db.scalars(
            select(Inventory)
            .options(joinedload(Inventory.warehouse))
            .where(
                Inventory.product_id == product_id,
                Inventory.location_type == "warehouse",
                Inventory.warehouse_id.is_not(None),
            )
        )
    )
    candidates = [inventory for inventory in inventories if get_available_quantity(inventory) > 0]
    if not candidates:
        raise BusinessException("all warehouses are insufficient to fulfill the request")

    single_candidates = [
        inventory for inventory in candidates if get_available_quantity(inventory) >= request_quantity
    ]
    if single_candidates:
        single_candidates.sort(
            key=lambda inventory: (
                -get_available_quantity(inventory),
                inventory.warehouse_id or 0,
            )
        )
        return [(single_candidates[0], request_quantity)]

    candidates.sort(
        key=lambda inventory: (
            -get_available_quantity(inventory),
            inventory.warehouse_id or 0,
        )
    )
    remaining = request_quantity
    allocations: list[tuple[Inventory, int]] = []
    for inventory in candidates:
        if remaining <= 0:
            break
        available = get_available_quantity(inventory)
        if available <= 0:
            continue
        allocated_quantity = min(available, remaining)
        allocations.append((inventory, allocated_quantity))
        remaining -= allocated_quantity

    if remaining > 0:
        raise BusinessException("all warehouses are insufficient to fulfill the request")
    return allocations


def get_inventory_warnings(db: Session) -> list[dict[str, Any]]:
    query = (
        select(Inventory, Product.name, Warehouse.name, Store.name)
        .join(Product, Product.id == Inventory.product_id)
        .outerjoin(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .outerjoin(Store, Store.id == Inventory.store_id)
    )
    warnings: list[dict[str, Any]] = []
    for inventory, product_name, warehouse_name, store_name in db.execute(query).all():
        location_name = warehouse_name if inventory.location_type == "warehouse" else store_name
        warning_type = None
        if inventory.current_quantity <= inventory.safety_stock * 0.5:
            warning_type = "critical_stockout"
        elif inventory.current_quantity <= inventory.safety_stock:
            warning_type = "stockout"
        elif inventory.current_quantity >= max(inventory.max_stock, inventory.safety_stock * 4):
            warning_type = "overstock"
        if warning_type:
            warnings.append(
                {
                    "product_id": inventory.product_id,
                    "product_name": product_name,
                    "location_type": inventory.location_type,
                    "location_name": location_name,
                    "current_quantity": inventory.current_quantity,
                    "frozen_quantity": inventory.frozen_quantity,
                    "available_quantity": get_available_quantity(inventory),
                    "safety_stock": inventory.safety_stock,
                    "max_stock": inventory.max_stock,
                    "warning_type": warning_type,
                    "warning_message": f"{product_name} 在 {location_name} 触发 {warning_type} 预警",
                }
            )
    return warnings


def get_inventory_summary(db: Session) -> dict[str, Any]:
    items = list(db.scalars(select(Inventory)))
    total_inventory = sum(item.current_quantity for item in items)
    warehouse_inventory = sum(item.current_quantity for item in items if item.location_type == "warehouse")
    store_inventory = sum(item.current_quantity for item in items if item.location_type == "store")
    return {
        "total_inventory_quantity": total_inventory,
        "warehouse_inventory_quantity": warehouse_inventory,
        "store_inventory_quantity": store_inventory,
        "warning_count": len(get_inventory_warnings(db)),
        "inventory_record_count": len(items),
    }


def get_product_distribution(db: Session, product_id: int) -> list[dict[str, Any]]:
    query = select(Inventory, Warehouse.name, Store.name).outerjoin(Warehouse).outerjoin(Store).where(Inventory.product_id == product_id)
    data = []
    for inventory, warehouse_name, store_name in db.execute(query).all():
        data.append(
            {
                "location_type": inventory.location_type,
                "warehouse_id": inventory.warehouse_id,
                "store_id": inventory.store_id,
                "location_name": warehouse_name if inventory.location_type == "warehouse" else store_name,
                "current_quantity": inventory.current_quantity,
                "frozen_quantity": inventory.frozen_quantity,
                "available_quantity": get_available_quantity(inventory),
                "safety_stock": inventory.safety_stock,
                "max_stock": inventory.max_stock,
            }
        )
    return data


def create_cross_warehouse_transfer(db: Session, payload: dict[str, Any]) -> CrossWarehouseTransferOrder:
    if payload["quantity"] <= 0:
        raise BusinessException("quantity must be greater than 0")
    if payload["source_warehouse_id"] == payload["target_warehouse_id"]:
        raise BusinessException("source_warehouse_id and target_warehouse_id cannot be same")
    source_inventory = get_or_create_inventory(
        db,
        product_id=payload["product_id"],
        location_type="warehouse",
        warehouse_id=payload["source_warehouse_id"],
    )
    if source_inventory.current_quantity - source_inventory.frozen_quantity < payload["quantity"]:
        raise BusinessException("库存不足，无法创建跨仓调拨")
    total = db.scalar(select(func.count(CrossWarehouseTransferOrder.id))) or 0
    order = CrossWarehouseTransferOrder(
        transfer_no=generate_doc_no("TR", total + 1),
        source_warehouse_id=payload["source_warehouse_id"],
        target_warehouse_id=payload["target_warehouse_id"],
        product_id=payload["product_id"],
        quantity=payload["quantity"],
        created_by=payload.get("created_by"),
        reason=payload.get("reason"),
        status="pending",
    )
    db.add(order)
    db.flush()
    return order


def complete_cross_warehouse_transfer(db: Session, transfer_id: int) -> CrossWarehouseTransferOrder:
    order = db.get(CrossWarehouseTransferOrder, transfer_id)
    if not order:
        raise BusinessException("transfer order not found", 404)
    if order.status != "pending":
        raise BusinessException("only pending transfer can be completed")
    transfer_stock(
        db,
        product_id=order.product_id,
        source_warehouse_id=order.source_warehouse_id,
        target_warehouse_id=order.target_warehouse_id,
        quantity=order.quantity,
        operator_id=order.created_by,
        related_doc_id=order.id,
        remark=order.reason,
    )
    order.status = "completed"
    order.completed_at = now_local()
    invalidate_business_cache()
    db.flush()
    return order


def get_rebalance_suggestions(db: Session) -> list[dict[str, Any]]:
    grouped: dict[int, list[Inventory]] = defaultdict(list)
    for item in db.scalars(select(Inventory).where(Inventory.location_type == "warehouse")):
        grouped[item.product_id].append(item)
    suggestions: list[dict[str, Any]] = []
    for product_id, inventories in grouped.items():
        low_items = [item for item in inventories if item.current_quantity < item.safety_stock]
        high_items = [item for item in inventories if item.current_quantity > max(item.max_stock, item.safety_stock * 3)]
        for low in low_items:
            for high in high_items:
                if low.warehouse_id != high.warehouse_id:
                    suggestions.append(
                        {
                            "product_id": product_id,
                            "source_warehouse_id": high.warehouse_id,
                            "target_warehouse_id": low.warehouse_id,
                            "suggested_quantity": min(high.current_quantity - high.safety_stock, low.safety_stock - low.current_quantity),
                        }
                    )
    return [item for item in suggestions if item["suggested_quantity"] > 0]
