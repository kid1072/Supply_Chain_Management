from __future__ import annotations

import calendar
import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from random import Random
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import set_sqlite_foreign_keys
from app.models import Base
from app.utils.datetime_utils import now_local
from app.utils.hash_utils import hash_password


RNG = Random(20260510)


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _month_start(base_date: date, months_ago: int = 0) -> date:
    year = base_date.year
    month = base_date.month - months_ago
    while month <= 0:
        year -= 1
        month += 12
    return date(year, month, 1)


def _safe_date(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def generate_example_data() -> dict[str, int]:
    settings = get_settings()
    example_dir = settings.example_dir_path
    if example_dir.exists():
        shutil.rmtree(example_dir)
    example_dir.mkdir(parents=True, exist_ok=True)

    categories = [
        {"name": "饮料", "parent_name": None},
        {"name": "矿泉水", "parent_name": "饮料"},
        {"name": "茶饮料", "parent_name": "饮料"},
        {"name": "碳酸饮料", "parent_name": "饮料"},
        {"name": "零食", "parent_name": None},
        {"name": "日用品", "parent_name": None},
        {"name": "文具", "parent_name": None},
        {"name": "药品", "parent_name": None},
        {"name": "冷藏食品", "parent_name": None},
        {"name": "粮油调味", "parent_name": None},
        {"name": "个人护理", "parent_name": None},
    ]
    product_templates = [
        ("矿泉水 550ml", "矿泉水"),
        ("苏打水 500ml", "矿泉水"),
        ("绿茶 500ml", "茶饮料"),
        ("可乐 330ml", "碳酸饮料"),
        ("橙汁 1L", "饮料"),
        ("乌龙茶 500ml", "茶饮料"),
        ("咖啡饮料 280ml", "饮料"),
        ("能量饮料 250ml", "饮料"),
        ("薯片 原味", "零食"),
        ("薯片 番茄味", "零食"),
        ("饼干 奶香味", "零食"),
        ("方便面 红烧牛肉味", "零食"),
        ("方便面 老坛酸菜味", "零食"),
        ("巧克力棒", "零食"),
        ("坚果混合装", "零食"),
        ("海苔卷", "零食"),
        ("洗手液", "日用品"),
        ("抽纸", "日用品"),
        ("垃圾袋", "日用品"),
        ("洗洁精", "日用品"),
        ("中性笔 黑色", "文具"),
        ("中性笔 蓝色", "文具"),
        ("A4 复印纸", "文具"),
        ("笔记本 B5", "文具"),
        ("修正带", "文具"),
        ("创可贴", "药品"),
        ("感冒药", "药品"),
        ("退烧贴", "药品"),
        ("碘伏棉签", "药品"),
        ("牛奶 250ml", "冷藏食品"),
        ("酸奶 200g", "冷藏食品"),
        ("鸡蛋", "冷藏食品"),
        ("火腿肠", "冷藏食品"),
        ("食用油", "粮油调味"),
        ("酱油", "粮油调味"),
        ("醋", "粮油调味"),
        ("大米 5kg", "粮油调味"),
        ("面条 1kg", "粮油调味"),
        ("洗发水", "个人护理"),
        ("牙膏", "个人护理"),
        ("牙刷", "个人护理"),
        ("沐浴露", "个人护理"),
        ("护手霜", "个人护理"),
    ]
    while len(product_templates) < 60:
        idx = len(product_templates) + 1
        category = ["饮料", "零食", "日用品", "文具", "药品", "冷藏食品", "粮油调味", "个人护理"][idx % 8]
        product_templates.append((f"示例商品{idx:02d}", category))
    products = []
    for idx, (name, category_name) in enumerate(product_templates, start=1):
        products.append(
            {
                "product_code": f"P{idx:04d}",
                "name": name,
                "barcode": f"6900000{idx:06d}",
                "category_name": category_name,
                "spec": "标准装",
                "unit": "piece",
                "shelf_life_days": 365 if category_name not in {"冷藏食品", "药品"} else 90,
                "default_safety_stock": 10 + idx % 20,
                "is_active": True,
            }
        )
    suppliers = [
        {
            "name": f"供应商S{i:02d}",
            "contact_person": f"联系人{i:02d}",
            "phone": f"1380000{i:04d}",
            "email": f"supplier{i:02d}@example.com",
            "address": f"示例供应商地址{i:02d}",
            "supplier_level": ["A", "B", "C"][i % 3],
            "cooperation_status": "active",
            "is_active": True,
        }
        for i in range(1, 13)
    ]
    supplier_products = []
    for idx, product in enumerate(products, start=1):
        for offset in range(1, 1 + (2 if idx % 5 == 0 else 1) + (1 if idx % 9 == 0 else 0)):
            supplier_index = ((idx + offset) % len(suppliers)) + 1
            supplier_products.append(
                {
                    "supplier_name": f"供应商S{supplier_index:02d}",
                    "product_code": product["product_code"],
                    "supply_price": round(3 + idx * 0.7 + offset * 0.5, 2),
                    "lead_time_days": 1 + (idx + offset) % 5,
                    "on_time_rate": round(0.85 + ((idx + offset) % 10) * 0.01, 2),
                    "quality_score": round(7.5 + ((idx + offset) % 5) * 0.4, 2),
                    "is_preferred": offset == 1,
                }
            )
    warehouses = [
        {"warehouse_code": "WH-CENTRAL", "name": "中心仓", "address": "中心区一号路", "manager_name": "张仓", "phone": "021-1000001", "max_capacity": 30000, "status": "active", "region": "中心区", "is_synthetic": False},
        {"warehouse_code": "WH-EAST", "name": "东区仓", "address": "东区二号路", "manager_name": "李东", "phone": "021-1000002", "max_capacity": 20000, "status": "active", "region": "东区", "is_synthetic": False},
        {"warehouse_code": "WH-WEST", "name": "西区仓", "address": "西区三号路", "manager_name": "王西", "phone": "021-1000003", "max_capacity": 18000, "status": "active", "region": "西区", "is_synthetic": False},
        {"warehouse_code": "WH-COLD", "name": "冷链仓", "address": "北区冷链路", "manager_name": "赵冷", "phone": "021-1000004", "max_capacity": 15000, "status": "active", "region": "北区", "is_synthetic": False},
    ]
    stores = []
    regions = ["东区", "西区", "南区", "北区", "中心区"]
    for idx, code in enumerate(["STORE-A", "STORE-B", "STORE-C", "STORE-D", "STORE-E", "STORE-F", "STORE-G", "STORE-H"], start=1):
        stores.append(
            {
                "store_code": code,
                "name": f"{code} 门店",
                "region": regions[(idx - 1) % len(regions)],
                "address": f"{regions[(idx - 1) % len(regions)]} 商业街 {idx} 号",
                "longitude": 121.4 + idx * 0.01,
                "latitude": 31.2 + idx * 0.01,
                "contact_person": f"店长{idx}",
                "phone": f"1391000{idx:04d}",
                "business_status": "active",
                "is_synthetic": False,
            }
        )
    users = [
        {"username": "admin", "password": "admin123", "real_name": "系统管理员", "role": "admin", "location_type": None, "warehouse_code": None, "store_code": None, "phone": "13000000001", "is_active": True},
        {"username": "buyer", "password": "buyer123", "real_name": "采购专员", "role": "buyer", "location_type": None, "warehouse_code": None, "store_code": None, "phone": "13000000002", "is_active": True},
        {"username": "warehouse", "password": "warehouse123", "real_name": "仓库主管", "role": "warehouse_manager", "location_type": "warehouse", "warehouse_code": "WH-CENTRAL", "store_code": None, "phone": "13000000003", "is_active": True},
        {"username": "store", "password": "store123", "real_name": "门店员工", "role": "store_staff", "location_type": "store", "warehouse_code": None, "store_code": "STORE-A", "phone": "13000000004", "is_active": True},
        {"username": "manager", "password": "manager123", "real_name": "运营经理", "role": "manager", "location_type": None, "warehouse_code": None, "store_code": None, "phone": "13000000005", "is_active": True},
    ]
    users = [
        {"username": "admin", "employee_no": "A1001", "password": "admin123", "verification_code": "246810", "real_name": "系统管理员", "role": "admin", "location_type": None, "warehouse_code": None, "store_code": None, "phone": "13000000001", "is_active": True, "is_verified": True},
        {"username": "buyer", "employee_no": "P1001", "password": "buyer123", "verification_code": "135790", "real_name": "采购专员", "role": "buyer", "location_type": None, "warehouse_code": None, "store_code": None, "phone": "13000000002", "is_active": True, "is_verified": True},
        {"username": "warehouse", "employee_no": "W1001", "password": "warehouse123", "verification_code": "975310", "real_name": "仓库主管", "role": "warehouse_manager", "location_type": "warehouse", "warehouse_code": "WH-CENTRAL", "store_code": None, "phone": "13000000003", "is_active": True, "is_verified": True},
        {"username": "store", "employee_no": "S1001", "password": "store123", "verification_code": "864200", "real_name": "门店员工", "role": "store_staff", "location_type": "store", "warehouse_code": None, "store_code": "STORE-A", "phone": "13000000004", "is_active": True, "is_verified": True},
        {"username": "manager", "employee_no": "M1001", "password": "manager123", "verification_code": "112233", "real_name": "运营经理", "role": "manager", "location_type": None, "warehouse_code": None, "store_code": None, "phone": "13000000005", "is_active": True, "is_verified": True},
        {"username": "store_pending_a", "employee_no": "S2001", "password": "pending123", "verification_code": "246810", "real_name": "王敏", "role": "store_staff", "location_type": "store", "warehouse_code": None, "store_code": "STORE-A", "phone": "13000002001", "is_active": True, "is_verified": False},
        {"username": "warehouse_pending_e", "employee_no": "W2001", "password": "pending123", "verification_code": "135790", "real_name": "李峰", "role": "warehouse_manager", "location_type": "warehouse", "warehouse_code": "WH-EAST", "store_code": None, "phone": "13000002002", "is_active": True, "is_verified": False},
    ]
    inventory_seed = []
    warehouse_codes = [item["warehouse_code"] for item in warehouses]
    for idx, product in enumerate(products, start=1):
        warehouse_code = warehouse_codes[idx % len(warehouse_codes)]
        inventory_seed.append(
            {
                "product_code": product["product_code"],
                "location_type": "warehouse",
                "warehouse_code": warehouse_code,
                "store_code": None,
                "current_quantity": 20 if idx % 11 == 0 else 500 + (idx % 7) * 80,
                "frozen_quantity": 0,
                "safety_stock": product["default_safety_stock"],
                "max_stock": product["default_safety_stock"] * (6 if idx % 13 == 0 else 12),
            }
        )
        if idx % 3 == 0:
            inventory_seed.append(
                {
                    "product_code": product["product_code"],
                    "location_type": "warehouse",
                    "warehouse_code": warehouse_codes[(idx + 1) % len(warehouse_codes)],
                    "store_code": None,
                    "current_quantity": 1200 if idx % 10 == 0 else 180,
                    "frozen_quantity": 0,
                    "safety_stock": product["default_safety_stock"],
                    "max_stock": product["default_safety_stock"] * 10,
                }
            )
    for store in stores:
        for idx, product in enumerate(products[:25], start=1):
            inventory_seed.append(
                {
                    "product_code": product["product_code"],
                    "location_type": "store",
                    "warehouse_code": None,
                    "store_code": store["store_code"],
                    "current_quantity": 5 if idx % 8 == 0 else 40 + (idx % 6) * 5,
                    "frozen_quantity": 0,
                    "safety_stock": product["default_safety_stock"],
                    "max_stock": product["default_safety_stock"] * 5,
                }
            )
    monthly_sales_facts = []
    today = date.today()
    month_anchor = today.replace(day=1)
    for month_offset in range(12):
        current_month = _month_start(month_anchor, month_offset)
        for row_idx in range(220):
            product = products[row_idx % len(products)]
            store = stores[row_idx % len(stores)]
            warehouse = warehouses[row_idx % len(warehouses)]
            trend_base = 30 + (row_idx % 15) * 5
            trend = trend_base + (11 - month_offset) * (3 if row_idx % 7 == 0 else -1 if row_idx % 9 == 0 else 1)
            monthly_sales_facts.append(
                {
                    "year": current_month.year,
                    "month": current_month.month,
                    "supplier_name": supplier_products[row_idx % len(supplier_products)]["supplier_name"],
                    "product_code": product["product_code"],
                    "category_name": product["category_name"],
                    "retail_sales": max(5, trend),
                    "retail_transfers": max(1, trend // 5),
                    "warehouse_sales": max(8, trend // 2),
                    "store_code": store["store_code"],
                    "warehouse_code": warehouse["warehouse_code"],
                    "promo_flag": row_idx % 17 == 0,
                }
            )
    purchase_orders = []
    for idx in range(1, 31):
        items = []
        for j in range(3):
            product = products[(idx * 3 + j) % len(products)]
            items.append({"product_code": product["product_code"], "purchase_quantity": 100 + idx * 5 + j * 10, "purchase_price": round(5 + idx * 0.4 + j, 2)})
        purchase_orders.append(
            {
                "order_no": f"POEX{idx:04d}",
                "supplier_name": suppliers[idx % len(suppliers)]["name"],
                "created_by_username": "buyer",
                "created_at": str(today - timedelta(days=idx * 3)),
                "expected_arrival_date": str(today + timedelta(days=idx % 7)),
                "status": ["pending", "confirmed", "partially_arrived", "completed", "cancelled"][idx % 5],
                "remark": f"示例采购单 {idx}",
                "items": items,
            }
        )
    inbound_orders = []
    for idx in range(1, 26):
        po = purchase_orders[idx - 1]
        inbound_orders.append(
            {
                "inbound_no": f"INEX{idx:04d}",
                "purchase_order_no": po["order_no"],
                "supplier_name": po["supplier_name"],
                "warehouse_code": warehouses[idx % len(warehouses)]["warehouse_code"],
                "inbound_time": f"{today - timedelta(days=idx)}T10:00:00",
                "handled_by_username": "warehouse",
                "status": "completed" if idx % 4 else "pending",
                "remark": f"示例入库单 {idx}",
                "items": [
                    {
                        "product_code": item["product_code"],
                        "quantity": int(item["purchase_quantity"] * (0.6 if idx % 3 == 0 else 1)),
                        "batch_no": f"BATCH{idx:04d}",
                        "production_date": str(today - timedelta(days=30 + idx)),
                        "expiry_date": str(today + timedelta(days=180)),
                    }
                    for item in po["items"]
                ],
            }
        )
    outbound_orders = []
    for idx in range(1, 31):
        outbound_orders.append(
            {
                "outbound_no": f"OUTEX{idx:04d}",
                "source_warehouse_code": warehouses[idx % len(warehouses)]["warehouse_code"],
                "target_store_code": stores[idx % len(stores)]["store_code"],
                "outbound_time": f"{today - timedelta(days=idx)}T15:00:00",
                "handled_by_username": "warehouse",
                "status": ["pending", "shipped", "signed"][idx % 3],
                "source_request_no": None,
                "remark": f"示例出库单 {idx}",
                "items": [
                    {"product_code": products[(idx + j) % len(products)]["product_code"], "quantity": 10 + j * 3 + idx % 5, "batch_no": f"OB{idx:04d}"}
                    for j in range(2)
                ],
            }
        )
    replenishment_requests = []
    for idx in range(1, 41):
        replenishment_requests.append(
            {
                "request_no": f"REQEX{idx:04d}",
                "store_code": stores[idx % len(stores)]["store_code"],
                "product_code": products[idx % len(products)]["product_code"],
                "request_quantity": 20 + idx,
                "request_reason": f"门店补货需求 {idx}",
                "request_time": f"{today - timedelta(days=idx)}T09:00:00",
                "audit_status": ["pending", "approved", "rejected", "converted"][idx % 4],
                "audited_by_username": "manager",
                "audit_time": f"{today - timedelta(days=max(1, idx - 1))}T18:00:00",
                "created_by_username": "store",
                "generated_outbound_order_no": outbound_orders[idx % len(outbound_orders)]["outbound_no"] if idx % 4 == 3 else None,
            }
        )
    stock_transactions = []
    for idx in range(1, 51):
        stock_transactions.append(
            {
                "transaction_no": f"TXEX{idx:05d}",
                "product_code": products[idx % len(products)]["product_code"],
                "transaction_type": "example_seed",
                "source_location_type": None,
                "source_warehouse_code": None,
                "source_store_code": None,
                "target_location_type": "warehouse",
                "target_warehouse_code": warehouses[idx % len(warehouses)]["warehouse_code"],
                "target_store_code": None,
                "change_quantity": 100 + idx,
                "before_quantity": 0,
                "after_quantity": 100 + idx,
                "transaction_time": f"{today - timedelta(days=idx)}T08:00:00",
                "operated_by_username": "admin",
                "related_doc_type": "example_seed",
                "related_doc_no": f"SEED{idx:04d}",
                "remark": "示例流水",
            }
        )
    ai_recommendations = []
    for idx in range(1, 21):
        ai_recommendations.append(
            {
                "store_code": stores[idx % len(stores)]["store_code"],
                "product_code": products[idx % len(products)]["product_code"],
                "current_stock": 10 + idx,
                "recent_7_sales": 20 + idx,
                "recent_30_sales": 80 + idx * 3,
                "avg_daily_sales": round((80 + idx * 3) / 30, 2),
                "safety_stock": 20,
                "recommended_quantity": 50 + idx,
                "recommended_supplier_name": suppliers[idx % len(suppliers)]["name"],
                "shortage_risk": idx % 2 == 0,
                "risk_level": ["low", "medium", "high"][idx % 3],
                "days_until_stockout": round((10 + idx) / max((80 + idx * 3) / 30, 0.1), 2),
                "reason": "规则模型生成的建议理由",
                "reason_enhanced": None,
                "llm_provider": "rule",
                "llm_used": False,
                "generated_at": f"{today}T12:00:00",
                "adoption_status": ["pending", "accepted", "rejected"][idx % 3],
            }
        )
    supplier_score_snapshots = []
    for idx, supplier in enumerate(suppliers, start=1):
        supplier_score_snapshots.append(
            {
                "supplier_name": supplier["name"],
                "product_count": 4 + idx,
                "avg_lead_time_days": 2 + idx % 4,
                "total_purchase_amount": 5000 + idx * 1000,
                "delayed_arrival_count": idx % 3,
                "score": 72 + idx,
                "score_source": "example_seed",
                "generated_at": f"{today}T10:30:00",
            }
        )
    promotions = [
        {"promotion_name": "开学季促销", "start_date": str(_safe_date(today.year, 9 if today.month >= 9 else today.month, 1)), "end_date": str(_safe_date(today.year, 9 if today.month >= 9 else today.month, 20)), "store_code": "STORE-A", "product_code": "P0021", "category_name": "文具", "promo_factor": 1.3, "description": "开学季文具热销"},
        {"promotion_name": "夏季饮料促销", "start_date": str(_safe_date(today.year, 6 if today.month >= 6 else today.month, 1)), "end_date": str(_safe_date(today.year, 8 if today.month >= 8 else today.month, 31)), "store_code": "STORE-B", "product_code": "P0001", "category_name": "饮料", "promo_factor": 1.4, "description": "夏季饮料销量提升"},
        {"promotion_name": "中秋节促销", "start_date": str(today), "end_date": str(today + timedelta(days=10)), "store_code": "STORE-C", "product_code": None, "category_name": "零食", "promo_factor": 1.2, "description": "节日礼盒促销"},
        {"promotion_name": "双十一促销", "start_date": str(today), "end_date": str(today + timedelta(days=5)), "store_code": "STORE-D", "product_code": None, "category_name": "日用品", "promo_factor": 1.5, "description": "双十一爆品活动"},
        {"promotion_name": "冬季日用品促销", "start_date": str(today), "end_date": str(today + timedelta(days=30)), "store_code": "STORE-E", "product_code": "P0017", "category_name": "日用品", "promo_factor": 1.15, "description": "冬季消耗品备货"},
    ]
    readme = """# Example Data\n\n本目录包含系统演示、初始化和测试所需的全部假数据。\n\n- categories.json: 商品类别及父子类别\n- products.json: 商品主数据\n- suppliers.json: 供应商主数据\n- supplier_products.json: 供应商商品关系\n- warehouses.json: 仓库主数据\n- stores.json: 门店主数据\n- users.json: 基础用户，导入时密码会自动哈希\n- inventory_seed.json: 初始库存\n- monthly_sales_facts.json: 最近12个月销售事实\n- purchase_orders.json: 采购订单及明细\n- inbound_orders.json: 入库单及明细\n- outbound_orders.json: 出库单及明细\n- replenishment_requests.json: 补货申请\n- stock_transactions.json: 示例库存流水\n- ai_recommendations.json: 初始AI补货建议\n- supplier_score_snapshots.json: 供应商评分快照\n- promotions.json: 促销活动数据\n"""
    files = {
        "categories.json": categories,
        "products.json": products,
        "suppliers.json": suppliers,
        "supplier_products.json": supplier_products,
        "warehouses.json": warehouses,
        "stores.json": stores,
        "users.json": users,
        "inventory_seed.json": inventory_seed,
        "monthly_sales_facts.json": monthly_sales_facts,
        "purchase_orders.json": purchase_orders,
        "inbound_orders.json": inbound_orders,
        "outbound_orders.json": outbound_orders,
        "replenishment_requests.json": replenishment_requests,
        "stock_transactions.json": stock_transactions,
        "ai_recommendations.json": ai_recommendations,
        "supplier_score_snapshots.json": supplier_score_snapshots,
        "promotions.json": promotions,
    }
    for filename, data in files.items():
        _write_json(example_dir / filename, data)
    (example_dir / "README.md").write_text(readme, encoding="utf-8")
    return {name: len(data) for name, data in files.items()}


def _load_json(name: str) -> list[dict]:
    return json.loads((get_settings().example_dir_path / name).read_text(encoding="utf-8"))


def _parse_date(value: str | None):
    return date.fromisoformat(value) if value else None


def _parse_datetime(value: str | None):
    return datetime.fromisoformat(value) if value else None


def load_example_data(db: Session) -> dict[str, int]:
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
    from app.models.user import User
    from app.models.warehouse import Warehouse

    categories = _load_json("categories.json")
    products = _load_json("products.json")
    suppliers = _load_json("suppliers.json")
    supplier_products = _load_json("supplier_products.json")
    warehouses = _load_json("warehouses.json")
    stores = _load_json("stores.json")
    users = _load_json("users.json")
    inventory_seed = _load_json("inventory_seed.json")
    monthly_sales_facts = _load_json("monthly_sales_facts.json")
    purchase_orders = _load_json("purchase_orders.json")
    inbound_orders = _load_json("inbound_orders.json")
    outbound_orders = _load_json("outbound_orders.json")
    replenishment_requests = _load_json("replenishment_requests.json")
    stock_transactions = _load_json("stock_transactions.json")
    ai_recommendations = _load_json("ai_recommendations.json")
    supplier_score_snapshots = _load_json("supplier_score_snapshots.json")
    promotions = _load_json("promotions.json")

    set_sqlite_foreign_keys(db, enabled=False)
    business_models = [
        AIRecommendation, MonthlySalesFact, Promotion, SupplierScoreSnapshot, CrossWarehouseTransferOrder, DistributedSyncLog,
        StockTransaction, OutboundItem, InboundItem, PurchaseOrderItem, OutboundOrder, InboundOrder, ReplenishmentRequest,
        PurchaseOrder, Inventory, SupplierProduct, Product, Category, Supplier, User, Store, Warehouse
    ]
    try:
        for model in business_models:
            db.query(model).delete()
    finally:
        set_sqlite_foreign_keys(db, enabled=True)
    db.flush()

    category_map = {}
    for item in categories:
        category = Category(name=item["name"], description=item.get("description"), is_active=True)
        db.add(category)
        db.flush()
        category_map[item["name"]] = category
    for item in categories:
        if item.get("parent_name"):
            category_map[item["name"]].parent_id = category_map[item["parent_name"]].id
    product_map = {}
    for item in products:
        product = Product(
            product_code=item["product_code"],
            name=item["name"],
            barcode=item["barcode"],
            category_id=category_map[item["category_name"]].id,
            spec=item["spec"],
            unit=item["unit"],
            shelf_life_days=item["shelf_life_days"],
            default_safety_stock=item["default_safety_stock"],
            is_active=item["is_active"],
        )
        db.add(product)
        db.flush()
        product_map[item["product_code"]] = product
    supplier_map = {}
    for item in suppliers:
        supplier = Supplier(**item)
        db.add(supplier)
        db.flush()
        supplier_map[item["name"]] = supplier
    for item in supplier_products:
        db.add(
            SupplierProduct(
                supplier_id=supplier_map[item["supplier_name"]].id,
                product_id=product_map[item["product_code"]].id,
                supply_price=item["supply_price"],
                lead_time_days=item["lead_time_days"],
                on_time_rate=item["on_time_rate"],
                quality_score=item["quality_score"],
                is_preferred=item["is_preferred"],
            )
        )
    warehouse_map = {}
    for item in warehouses:
        warehouse = Warehouse(**item)
        db.add(warehouse)
        db.flush()
        warehouse_map[item["warehouse_code"]] = warehouse
    store_map = {}
    for item in stores:
        store = Store(**item)
        db.add(store)
        db.flush()
        store_map[item["store_code"]] = store
    user_map = {}
    for item in users:
        user = User(
            username=item["username"],
            employee_no=item["employee_no"],
            password_hash=hash_password(item["password"]),
            verification_code_hash=hash_password(item["verification_code"]),
            real_name=item["real_name"],
            role=item["role"],
            location_type=item["location_type"],
            warehouse_id=warehouse_map[item["warehouse_code"]].id if item.get("warehouse_code") else None,
            store_id=store_map[item["store_code"]].id if item.get("store_code") else None,
            phone=item["phone"],
            is_active=item["is_active"],
            is_verified=item["is_verified"],
        )
        db.add(user)
        db.flush()
        user_map[item["username"]] = user
    for item in inventory_seed:
        inventory = Inventory(
            product_id=product_map[item["product_code"]].id,
            location_type=item["location_type"],
            warehouse_id=warehouse_map[item["warehouse_code"]].id if item.get("warehouse_code") else None,
            store_id=store_map[item["store_code"]].id if item.get("store_code") else None,
            current_quantity=item["current_quantity"],
            frozen_quantity=item["frozen_quantity"],
            safety_stock=item["safety_stock"],
            max_stock=item["max_stock"],
        )
        db.add(inventory)
        db.flush()
        db.add(
            StockTransaction(
                transaction_no=f"TXSEED{inventory.id:06d}",
                product_id=inventory.product_id,
                transaction_type="example_seed",
                source_location_type=None,
                source_warehouse_id=None,
                source_store_id=None,
                target_location_type=inventory.location_type,
                target_warehouse_id=inventory.warehouse_id,
                target_store_id=inventory.store_id,
                change_quantity=inventory.current_quantity,
                before_quantity=0,
                after_quantity=inventory.current_quantity,
                transaction_time=now_local(),
                operated_by=user_map["admin"].id,
                related_doc_type="example_seed",
                related_doc_id=inventory.id,
                remark="inventory seed bootstrap",
            )
        )
    for item in monthly_sales_facts:
        db.add(
            MonthlySalesFact(
                year=item["year"],
                month=item["month"],
                supplier_id=supplier_map[item["supplier_name"]].id,
                product_id=product_map[item["product_code"]].id,
                category_id=category_map[item["category_name"]].id,
                retail_sales=item["retail_sales"],
                retail_transfers=item["retail_transfers"],
                warehouse_sales=item["warehouse_sales"],
                store_id=store_map[item["store_code"]].id,
                warehouse_id=warehouse_map[item["warehouse_code"]].id,
                promo_flag=item["promo_flag"],
                is_example_data=True,
            )
        )
    purchase_order_map = {}
    for item in purchase_orders:
        po = PurchaseOrder(
            order_no=item["order_no"],
            supplier_id=supplier_map[item["supplier_name"]].id,
            created_by=user_map[item["created_by_username"]].id,
            created_at=_parse_datetime(f"{item['created_at']}T00:00:00") if "T" not in item["created_at"] else _parse_datetime(item["created_at"]),
            expected_arrival_date=_parse_date(item["expected_arrival_date"]),
            status=item["status"],
            total_amount=sum(sub["purchase_quantity"] * sub["purchase_price"] for sub in item["items"]),
            remark=item["remark"],
        )
        db.add(po)
        db.flush()
        purchase_order_map[item["order_no"]] = po
        for sub in item["items"]:
            db.add(
                PurchaseOrderItem(
                    purchase_order_id=po.id,
                    product_id=product_map[sub["product_code"]].id,
                    purchase_quantity=sub["purchase_quantity"],
                    purchase_price=sub["purchase_price"],
                    subtotal_amount=sub["purchase_quantity"] * sub["purchase_price"],
                )
            )
    replenishment_map = {}
    for item in replenishment_requests:
        req = ReplenishmentRequest(
            request_no=item["request_no"],
            store_id=store_map[item["store_code"]].id,
            product_id=product_map[item["product_code"]].id,
            request_quantity=item["request_quantity"],
            request_reason=item["request_reason"],
            request_time=_parse_datetime(item["request_time"]),
            audit_status=item["audit_status"],
            audited_by=user_map[item["audited_by_username"]].id if item.get("audited_by_username") else None,
            audit_time=_parse_datetime(item["audit_time"]) if item.get("audit_time") else None,
            created_by=user_map[item["created_by_username"]].id if item.get("created_by_username") else None,
        )
        db.add(req)
        db.flush()
        replenishment_map[item["request_no"]] = req
    outbound_map = {}
    for item in outbound_orders:
        outbound = OutboundOrder(
            outbound_no=item["outbound_no"],
            source_warehouse_id=warehouse_map[item["source_warehouse_code"]].id,
            target_store_id=store_map[item["target_store_code"]].id,
            outbound_time=_parse_datetime(item["outbound_time"]),
            handled_by=user_map[item["handled_by_username"]].id,
            status=item["status"],
            source_request_id=replenishment_map[item["source_request_no"]].id if item.get("source_request_no") else None,
            remark=item["remark"],
        )
        db.add(outbound)
        db.flush()
        outbound_map[item["outbound_no"]] = outbound
        for sub in item["items"]:
            db.add(
                OutboundItem(
                    outbound_order_id=outbound.id,
                    product_id=product_map[sub["product_code"]].id,
                    quantity=sub["quantity"],
                    batch_no=sub["batch_no"],
                )
            )
    for item in replenishment_requests:
        if item.get("generated_outbound_order_no"):
            replenishment_map[item["request_no"]].generated_outbound_order_id = outbound_map[item["generated_outbound_order_no"]].id
    for item in inbound_orders:
        inbound = InboundOrder(
            inbound_no=item["inbound_no"],
            purchase_order_id=purchase_order_map[item["purchase_order_no"]].id if item.get("purchase_order_no") else None,
            supplier_id=supplier_map[item["supplier_name"]].id,
            warehouse_id=warehouse_map[item["warehouse_code"]].id,
            inbound_time=_parse_datetime(item["inbound_time"]),
            handled_by=user_map[item["handled_by_username"]].id,
            status=item["status"],
            remark=item["remark"],
        )
        db.add(inbound)
        db.flush()
        for sub in item["items"]:
            db.add(
                InboundItem(
                    inbound_order_id=inbound.id,
                    product_id=product_map[sub["product_code"]].id,
                    quantity=sub["quantity"],
                    batch_no=sub["batch_no"],
                    production_date=_parse_date(sub["production_date"]),
                    expiry_date=_parse_date(sub["expiry_date"]),
                )
            )
    for item in stock_transactions:
        db.add(
            StockTransaction(
                transaction_no=item["transaction_no"],
                product_id=product_map[item["product_code"]].id,
                transaction_type=item["transaction_type"],
                source_location_type=item["source_location_type"],
                source_warehouse_id=warehouse_map[item["source_warehouse_code"]].id if item.get("source_warehouse_code") else None,
                source_store_id=store_map[item["source_store_code"]].id if item.get("source_store_code") else None,
                target_location_type=item["target_location_type"],
                target_warehouse_id=warehouse_map[item["target_warehouse_code"]].id if item.get("target_warehouse_code") else None,
                target_store_id=store_map[item["target_store_code"]].id if item.get("target_store_code") else None,
                change_quantity=item["change_quantity"],
                before_quantity=item["before_quantity"],
                after_quantity=item["after_quantity"],
                transaction_time=_parse_datetime(item["transaction_time"]),
                operated_by=user_map[item["operated_by_username"]].id if item.get("operated_by_username") else None,
                related_doc_type=item["related_doc_type"],
                related_doc_id=None,
                remark=item["remark"],
            )
        )
    for item in ai_recommendations:
        db.add(
            AIRecommendation(
                store_id=store_map[item["store_code"]].id,
                product_id=product_map[item["product_code"]].id,
                current_stock=item["current_stock"],
                recent_7_sales=item["recent_7_sales"],
                recent_30_sales=item["recent_30_sales"],
                avg_daily_sales=item["avg_daily_sales"],
                safety_stock=item["safety_stock"],
                recommended_quantity=item["recommended_quantity"],
                recommended_supplier_id=supplier_map[item["recommended_supplier_name"]].id if item.get("recommended_supplier_name") else None,
                shortage_risk=item["shortage_risk"],
                risk_level=item["risk_level"],
                days_until_stockout=item["days_until_stockout"],
                reason=item["reason"],
                reason_enhanced=item["reason_enhanced"],
                llm_provider=item["llm_provider"],
                llm_used=item["llm_used"],
                generated_at=_parse_datetime(item["generated_at"]),
                adoption_status=item["adoption_status"],
            )
        )
    for item in supplier_score_snapshots:
        db.add(
            SupplierScoreSnapshot(
                supplier_id=supplier_map[item["supplier_name"]].id,
                product_count=item["product_count"],
                avg_lead_time_days=item["avg_lead_time_days"],
                total_purchase_amount=item["total_purchase_amount"],
                delayed_arrival_count=item["delayed_arrival_count"],
                score=item["score"],
                score_source=item["score_source"],
                generated_at=_parse_datetime(item["generated_at"]),
            )
        )
    for item in promotions:
        db.add(
            Promotion(
                promotion_name=item["promotion_name"],
                start_date=_parse_date(item["start_date"]),
                end_date=_parse_date(item["end_date"]),
                store_id=store_map[item["store_code"]].id if item.get("store_code") else None,
                product_id=product_map[item["product_code"]].id if item.get("product_code") else None,
                category_id=category_map[item["category_name"]].id if item.get("category_name") else None,
                promo_factor=item["promo_factor"],
                description=item["description"],
            )
        )
    db.flush()
    return {
        "categories": len(categories),
        "products": len(products),
        "suppliers": len(suppliers),
        "supplier_products": len(supplier_products),
        "warehouses": len(warehouses),
        "stores": len(stores),
        "users": len(users),
        "inventory": len(inventory_seed),
        "monthly_sales_facts": len(monthly_sales_facts),
        "purchase_orders": len(purchase_orders),
        "inbound_orders": len(inbound_orders),
        "outbound_orders": len(outbound_orders),
        "replenishment_requests": len(replenishment_requests),
        "stock_transactions": len(stock_transactions),
        "ai_recommendations": len(ai_recommendations),
        "supplier_score_snapshots": len(supplier_score_snapshots),
        "promotions": len(promotions),
    }


def get_example_status(db: Session) -> dict[str, Any]:
    example_dir = get_settings().example_dir_path
    files = {}
    if example_dir.exists():
        for path in example_dir.glob("*.json"):
            files[path.name] = len(json.loads(path.read_text(encoding="utf-8")))
    table_counts = {}
    for table in Base.metadata.tables:
        table_counts[table] = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
    return {"example_exists": example_dir.exists(), "files": files, "tables": table_counts}
