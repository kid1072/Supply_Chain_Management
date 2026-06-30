from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.exceptions import BusinessException
from app.models.product import Product
from app.models.store import Store
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.replenishment import ReplenishmentRequestCreate
from app.services.inventory_service import get_or_create_inventory
from app.services.replenishment_service import approve_request, convert_to_outbound, create_replenishment_request


def _ensure_user(session):
    user = session.get(User, 1)
    if user:
        return user
    user = session.scalars(select(User).order_by(User.id)).first()
    assert user is not None
    return user


def _ensure_store(session):
    store = session.scalars(select(Store).order_by(Store.id)).first()
    if store:
        return store
    store = Store(
        store_code=f"STORE-{uuid4().hex[:8]}",
        name="自动测试门店",
        business_status="active",
        is_synthetic=True,
    )
    session.add(store)
    session.flush()
    return store


def _ensure_warehouses(session):
    warehouses = list(session.scalars(select(Warehouse).order_by(Warehouse.id)))
    while len(warehouses) < 2:
        warehouse = Warehouse(
            warehouse_code=f"WH-{uuid4().hex[:8]}",
            name=f"自动测试仓库{len(warehouses) + 1}",
            status="active",
            is_synthetic=True,
        )
        session.add(warehouse)
        session.flush()
        warehouses.append(warehouse)
    return warehouses[:2]


def _create_product(session):
    product = Product(
        product_code=f"PROD-{uuid4().hex[:8]}",
        name=f"自动测试商品-{uuid4().hex[:6]}",
        unit="件",
        default_safety_stock=10,
        is_active=True,
    )
    session.add(product)
    session.flush()
    return product


def _set_inventory(session, *, product_id, location_type, current_quantity, frozen_quantity=0, warehouse_id=None, store_id=None):
    inventory = get_or_create_inventory(
        session,
        product_id=product_id,
        location_type=location_type,
        warehouse_id=warehouse_id,
        store_id=store_id,
        safety_stock=10,
        max_stock=200,
    )
    inventory.current_quantity = current_quantity
    inventory.frozen_quantity = frozen_quantity
    session.flush()
    return inventory


def _create_approved_request(session, *, quantity):
    user = _ensure_user(session)
    store = _ensure_store(session)
    product = _create_product(session)
    request = create_replenishment_request(
        session,
        ReplenishmentRequestCreate(
            store_id=store.id,
            product_id=product.id,
            request_quantity=quantity,
            request_reason="自动分仓测试",
            created_by=user.id,
        ),
    )
    approve_request(session, request.id, user.id)
    session.flush()
    return request, product, store, user


def test_convert_to_outbound_auto_selects_warehouse_with_max_remaining_stock():
    session = SessionLocal()
    try:
        request, product, _store, user = _create_approved_request(session, quantity=40)
        warehouse_a, warehouse_b = _ensure_warehouses(session)
        _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_a.id,
            current_quantity=70,
            frozen_quantity=5,
        )
        _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_b.id,
            current_quantity=120,
            frozen_quantity=10,
        )

        outbounds = convert_to_outbound(session, request.id, None, user.id)

        assert len(outbounds) == 1
        assert outbounds[0].source_warehouse_id == warehouse_b.id
        assert outbounds[0].source_warehouse_id is not None
    finally:
        session.rollback()
        session.close()


def test_convert_to_outbound_rejects_specified_warehouse_with_insufficient_stock():
    session = SessionLocal()
    try:
        request, product, _store, user = _create_approved_request(session, quantity=30)
        warehouse_a, warehouse_b = _ensure_warehouses(session)
        _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_a.id,
            current_quantity=20,
            frozen_quantity=0,
        )
        _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_b.id,
            current_quantity=100,
            frozen_quantity=0,
        )

        with pytest.raises(BusinessException, match="指定仓库库存不足，无法生成出库单"):
            convert_to_outbound(session, request.id, warehouse_a.id, user.id)
    finally:
        session.rollback()
        session.close()


def test_convert_to_outbound_fails_when_all_warehouses_are_insufficient():
    session = SessionLocal()
    try:
        request, product, _store, user = _create_approved_request(session, quantity=80)
        warehouse_a, warehouse_b = _ensure_warehouses(session)
        _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_a.id,
            current_quantity=40,
            frozen_quantity=5,
        )
        _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_b.id,
            current_quantity=50,
            frozen_quantity=10,
        )

        with pytest.raises(BusinessException, match="所有仓库库存不足，无法生成出库单"):
            convert_to_outbound(session, request.id, None, user.id)
    finally:
        session.rollback()
        session.close()


