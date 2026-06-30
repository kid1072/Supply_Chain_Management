import pytest

from app.core.database import SessionLocal
from app.core.exceptions import BusinessException
from app.models.inventory import Inventory
from app.models.outbound import OutboundOrder
from app.services.inventory_service import get_or_create_inventory
from app.services.outbound_service import ship_outbound_order, sign_outbound_order


def test_outbound_stock_check():
    session = SessionLocal()
    try:
        order = session.query(OutboundOrder).filter_by(status="pending").first()
        assert order is not None
        first_item = order.items[0]
        inventory = session.query(Inventory).filter_by(product_id=first_item.product_id, warehouse_id=order.source_warehouse_id).first()
        if inventory:
            inventory.current_quantity = 0
            session.flush()
        with pytest.raises(BusinessException):
            ship_outbound_order(session, order.id)
        session.rollback()
    finally:
        session.close()


def test_outbound_success_only_increases_store_stock_after_sign():
    session = SessionLocal()
    try:
        order = session.query(OutboundOrder).filter_by(status="pending").first()
        first_item = order.items[0]
        for item in order.items:
            warehouse_inventory = session.query(Inventory).filter_by(product_id=item.product_id, warehouse_id=order.source_warehouse_id).first()
            if warehouse_inventory is None:
                warehouse_inventory = get_or_create_inventory(
                    session,
                    product_id=item.product_id,
                    location_type="warehouse",
                    warehouse_id=order.source_warehouse_id,
                    safety_stock=10,
                    max_stock=100,
                )
            warehouse_inventory.current_quantity = max(warehouse_inventory.current_quantity, item.quantity + 50)
        warehouse_inventory = session.query(Inventory).filter_by(product_id=first_item.product_id, warehouse_id=order.source_warehouse_id).first()
        store_inventory = session.query(Inventory).filter_by(product_id=first_item.product_id, store_id=order.target_store_id).first()
        before_store = store_inventory.current_quantity if store_inventory else 0
        before_warehouse = warehouse_inventory.current_quantity

        ship_outbound_order(session, order.id)
        session.refresh(warehouse_inventory)

        store_inventory = session.query(Inventory).filter_by(product_id=first_item.product_id, store_id=order.target_store_id).first()
        assert warehouse_inventory.current_quantity == before_warehouse - first_item.quantity
        assert (store_inventory.current_quantity if store_inventory else 0) == before_store

        sign_outbound_order(session, order.id)
        session.commit()

        store_inventory = session.query(Inventory).filter_by(product_id=first_item.product_id, store_id=order.target_store_id).one()
        assert store_inventory.current_quantity >= before_store + first_item.quantity
    finally:
        session.close()
