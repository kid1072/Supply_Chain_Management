from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_db_dep
from app.core.db_errors import raise_product_integrity_error
from app.core.exceptions import BusinessException
from app.core.response import page_response, success_response
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.utils.pagination import normalize_pagination

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("")
def list_products(page: int = 1, page_size: int = 20, keyword: str | None = None, db: Session = Depends(get_db_dep)):
    page, page_size = normalize_pagination(page, page_size)
    query = select(Product)
    if keyword:
        query = query.where(Product.name.contains(keyword))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = [ProductRead.model_validate(item).model_dump() for item in db.scalars(query.offset((page - 1) * page_size).limit(page_size))]
    return page_response(items, total, page, page_size)


@router.post("")
def create_product(payload: ProductCreate, db: Session = Depends(get_db_dep)):
    try:
        item = Product(**payload.model_dump())
        db.add(item)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_product_integrity_error(exc)
    db.refresh(item)
    return success_response(ProductRead.model_validate(item).model_dump())


@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db_dep)):
    item = db.get(Product, product_id)
    if not item:
        raise BusinessException("product not found", 404)
    return success_response(ProductRead.model_validate(item).model_dump())


@router.put("/{product_id}")
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db_dep)):
    item = db.get(Product, product_id)
    if not item:
        raise BusinessException("product not found", 404)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_product_integrity_error(exc)
    db.refresh(item)
    return success_response(ProductRead.model_validate(item).model_dump())


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db_dep)):
    item = db.get(Product, product_id)
    if not item:
        raise BusinessException("product not found", 404)
    item.is_active = False
    db.commit()
    return success_response(message="deleted")