def test_convert_to_outbound_api_returns_selected_source_warehouse_and_outbound_list_contains_name(api_client):
    session = SessionLocal()
    try:
        request, product, _store, user = _create_approved_request(session, quantity=35)
        warehouse_a, warehouse_b = _ensure_warehouses(session)
        _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_a.id,
            current_quantity=45,
            frozen_quantity=0,
        )
        _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_b.id,
            current_quantity=95,
            frozen_quantity=0,
        )
        request_id = request.id
        user_id = user.id
        expected_warehouse_id = warehouse_b.id
        expected_warehouse_name = warehouse_b.name
        session.commit()
    finally:
        session.close()

    response = api_client.post(
        f"/api/replenishment-requests/{request_id}/convert-to-outbound?handled_by={user_id}"
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["outbound_order_id"] is not None
    assert payload["source_warehouse_id"] == expected_warehouse_id
    assert payload["source_warehouse_name"] == expected_warehouse_name
    assert payload["outbound_order_count"] == 1

    list_response = api_client.get("/api/outbound-orders?page=1&page_size=500")
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    outbound_item = next(item for item in items if item["id"] == payload["outbound_order_id"])
    assert outbound_item["source_warehouse_id"] == expected_warehouse_id
    assert outbound_item["source_warehouse_name"] == expected_warehouse_name


def test_inventory_list_returns_warehouse_and_store_records_without_breaking_warnings(api_client):
    session = SessionLocal()
    try:
        _user = _ensure_user(session)
        store = _ensure_store(session)
        warehouse, _ = _ensure_warehouses(session)
        product = _create_product(session)
        _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse.id,
            current_quantity=88,
            frozen_quantity=8,
        )
        _set_inventory(
            session,
            product_id=product.id,
            location_type="store",
            store_id=store.id,
            current_quantity=19,
            frozen_quantity=1,
        )
        session.commit()
        product_id = product.id
        warehouse_id = warehouse.id
        store_id = store.id
    finally:
        session.close()

    response = api_client.get("/api/inventory?page=1&page_size=500")
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    matched = [item for item in items if item["product_id"] == product_id]
    warehouse_row = next(item for item in matched if item["location_type"] == "warehouse")
    store_row = next(item for item in matched if item["location_type"] == "store")
    assert warehouse_row["warehouse_id"] == warehouse_id
    assert warehouse_row["current_quantity"] == 88
    assert warehouse_row["frozen_quantity"] == 8
    assert store_row["store_id"] == store_id
    assert store_row["current_quantity"] == 19
    assert store_row["frozen_quantity"] == 1

    warning_response = api_client.get("/api/inventory/warnings")
    assert warning_response.status_code == 200
    assert warning_response.json()["success"] is True


def test_convert_to_outbound_reserves_stock_immediately_and_next_request_uses_other_warehouse():
    session = SessionLocal()
    try:
        first_request, product, _store, user = _create_approved_request(session, quantity=10)
        second_request = create_replenishment_request(
            session,
            ReplenishmentRequestCreate(
                store_id=first_request.store_id,
                product_id=product.id,
                request_quantity=10,
                request_reason="第二张申请单",
                created_by=user.id,
            ),
        )
        approve_request(session, second_request.id, user.id)
        warehouse_a, warehouse_b = _ensure_warehouses(session)
        inventory_a = _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_a.id,
            current_quantity=10,
            frozen_quantity=0,
        )
        inventory_b = _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_b.id,
            current_quantity=10,
            frozen_quantity=0,
        )

        first_outbounds = convert_to_outbound(session, first_request.id, None, user.id)
        second_outbounds = convert_to_outbound(session, second_request.id, None, user.id)

        assert len(first_outbounds) == 1
        assert len(second_outbounds) == 1
        assert first_outbounds[0].source_warehouse_id != second_outbounds[0].source_warehouse_id
        assert inventory_a.frozen_quantity + inventory_b.frozen_quantity == 20
    finally:
        session.rollback()
        session.close()


def test_convert_to_outbound_splits_request_across_multiple_warehouses():
    session = SessionLocal()
    try:
        request, product, _store, user = _create_approved_request(session, quantity=13)
        warehouse_a, warehouse_b = _ensure_warehouses(session)
        inventory_a = _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_a.id,
            current_quantity=10,
            frozen_quantity=0,
        )
        inventory_b = _set_inventory(
            session,
            product_id=product.id,
            location_type="warehouse",
            warehouse_id=warehouse_b.id,
            current_quantity=3,
            frozen_quantity=0,
        )

        outbounds = convert_to_outbound(session, request.id, None, user.id)

        assert len(outbounds) == 2
        shipped_quantities = sorted(item.items[0].quantity for item in outbounds)
        assert shipped_quantities == [3, 10]
        assert inventory_a.frozen_quantity == 10
        assert inventory_b.frozen_quantity == 3
    finally:
        session.rollback()
        session.close()
