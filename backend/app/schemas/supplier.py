from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import ORMBase


class SupplierBase(BaseModel):
    name: str
    contact_person: str | None = None
    phone: str
    email: str | None = None
    address: str | None = None
    supplier_level: str | None = None
    cooperation_status: str = "active"
    is_active: bool = True


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    supplier_level: str | None = None
    cooperation_status: str | None = None
    is_active: bool | None = None


class SupplierRead(SupplierBase, ORMBase):
    id: int
    created_at: datetime
    updated_at: datetime


class SupplierProductRead(ORMBase):
    id: int
    supplier_id: int
    product_id: int
    supply_price: Decimal
    lead_time_days: int
    on_time_rate: float
    quality_score: float
    is_preferred: bool


class SupplierProductUpsert(BaseModel):
    product_id: int
    supply_price: Decimal
    lead_time_days: int = 3
    on_time_rate: float = 0.9
    quality_score: float = 8.0
    is_preferred: bool = False
