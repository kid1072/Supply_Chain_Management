from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep
from app.core.exceptions import BusinessException
from app.models.product import Product
from app.core.response import page_response, success_response
from app.models.supplier import Supplier, SupplierProduct
from app.schemas.supplier import SupplierCreate, SupplierProductRead, SupplierProductUpsert, SupplierRead, SupplierUpdate
from app.services.supplier_score_service import get_supplier_ranking, get_supplier_score, recalculate_scores
from app.utils.pagination import normalize_pagination

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("")
def list_suppliers(page: int = 1, page_size: int = 20, keyword: str | None = None, db: Session = Depends(get_db_dep)):
    page, page_size = normalize_pagination(page, page_size)
    query = select(Supplier)
    if keyword:
        query = query.where(Supplier.name.contains(keyword))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = [SupplierRead.model_validate(item).model_dump() for item in db.scalars(query.offset((page - 1) * page_size).limit(page_size))]
    return page_response(items, total, page, page_size)


@router.post("")
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db_dep)):
    item = Supplier(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return success_response(SupplierRead.model_validate(item).model_dump())


@router.post("/recalculate-scores")
def supplier_recalculate(db: Session = Depends(get_db_dep)):
    items = recalculate_scores(db)
    db.commit()
    return success_response({"count": len(items)})


@router.get("/ranking")
def supplier_ranking(db: Session = Depends(get_db_dep)):
    items = get_supplier_ranking(db)
    return success_response(
        [{"supplier_id": item.supplier_id, "score": item.score, "score_source": item.score_source} for item in items]
    )


@router.get("/{supplier_id}")
def get_supplier(supplier_id: int, db: Session = Depends(get_db_dep)):
    item = db.get(Supplier, supplier_id)
    if not item:
        raise BusinessException("supplier not found", 404)
    return success_response(SupplierRead.model_validate(item).model_dump())


@router.put("/{supplier_id}")
def update_supplier(supplier_id: int, payload: SupplierUpdate, db: Session = Depends(get_db_dep)):
    item = db.get(Supplier, supplier_id)
    if not item:
        raise BusinessException("supplier not found", 404)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return success_response(SupplierRead.model_validate(item).model_dump())


@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: int, db: Session = Depends(get_db_dep)):
    item = db.get(Supplier, supplier_id)
    if not item:
        raise BusinessException("supplier not found", 404)
    item.is_active = False
    db.commit()
    return success_response(message="deleted")


@router.get("/{supplier_id}/products")
def get_supplier_products(supplier_id: int, db: Session = Depends(get_db_dep)):
    items = list(db.scalars(select(SupplierProduct).where(SupplierProduct.supplier_id == supplier_id)))
    return success_response([SupplierProductRead.model_validate(item).model_dump() for item in items])


@router.post("/{supplier_id}/products")
def upsert_supplier_product(supplier_id: int, payload: SupplierProductUpsert, db: Session = Depends(get_db_dep)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise BusinessException("supplier not found", 404)
    product = db.get(Product, payload.product_id)
    if not product:
        raise BusinessException("product not found", 404)

    relation = db.scalar(
        select(SupplierProduct).where(
            SupplierProduct.supplier_id == supplier_id,
            SupplierProduct.product_id == payload.product_id,
        )
    )

    if relation:
        relation.supply_price = payload.supply_price
        relation.lead_time_days = payload.lead_time_days
        relation.on_time_rate = payload.on_time_rate
        relation.quality_score = payload.quality_score
        relation.is_preferred = payload.is_preferred
        db.commit()
        db.refresh(relation)
        return success_response(SupplierProductRead.model_validate(relation).model_dump(), message="updated")

    relation = SupplierProduct(supplier_id=supplier_id, **payload.model_dump())
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return success_response(SupplierProductRead.model_validate(relation).model_dump(), message="created")


@router.get("/{supplier_id}/score")
def supplier_score(supplier_id: int, db: Session = Depends(get_db_dep)):
    item = get_supplier_score(db, supplier_id)
    return success_response(item and {"supplier_id": item.supplier_id, "score": item.score, "score_source": item.score_source})
