import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal, set_sqlite_foreign_keys
from app.models.analytics import MonthlySalesFact, Promotion, SupplierScoreSnapshot
from app.models.distributed import CrossWarehouseTransferOrder, DistributedSyncLog
from app.models.inbound import InboundItem, InboundOrder
from app.models.inventory import Inventory
from app.models.outbound import OutboundItem, OutboundOrder
from app.models.product import Category, Product
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.recommendation import AIRecommendation
from app.models.replenishment import ReplenishmentRequest
from app.models.store import Store
from app.models.supplier import Supplier, SupplierProduct
from app.models.transaction import StockTransaction
from app.models.warehouse import Warehouse


if __name__ == "__main__":
    session = SessionLocal()
    try:
        set_sqlite_foreign_keys(session, enabled=False)
        try:
            for model in [
                AIRecommendation,
                MonthlySalesFact,
                Promotion,
                SupplierScoreSnapshot,
                DistributedSyncLog,
                CrossWarehouseTransferOrder,
                StockTransaction,
                ReplenishmentRequest,
                OutboundItem,
                OutboundOrder,
                InboundItem,
                InboundOrder,
                PurchaseOrderItem,
                PurchaseOrder,
                Inventory,
                SupplierProduct,
                Product,
                Category,
                Supplier,
                Store,
                Warehouse,
            ]:
                session.query(model).delete()
        finally:
            set_sqlite_foreign_keys(session, enabled=True)
        session.commit()
    finally:
        session.close()
