from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep
from app.core.response import success_response
from app.models.recommendation import AIRecommendation
from app.schemas.recommendation import RecommendationRead
from app.services.recommendation_service import generate_recommendations, set_recommendation_status

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.post("/generate")
def generate(store_id: int | None = None, enhance_with_llm: bool = True, db: Session = Depends(get_db_dep)):
    items = generate_recommendations(db, store_id, enhance_with_llm=enhance_with_llm)
    db.commit()
    return success_response({"count": len(items)})


@router.get("")
def list_all(db: Session = Depends(get_db_dep)):
    items = list(db.scalars(select(AIRecommendation)))
    return success_response([RecommendationRead.model_validate(item).model_dump() for item in items])


@router.get("/store/{store_id}")
def by_store(store_id: int, db: Session = Depends(get_db_dep)):
    items = list(db.scalars(select(AIRecommendation).where(AIRecommendation.store_id == store_id)))
    return success_response([RecommendationRead.model_validate(item).model_dump() for item in items])


@router.post("/{recommendation_id}/accept")
def accept(recommendation_id: int, db: Session = Depends(get_db_dep)):
    item = set_recommendation_status(db, recommendation_id, "accepted")
    db.commit()
    return success_response(RecommendationRead.model_validate(item).model_dump())


@router.post("/{recommendation_id}/reject")
def reject(recommendation_id: int, db: Session = Depends(get_db_dep)):
    item = set_recommendation_status(db, recommendation_id, "rejected")
    db.commit()
    return success_response(RecommendationRead.model_validate(item).model_dump())
