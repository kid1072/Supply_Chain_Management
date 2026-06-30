from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WalmartStoreProfile(Base):
    __tablename__ = "walmart_store_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, unique=True)
    walmart_store_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    store_type: Mapped[str | None] = mapped_column(String(50))
    store_size: Mapped[float | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    store = relationship("Store")


class WalmartWeeklySalesFact(Base):
    __tablename__ = "walmart_weekly_sales_facts"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", "sales_date", name="uq_walmart_weekly_store_product_date"),
        UniqueConstraint("source_row_key", name="uq_walmart_weekly_source_row_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    sales_date: Mapped[date] = mapped_column(Date, nullable=False)
    weekly_sales: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    is_holiday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    temperature: Mapped[float | None] = mapped_column(Numeric(10, 2))
    fuel_price: Mapped[float | None] = mapped_column(Numeric(10, 4))
    markdown1: Mapped[float | None] = mapped_column(Numeric(14, 2))
    markdown2: Mapped[float | None] = mapped_column(Numeric(14, 2))
    markdown3: Mapped[float | None] = mapped_column(Numeric(14, 2))
    markdown4: Mapped[float | None] = mapped_column(Numeric(14, 2))
    markdown5: Mapped[float | None] = mapped_column(Numeric(14, 2))
    cpi: Mapped[float | None] = mapped_column(Numeric(12, 4))
    unemployment: Mapped[float | None] = mapped_column(Numeric(10, 4))
    raw_store_code: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_department_code: Mapped[str] = mapped_column(String(80), nullable=False)
    raw_category_code: Mapped[str | None] = mapped_column(String(80))
    raw_week_key: Mapped[str | None] = mapped_column(String(20))
    weekly_units: Mapped[float | None] = mapped_column(Numeric(14, 2))
    avg_sell_price: Mapped[float | None] = mapped_column(Numeric(14, 4))
    event_name_1: Mapped[str | None] = mapped_column(String(100))
    event_type_1: Mapped[str | None] = mapped_column(String(50))
    event_name_2: Mapped[str | None] = mapped_column(String(100))
    event_type_2: Mapped[str | None] = mapped_column(String(50))
    snap_flag: Mapped[bool | None] = mapped_column(Boolean)
    source_row_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    store = relationship("Store")
    product = relationship("Product")
