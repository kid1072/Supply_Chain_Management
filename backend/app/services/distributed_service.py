from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import invalidate_business_cache
from app.core.database import get_database_dialect_name, get_database_runtime_profile
from app.models.distributed import DistributedSyncLog
from app.models.inventory import Inventory
from app.models.store import Store
from app.models.transaction import StockTransaction
from app.models.warehouse import Warehouse
from app.services.inventory_service import complete_cross_warehouse_transfer, create_cross_warehouse_transfer
from app.utils.datetime_utils import now_local


def overview(db: Session) -> dict:
    runtime_profile = get_database_runtime_profile(db)
    warehouses = list(db.scalars(select(Warehouse)))
    stores = list(db.scalars(select(Store)))
    inventory_rows = list(db.scalars(select(Inventory)))
    by_warehouse = defaultdict(int)
    by_store = defaultdict(int)
    by_region = defaultdict(int)
    for inv in inventory_rows:
        if inv.warehouse_id:
            by_warehouse[inv.warehouse_id] += inv.current_quantity
        if inv.store_id:
            by_store[inv.store_id] += inv.current_quantity
    for wh in warehouses:
        by_region[wh.region or "未知"] += by_warehouse[wh.id]
    for store in stores:
        by_region[store.region or "未知"] += by_store[store.id]
    return {
        "backend": runtime_profile,
        "warehouses": [{"warehouse_id": wh.id, "warehouse_code": wh.warehouse_code, "quantity": by_warehouse[wh.id]} for wh in warehouses],
        "stores": [{"store_id": st.id, "store_code": st.store_code, "quantity": by_store[st.id]} for st in stores],
        "regions": [{"region": region, "quantity": qty} for region, qty in by_region.items()],
    }


def run_reconciliation(db: Session) -> dict:
    runtime_profile = get_database_runtime_profile(db)
    started_at = now_local()
    checked = 0
    mismatch_records = []
    for inventory in db.scalars(select(Inventory)):
        checked += 1
        inflow = 0
        outflow = 0
        for tx in db.scalars(select(StockTransaction).where(StockTransaction.product_id == inventory.product_id)):
            if inventory.location_type == "warehouse" and inventory.warehouse_id:
                if tx.target_location_type == "warehouse" and tx.target_warehouse_id == inventory.warehouse_id:
                    inflow += max(tx.change_quantity, 0)
                if tx.source_location_type == "warehouse" and tx.source_warehouse_id == inventory.warehouse_id:
                    outflow += abs(min(tx.change_quantity, 0))
            if inventory.location_type == "store" and inventory.store_id:
                if tx.target_location_type == "store" and tx.target_store_id == inventory.store_id:
                    inflow += max(tx.change_quantity, 0)
                if tx.source_location_type == "store" and tx.source_store_id == inventory.store_id:
                    outflow += abs(min(tx.change_quantity, 0))
        theoretical = inflow - outflow
        if theoretical != inventory.current_quantity:
            mismatch_records.append(
                {
                    "inventory_id": inventory.id,
                    "product_id": inventory.product_id,
                    "location_type": inventory.location_type,
                    "warehouse_id": inventory.warehouse_id,
                    "store_id": inventory.store_id,
                    "current_quantity": inventory.current_quantity,
                    "theoretical_quantity": theoretical,
                }
            )
    log = DistributedSyncLog(
        node_name="oceanbase-primary-node" if runtime_profile["mode"] == "oceanbase-primary" else "sqlite-fallback-node",
        node_type=get_database_dialect_name(db),
        region="distributed-core",
        sync_type="reconciliation",
        status="completed",
        checked_records=checked,
        mismatch_records=len(mismatch_records),
        started_at=started_at,
        finished_at=now_local(),
        message=f"reconciliation finished on {runtime_profile['mode']}",
    )
    db.add(log)
    db.flush()
    return {
        "checked_records": checked,
        "mismatch_records": mismatch_records,
        "log_id": log.id,
        "backend_mode": runtime_profile["mode"],
        "preferred_backend": runtime_profile["preferred_backend"],
    }


def get_sync_logs(db: Session) -> list[DistributedSyncLog]:
    return list(db.scalars(select(DistributedSyncLog).order_by(DistributedSyncLog.started_at.desc())))


def create_transfer(db: Session, payload: dict):
    order = create_cross_warehouse_transfer(db, payload)
    db.flush()
    return order


def complete_transfer(db: Session, transfer_id: int):
    order = complete_cross_warehouse_transfer(db, transfer_id)
    invalidate_business_cache()
    return order
