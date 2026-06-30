from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep
from app.core.response import page_response, success_response
from app.models.product import Product
from app.models.transaction import StockTransaction
from app.utils.pagination import normalize_pagination

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("")
def list_transactions(page: int = 1, page_size: int = 20, keyword: str | None = None, db: Session = Depends(get_db_dep)):
    page, page_size = normalize_pagination(page, page_size)
    query = select(StockTransaction).order_by(desc(StockTransaction.transaction_time), desc(StockTransaction.id))
    if keyword:
        query = query.where(StockTransaction.transaction_no.contains(keyword))
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = [item.__dict__ | {"_sa_instance_state": None} for item in db.scalars(query.offset((page - 1) * page_size).limit(page_size))]
    cleaned = [{k: v for k, v in item.items() if k != "_sa_instance_state"} for item in items]
    return page_response(cleaned, total, page, page_size)


@router.get("/product/{product_id}")
def by_product(product_id: int, db: Session = Depends(get_db_dep)):
    items = list(db.scalars(select(StockTransaction).where(StockTransaction.product_id == product_id)))
    return success_response([{"transaction_no": item.transaction_no, "transaction_type": item.transaction_type, "change_quantity": item.change_quantity} for item in items])


@router.get("/doc/{doc_type}/{doc_id}")
def by_doc(doc_type: str, doc_id: int, db: Session = Depends(get_db_dep)):
    items = list(db.scalars(select(StockTransaction).where(StockTransaction.related_doc_type == doc_type, StockTransaction.related_doc_id == doc_id)))
    return success_response([{"transaction_no": item.transaction_no, "transaction_type": item.transaction_type, "change_quantity": item.change_quantity} for item in items])


@router.get("/product/{product_id}/trace")
def trace(product_id: int, db: Session = Depends(get_db_dep)):
    product = db.get(Product, product_id)
    transactions = list(db.scalars(select(StockTransaction).where(StockTransaction.product_id == product_id).order_by(StockTransaction.transaction_time)))
    data = [
        {
            "source": "example_data",
            "product": product.name if product else product_id,
            "transaction_no": item.transaction_no,
            "path": f"{item.source_location_type or 'example seed'} -> {item.target_location_type or 'n/a'}",
            "related_doc_type": item.related_doc_type,
        }
        for item in transactions
    ]
    return success_response(data)
