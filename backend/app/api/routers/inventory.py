from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db_dep
from app.core.cache import cache
from app.core.response import page_response, success_response
from app.models.inventory import Inventory
from app.schemas.inventory import CrossWarehouseTransferCreate, InventoryAdjustRequest, InventoryRead
from app.services.inventory_service import (
    adjust_stock,
    complete_cross_warehouse_transfer,
    create_cross_warehouse_transfer,
    get_inventory_summary,
    get_inventory_warnings,
    get_product_distribution,
    list_inventory,
    get_rebalance_suggestions,
)
from app.utils.pagination import normalize_pagination

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def serialize_inventory(item: Inventory) -> dict:
    data = InventoryRead.model_validate(item).model_dump()
    data["product_name"] = item.product.name if item.product else None
    data["warehouse_name"] = item.warehouse.name if item.warehouse else None
    data["store_name"] = item.store.name if item.store else None
    data["location_name"] = data["warehouse_name"] if item.location_type == "warehouse" else data["store_name"]
    data["available_quantity"] = int(item.current_quantity or 0) - int(item.frozen_quantity or 0)
    return data


@router.get("")
def inventory_list(page: int = 1, page_size: int = 20, keyword: str | None = None, db: Session = Depends(get_db_dep)):
    page, page_size = normalize_pagination(page, page_size)
    items, total = list_inventory(db, page, page_size, keyword)
    return page_response([serialize_inventory(item) for item in items], total, page, page_size)


@router.get("/product/{product_id}/distribution")
def product_distribution(product_id: int, db: Session = Depends(get_db_dep)):
    return success_response(get_product_distribution(db, product_id))


@router.get("/store/{store_id}")
def store_inventory(store_id: int, db: Session = Depends(get_db_dep)):
    items = list(
        db.scalars(
            select(Inventory)
            .options(joinedload(Inventory.product), joinedload(Inventory.warehouse), joinedload(Inventory.store))
            .where(Inventory.store_id == store_id)
        )
    )
    return success_response([serialize_inventory(item) for item in items])


@router.get("/warehouse/{warehouse_id}")
def warehouse_inventory(warehouse_id: int, db: Session = Depends(get_db_dep)):
    items = list(
        db.scalars(
            select(Inventory)
            .options(joinedload(Inventory.product), joinedload(Inventory.warehouse), joinedload(Inventory.store))
            .where(Inventory.warehouse_id == warehouse_id)
        )
    )
    return success_response([serialize_inventory(item) for item in items])


@router.get("/warnings")
def warnings(db: Session = Depends(get_db_dep)):
    return success_response(get_inventory_warnings(db))


@router.get("/summary")
def summary(db: Session = Depends(get_db_dep)):
    cached = cache.get("inventory:summary")
    if cached is not None:
        return success_response(cached)
    data = get_inventory_summary(db)
    cache.set("inventory:summary", data)
    return success_response(data)


@router.post("/adjust")
def adjust(payload: InventoryAdjustRequest, db: Session = Depends(get_db_dep)):
    try:
        item = adjust_stock(db, **payload.model_dump())
        db.commit()
        db.refresh(item)
        return success_response(InventoryRead.model_validate(item).model_dump())
    except Exception:
        db.rollback()
        raise


@router.post("/cross-warehouse-transfer")
def create_transfer(payload: CrossWarehouseTransferCreate, db: Session = Depends(get_db_dep)):
    item = create_cross_warehouse_transfer(db, payload.model_dump())
    db.commit()
    return success_response({"id": item.id, "transfer_no": item.transfer_no, "status": item.status})


@router.post("/cross-warehouse-transfer/{transfer_id}/complete")
def complete_transfer(transfer_id: int, db: Session = Depends(get_db_dep)):
    try:
        item = complete_cross_warehouse_transfer(db, transfer_id)
        db.commit()
        return success_response({"id": item.id, "transfer_no": item.transfer_no, "status": item.status})
    except Exception:
        db.rollback()
        raise


@router.get("/rebalance-suggestions")
def rebalance(db: Session = Depends(get_db_dep)):
    return success_response(get_rebalance_suggestions(db))
