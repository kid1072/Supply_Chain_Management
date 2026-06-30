from __future__ import annotations

import math
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.cache import invalidate_business_cache
from app.models.analytics import MonthlySalesFact, Promotion, SupplierScoreSnapshot
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.recommendation import AIRecommendation
from app.models.replenishment import ReplenishmentRequest
from app.models.store import Store
from app.models.supplier import SupplierProduct
from app.services.llm.llm_router import get_llm_client
from app.services.llm.prompt_templates import recommendation_prompt
from app.utils.datetime_utils import now_local


def choose_supplier(db: Session, product_id: int) -> SupplierProduct | None:
    score_subquery = (
        select(SupplierScoreSnapshot.supplier_id, SupplierScoreSnapshot.score)
        .order_by(SupplierScoreSnapshot.generated_at.desc())
        .subquery()
    )
    rows = db.execute(
        select(SupplierProduct, score_subquery.c.score)
        .outerjoin(score_subquery, score_subquery.c.supplier_id == SupplierProduct.supplier_id)
        .where(SupplierProduct.product_id == product_id)
        .order_by(desc(score_subquery.c.score), SupplierProduct.lead_time_days.asc(), SupplierProduct.supply_price.asc())
    ).all()
    return rows[0][0] if rows else None


def build_rule_reason(
    store_code: str,
    product_name: str,
    current_stock: int,
    safety_stock: int,
    recent_30_sales: float,
    avg_daily_sales: float,
    days_until_stockout: float,
    recommended_quantity: int,
    supplier_name: str | None,
    lead_time_days: int,
) -> str:
    return (
        f"门店 {store_code} 的商品 {product_name} 当前库存为 {current_stock}，"
        f"{'低于' if current_stock <= safety_stock else '高于'}安全库存 {safety_stock}；"
        f"最近30天销量为 {recent_30_sales:.0f}，平均日销量约 {avg_daily_sales:.2f}，"
        f"预计 {days_until_stockout:.2f} 天后可能缺货；建议补货 {recommended_quantity} 件，"
        f"优先选择供应商 {supplier_name or '待分配'}，预计供货周期 {lead_time_days} 天。"
    )


def maybe_enhance_reason(rule_reason: str) -> tuple[str | None, str, bool]:
    client = get_llm_client()
    if not client:
        return None, "rule", False
    try:
        return client.generate_text(recommendation_prompt(rule_reason)), client.__class__.__name__.replace("Client", "").lower(), True
    except Exception:
        return None, "rule", False


def generate_recommendations(
    db: Session,
    store_id: int | None = None,
    enhance_with_llm: bool = True,
) -> list[AIRecommendation]:
    if store_id:
        db.query(AIRecommendation).filter(AIRecommendation.store_id == store_id).delete()
    else:
        db.query(AIRecommendation).delete()
    store_query = select(Store)
    if store_id:
        store_query = store_query.where(Store.id == store_id)
    stores = list(db.scalars(store_query))
    recommendations: list[AIRecommendation] = []
    latest_month_rows = db.execute(
        select(MonthlySalesFact.year, MonthlySalesFact.month).order_by(MonthlySalesFact.year.desc(), MonthlySalesFact.month.desc()).limit(1)
    ).first()
    latest_year, latest_month = latest_month_rows if latest_month_rows else (now_local().year, now_local().month)
    for store in stores:
        inventory_rows = list(db.scalars(select(Inventory).where(Inventory.store_id == store.id, Inventory.location_type == "store")))
        for inventory in inventory_rows:
            sales = db.scalar(
                select(func.coalesce(func.sum(MonthlySalesFact.retail_sales), 0)).where(
                    MonthlySalesFact.store_id == store.id,
                    MonthlySalesFact.product_id == inventory.product_id,
                    MonthlySalesFact.year == latest_year,
                    MonthlySalesFact.month == latest_month,
                )
            ) or 0
            recent_30_sales = float(sales)
            recent_7_sales = recent_30_sales / 4
            avg_daily_sales = recent_30_sales / 30
            supplier_link = choose_supplier(db, inventory.product_id)
            lead_time_days = supplier_link.lead_time_days if supplier_link else 3
            review_period_days = 7
            buffer_days = 3
            target_days = lead_time_days + review_period_days + buffer_days
            target_stock = math.ceil(avg_daily_sales * target_days + inventory.safety_stock)
            recommended_quantity = max(0, target_stock - inventory.current_quantity)
            promo = db.scalar(
                select(Promotion).where(
                    Promotion.store_id == store.id,
                    Promotion.product_id == inventory.product_id,
                )
            )
            if promo:
                recommended_quantity = math.ceil(recommended_quantity * 1.2)
            days_until_stockout = inventory.current_quantity / max(avg_daily_sales, 0.01)
            if days_until_stockout <= lead_time_days:
                risk_level = "high"
            elif days_until_stockout <= lead_time_days + 3:
                risk_level = "medium"
            else:
                risk_level = "low"
            shortage_risk = risk_level in {"medium", "high"}
            product = db.get(Product, inventory.product_id)
            supplier_name = supplier_link.supplier.name if supplier_link else None
            rule_reason = build_rule_reason(
                store.store_code,
                product.name if product else str(inventory.product_id),
                inventory.current_quantity,
                inventory.safety_stock,
                recent_30_sales,
                avg_daily_sales,
                days_until_stockout,
                recommended_quantity,
                supplier_name,
                lead_time_days,
            )
            recommendation = AIRecommendation(
                store_id=store.id,
                product_id=inventory.product_id,
                current_stock=inventory.current_quantity,
                recent_7_sales=recent_7_sales,
                recent_30_sales=recent_30_sales,
                avg_daily_sales=avg_daily_sales,
                safety_stock=inventory.safety_stock,
                recommended_quantity=recommended_quantity,
                recommended_supplier_id=supplier_link.supplier_id if supplier_link else None,
                shortage_risk=shortage_risk,
                risk_level=risk_level,
                days_until_stockout=days_until_stockout,
                reason=rule_reason,
                reason_enhanced=None,
                llm_provider="rule",
                llm_used=False,
                generated_at=now_local(),
                adoption_status="pending",
            )
            db.add(recommendation)
            recommendations.append(recommendation)
    if enhance_with_llm:
        high_risk_recommendations = [item for item in recommendations if item.risk_level == "high"]
        for recommendation in high_risk_recommendations:
            reason_enhanced, llm_provider, llm_used = maybe_enhance_reason(recommendation.reason)
            recommendation.reason_enhanced = reason_enhanced
            recommendation.llm_provider = llm_provider
            recommendation.llm_used = llm_used
    invalidate_business_cache()
    db.flush()
    return recommendations


def set_recommendation_status(db: Session, recommendation_id: int, status: str) -> AIRecommendation:
    recommendation = db.get(AIRecommendation, recommendation_id)
    if not recommendation:
        raise ValueError("recommendation not found")
    recommendation.adoption_status = status
    db.flush()
    return recommendation
