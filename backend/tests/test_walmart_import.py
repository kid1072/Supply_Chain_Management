import csv

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.analytics import MonthlySalesFact
from app.models.product import Category, Product
from app.models.store import Store
from app.models.transaction import StockTransaction
from app.models.walmart import WalmartStoreProfile, WalmartWeeklySalesFact
from app.services.walmart_import_service import clear_walmart_fact_data, import_walmart_data


def _write_standard_walmart_dataset(base_path):
    train_path = base_path / "train.csv"
    features_path = base_path / "features.csv"
    stores_path = base_path / "stores.csv"

    with train_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Store", "Dept", "Date", "Weekly_Sales", "IsHoliday"])
        writer.writerow([1, 5, "2012-01-06", "100.50", "FALSE"])
        writer.writerow([1, 5, "2012-01-13", "-20.00", "TRUE"])
        writer.writerow([2, 7, "2012-01-06", "200.00", "FALSE"])

    with features_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Store", "Date", "Temperature", "Fuel_Price", "CPI", "Unemployment", "IsHoliday"])
        writer.writerow([1, "2012-01-06", "60.5", "3.55", "210.1", "8.0", "FALSE"])
        writer.writerow([1, "2012-01-13", "55.0", "3.45", "211.2", "8.1", "TRUE"])
        writer.writerow([2, "2012-01-06", "65.0", "3.65", "212.0", "7.9", "FALSE"])

    with stores_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Store", "Type", "Size"])
        writer.writerow([1, "A", "100"])
        writer.writerow([2, "B", "200"])

    return base_path


def test_walmart_import_standard_dataset_is_idempotent_and_keeps_example_data(tmp_path):
    dataset_path = _write_standard_walmart_dataset(tmp_path)
    session = SessionLocal()
    try:
        example_monthly_count = session.scalar(
            select(func.count(MonthlySalesFact.id)).where(MonthlySalesFact.is_example_data.is_(True))
        )
        stock_transaction_count = session.scalar(select(func.count(StockTransaction.id)))

        clear_walmart_fact_data(session)
        session.commit()

        first_summary = import_walmart_data(session, dataset_path, dry_run=False, replace_walmart=True)
        session.commit()

        assert first_summary.raw_weekly_sales_count == 3
        assert first_summary.imported_row_count == 3
        assert first_summary.unparsed_row_count == 0
        assert first_summary.feature_missing_count == 0
        assert first_summary.monthly_sales_fact_count == 2

        walmart_store = session.execute(select(Store).where(Store.store_code == "WM-STORE-001")).scalar_one()
        assert walmart_store.name == "Walmart Store 001"
        assert walmart_store.is_synthetic is False
        assert walmart_store.business_status == "active"

        walmart_profile = session.execute(
            select(WalmartStoreProfile).where(WalmartStoreProfile.walmart_store_no == "1")
        ).scalar_one()
        assert walmart_profile.store_id == walmart_store.id
        assert str(walmart_profile.store_size) == "100.00"
        assert walmart_profile.store_type == "A"

        parent_category = session.execute(
            select(Category).where(Category.name == "Walmart Department", Category.parent_id.is_(None))
        ).scalar_one()
        child_category = session.execute(
            select(Category).where(Category.name == "Walmart Dept 005", Category.parent_id == parent_category.id)
        ).scalar_one()
        dept_product = session.execute(
            select(Product).where(Product.product_code == "WM-DEPT-005")
        ).scalar_one()
        assert dept_product.name == "Walmart Department 005"
        assert dept_product.unit == "sales_amount"
        assert dept_product.category_id == child_category.id

        weekly_rows = session.execute(
            select(WalmartWeeklySalesFact).order_by(WalmartWeeklySalesFact.sales_date, WalmartWeeklySalesFact.raw_department_code)
        ).scalars().all()
        assert len(weekly_rows) == 3
        assert float(weekly_rows[0].weekly_sales) == 100.50
        assert float(weekly_rows[1].weekly_sales) == 200.00
        assert float(weekly_rows[2].weekly_sales) == -20.00

        monthly_rows = session.execute(
            select(MonthlySalesFact)
            .join(Product, Product.id == MonthlySalesFact.product_id)
            .where(
                MonthlySalesFact.is_example_data.is_(False),
                Product.product_code.in_(["WM-DEPT-005", "WM-DEPT-007"]),
            )
            .order_by(MonthlySalesFact.store_id, MonthlySalesFact.product_id)
        ).scalars().all()
        assert len(monthly_rows) == 2
        assert monthly_rows[0].promo_flag is True
        assert monthly_rows[1].promo_flag is False
        assert round(monthly_rows[0].retail_sales, 2) == 80.50
        assert round(monthly_rows[1].retail_sales, 2) == 200.00
        assert all(item.retail_transfers == 0 for item in monthly_rows)
        assert all(item.warehouse_sales == 0 for item in monthly_rows)

        second_summary = import_walmart_data(session, dataset_path, dry_run=False, replace_walmart=False)
        session.commit()
        assert second_summary.imported_row_count == 0
        assert second_summary.skipped_row_count >= 3
        assert session.scalar(select(func.count(WalmartWeeklySalesFact.id))) == 3
        assert len(monthly_rows) == session.scalar(
            select(func.count(MonthlySalesFact.id)).where(MonthlySalesFact.is_example_data.is_(False))
        )

        third_summary = import_walmart_data(session, dataset_path, dry_run=False, replace_walmart=True)
        session.commit()
        assert third_summary.imported_row_count == 3
        assert session.scalar(
            select(func.count(MonthlySalesFact.id)).where(MonthlySalesFact.is_example_data.is_(True))
        ) == example_monthly_count
        assert session.scalar(select(func.count(StockTransaction.id))) == stock_transaction_count
    finally:
        clear_walmart_fact_data(session)
        session.commit()
        session.close()


def test_walmart_status_endpoint_returns_counts(api_client, tmp_path):
    dataset_path = _write_standard_walmart_dataset(tmp_path)
    session = SessionLocal()
    try:
        clear_walmart_fact_data(session)
        session.commit()
        import_walmart_data(session, dataset_path, dry_run=False, replace_walmart=True)
        session.commit()
    finally:
        session.close()

    try:
        response = api_client.get("/api/external-data/walmart/status")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "ok"
        assert body["data"]["raw_weekly_sales_count"] == 3
        assert body["data"]["monthly_sales_fact_count"] == 2
        assert body["data"]["store_count"] >= 2
        assert body["data"]["department_product_count"] >= 2
        assert body["data"]["min_sales_date"] == "2012-01-06"
        assert body["data"]["max_sales_date"] == "2012-01-13"
        assert "mode" in body["data"]["database_runtime"]
        assert "active_dialect" in body["data"]["database_runtime"]
    finally:
        cleanup_session = SessionLocal()
        try:
            clear_walmart_fact_data(cleanup_session)
            cleanup_session.commit()
        finally:
            cleanup_session.close()
