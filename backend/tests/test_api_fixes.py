from uuid import uuid4

from app.core.database import SessionLocal
from app.models.product import Product
from app.services.analytics_service import dashboard


def test_supplier_ranking_returns_200(api_client):
    response = api_client.get("/api/suppliers/ranking")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_dashboard_top_stockout_products_excludes_overstock():
    session = SessionLocal()
    try:
        data = dashboard(session)
        assert all(item["warning_type"] in {"stockout", "critical_stockout"} for item in data["top_stockout_products"])
        assert all(item["warning_type"] == "overstock" for item in data["top_overstock_products"])
    finally:
        session.close()


def test_create_product_returns_readable_message_when_product_code_is_duplicated(api_client):
    session = SessionLocal()
    try:
        existing = Product(
            product_code=f"PROD-DUP-{uuid4().hex[:6]}",
            name="重复编码测试商品",
            unit="件",
            default_safety_stock=10,
            is_active=True,
        )
        session.add(existing)
        session.commit()
        duplicated_code = existing.product_code
    finally:
        session.close()

    response = api_client.post(
        "/api/products",
        json={
            "product_code": duplicated_code,
            "name": "另一个商品",
            "barcode": f"BAR-{uuid4().hex[:8]}",
            "unit": "件",
            "default_safety_stock": 10,
            "is_active": True,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["message"] == "商品编码已存在，请勿重复填写"
