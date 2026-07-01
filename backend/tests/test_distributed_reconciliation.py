from app.core.database import SessionLocal
from app.models.distributed import DistributedSyncLog
from app.models.inventory import Inventory
from app.services.distributed_service import run_reconciliation
from app.services.inventory_service import complete_cross_warehouse_transfer, create_cross_warehouse_transfer


def test_reconciliation_and_transfer():
    session = SessionLocal()
    try:
        result = run_reconciliation(session)
        session.commit()
        assert "mismatch_records" in result
        assert result["preferred_backend"] in {"oceanbase", "sqlite"}
        assert result["backend_mode"] in {"oceanbase-primary", "sqlite-fallback", "sqlite-primary"}
        assert session.query(DistributedSyncLog).count() > 0
        log = session.query(DistributedSyncLog).order_by(DistributedSyncLog.id.desc()).first()
        assert log is not None
        assert log.node_type in {"sqlite", "mysql"}
        inventory_count = session.query(Inventory).count()
        assert len(result["mismatch_records"]) < inventory_count

        source = session.query(Inventory).filter_by(location_type="warehouse").first()
        target = session.query(Inventory).filter(Inventory.location_type == "warehouse", Inventory.warehouse_id != source.warehouse_id).first()
        source.current_quantity = max(source.current_quantity, 50)
        session.flush()
        transfer = create_cross_warehouse_transfer(
            session,
            {
                "source_warehouse_id": source.warehouse_id,
                "target_warehouse_id": target.warehouse_id,
                "product_id": source.product_id,
                "quantity": 10,
                "reason": "test",
                "created_by": None,
            },
        )
        before_source = source.current_quantity
        before_target = target.current_quantity
        complete_cross_warehouse_transfer(session, transfer.id)
        session.commit()
        session.refresh(source)
        session.refresh(target)
        assert source.current_quantity == before_source - 10
        assert target.current_quantity >= before_target
    finally:
        session.close()
