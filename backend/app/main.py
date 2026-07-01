from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.api.routers import (
    analytics,
    categories,
    distributed,
    external_data,
    example_data,
    health,
    inbound_orders,
    inventory,
    llm,
    outbound_orders,
    products,
    purchase_orders,
    recommendations,
    replenishment_requests,
    stores,
    suppliers,
    transactions,
    users,
    warehouses,
)
from app.core.config import get_settings
from app.core.db_errors import map_integrity_error_message
from app.core.exceptions import BusinessException
from app.core.response import error_response

settings = get_settings()
app = FastAPI(title=settings.app_name)
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@app.exception_handler(BusinessException)
async def business_exception_handler(_request: Request, exc: BusinessException):
    return JSONResponse(status_code=exc.status_code, content=error_response(exc.message))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=error_response(str(exc)))


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(_request: Request, exc: IntegrityError):
    return JSONResponse(status_code=400, content=error_response(map_integrity_error_message(exc)))


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=error_response(str(exc)))


for router in [
    health.router,
    external_data.router,
    users.router,
    categories.router,
    products.router,
    suppliers.router,
    warehouses.router,
    stores.router,
    purchase_orders.router,
    inbound_orders.router,
    outbound_orders.router,
    replenishment_requests.router,
    inventory.router,
    transactions.router,
    recommendations.router,
    analytics.router,
    example_data.router,
    distributed.router,
    llm.router,
]:
    app.include_router(router)


if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")


@app.get("/demo", include_in_schema=False)
def demo_page(request: Request):
    query = request.url.query
    target = "/ui/"
    if query:
        target = f"{target}?{query}"
    return RedirectResponse(url=target)


@app.get("/")
def root():
    return {"app": settings.app_name, "docs": "/docs", "ui": "/ui/", "demo": "/demo"}
