# 最小接口契约 v0.1

> 本文件用于前后端协作。前端只调用本文件中的接口；后端优先保证本文件中的接口稳定。除非全员确认，不要随意修改路径、字段名、响应结构。

---

## 0. 契约范围

本接口契约覆盖期末 Demo 必须展示的最小业务闭环：

```text
系统状态
→ 首页看板
→ 基础数据查询
→ 库存查询与预警
→ 采购入库
→ 库存流水
→ 门店补货申请
→ 审核补货申请
→ 转出库单
→ 出库发货
→ 门店签收
→ AI 补货建议
→ 供应商评分与统计分析
```

## 22. Walmart 外部数据状态接口

### 22.1 `GET /api/external-data/walmart/status`

- 用途：查看 Walmart 外部销售数据是否已导入，以及当前实际运行数据库模式。
- 成功响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "raw_weekly_sales_count": 0,
    "monthly_sales_fact_count": 0,
    "store_count": 0,
    "department_product_count": 0,
    "min_sales_date": null,
    "max_sales_date": null,
    "database_runtime": {
      "mode": "oceanbase-primary",
      "active_dialect": "mysql"
    }
  }
}
```

- `raw_weekly_sales_count`：`walmart_weekly_sales_facts` 中的 Walmart 周销售事实行数。
- `monthly_sales_fact_count`：写入 `monthly_sales_facts` 且 `is_example_data=false` 的 Walmart 月销售事实行数。
- `store_count`：`walmart_store_profiles` 中的 Walmart 门店数。
- `department_product_count`：映射到现有 `products` 的 Walmart 部门商品数。
- `min_sales_date` / `max_sales_date`：Walmart 周事实最早和最晚销售日期。
- `database_runtime.mode`：当前数据库模式，可能是 `oceanbase-primary` 或 `sqlite-fallback`。
- `database_runtime.active_dialect`：当前 SQLAlchemy 实际方言，例如 `mysql` 或 `sqlite`。

本契约不覆盖完整登录注册、复杂权限系统、完整企业级审批流。

---

## 1. 通用约定

### 1.1 Base URL

开发环境：

```text
http://127.0.0.1:8000
```

API 前缀：

```text
/api
```

前端请求示例：

```js
fetch("/api/analytics/dashboard")
```

### 1.2 Content-Type

所有请求与响应默认使用：

```http
Content-Type: application/json
```

### 1.3 通用成功响应格式

所有接口统一返回：

```json
{
  "success": true,
  "message": "ok",
  "data": {}
}
```

### 1.4 通用失败响应格式

```json
{
  "success": false,
  "message": "错误信息",
  "data": null
}
```

前端处理规则：

```js
const json = await response.json();
if (!response.ok || !json.success) {
  throw new Error(json.message || "请求失败");
}
return json.data;
```

### 1.5 分页响应格式

列表接口如果分页，统一返回：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20
  }
}
```

### 1.6 分页查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---:|---:|---:|---|
| `page` | int | 否 | 1 | 页码，从 1 开始 |
| `page_size` | int | 否 | 20 | 每页数量 |
| `keyword` | string | 否 | null | 搜索关键词 |

示例：

```text
GET /api/products?page=1&page_size=20&keyword=矿泉水
```

### 1.7 时间格式

统一使用 ISO 8601 字符串或后端默认 datetime JSON 字符串：

```json
"2026-06-27T14:30:00"
```

前端只展示即可，不在前端做复杂时区换算。

### 1.8 金额格式

金额字段可由后端返回字符串或数字。前端展示时统一转成字符串。

示例：

```json
"total_amount": "1280.00"
```

或：

```json
"total_amount": 1280.00
```

### 1.9 状态字段约定

#### 采购订单状态 `PurchaseOrder.status`

| 值 | 中文含义 |
|---|---|
| `pending` | 待确认 |
| `confirmed` | 已确认 |
| `partial_received` | 部分到货 |
| `completed` | 已完成 |
| `cancelled` | 已取消 |

#### 入库单状态 `InboundOrder.status`

| 值 | 中文含义 |
|---|---|
| `pending` | 待入库 |
| `completed` | 已入库 |
| `cancelled` | 已取消 |

#### 出库单状态 `OutboundOrder.status`

| 值 | 中文含义 |
|---|---|
| `pending` | 待出库 |
| `shipped` | 已出库 / 已发货 |
| `signed` | 门店已签收 |
| `cancelled` | 已取消 |

#### 补货申请审核状态 `ReplenishmentRequest.audit_status`

| 值 | 中文含义 |
|---|---|
| `pending` | 待审核 |
| `approved` | 已通过 |
| `rejected` | 已拒绝 |

#### AI 建议采纳状态 `AIRecommendation.adoption_status`

| 值 | 中文含义 |
|---|---|
| `pending` | 未处理 |
| `accepted` | 已采纳 |
| `rejected` | 已拒绝 |

#### 风险等级 `risk_level`

| 值 | 中文含义 |
|---|---|
| `low` | 低风险 |
| `medium` | 中风险 |
| `high` | 高风险 |

#### 库存位置类型 `location_type`

| 值 | 中文含义 |
|---|---|
| `warehouse` | 仓库 |
| `store` | 门店 |

---

## 2. 前端统一 API 封装要求

前端必须只在 `frontend/api.js` 中写 `fetch`，页面代码不要散写请求。

推荐实现：

```js
const API_BASE = "/api";
const USE_MOCK = false;

async function request(path, options = {}) {
  if (USE_MOCK) return mockRequest(path, options);

  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  const json = await res.json().catch(() => null);
  if (!res.ok || !json?.success) {
    throw new Error(json?.message || "请求失败");
  }
  return json.data;
}

function get(path) {
  return request(path);
}

function post(path, body = undefined) {
  return request(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
```

---

## 3. 系统状态接口

### 3.1 健康检查

```http
GET /api/health
```

用途：确认后端和数据库连接可用。

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "status": "running",
    "database": "connected",
    "app": "Supply Chain Management"
  }
}
```

### 3.2 数据库状态

```http
GET /api/health/db
```

用途：前端首页展示当前数据库类型；OceanBase 加分项展示。

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "status": "connected",
    "dialect": "sqlite",
    "database_url_masked": "sqlite:///schema/supply_chain.db"
  }
}
```

OceanBase / MySQL 模式示例：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "status": "connected",
    "dialect": "mysql",
    "database_url_masked": "mysql+pymysql://root:***@127.0.0.1:2881/supply_chain?charset=utf8mb4"
  }
}
```

前端展示字段：

| 字段 | 展示名称 |
|---|---|
| `status` | 数据库状态 |
| `dialect` | 数据库类型 |
| `database_url_masked` | 数据库连接 |

### 3.3 演示登录

```http
POST /api/users/login
```

请求：

```json
{
  "username": "admin",
  "password": "admin123"
}
```

成功响应中的 `data` 为用户对象，不包含密码或密码摘要：

```json
{
  "success": true,
  "message": "登录成功",
  "data": {
    "id": 1,
    "username": "admin",
    "real_name": "系统管理员",
    "role": "admin",
    "location_type": null,
    "warehouse_id": null,
    "store_id": null,
    "phone": "13000000001",
    "is_active": true,
    "created_at": "2026-06-27T10:00:00"
  }
}
```

失败时返回 HTTP 401 和统一失败响应，`message` 为 `用户名或密码错误`。

说明：该接口用于课程 Demo 的身份校验和用户信息展示，不签发 Token，也不实现复杂角色权限控制，符合 workplan 中“不做完整登录注册与复杂权限控制”的范围约束。

---

## 4. 示例数据接口

### 4.1 查看示例数据状态

```http
GET /api/example/status
```

用途：确认是否已导入演示数据。

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "products": 30,
    "suppliers": 8,
    "warehouses": 3,
    "stores": 10,
    "inventory_records": 120,
    "inbound_orders": 8,
    "outbound_orders": 10,
    "replenishment_requests": 12,
    "stock_transactions": 50
  }
}
```

如果后端实际返回字段更多，前端忽略未知字段。

### 4.2 导入示例数据

```http
POST /api/example/load
```

用途：开发阶段手动导入示例数据。现场演示一般使用命令行脚本导入，不一定在前端放按钮。

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "loaded": true,
    "message": "example data loaded"
  }
}
```

---

## 5. 首页看板接口

### 5.1 首页 Dashboard

```http
GET /api/analytics/dashboard
```

用途：演示系统整体状态。

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "product_count": 30,
    "supplier_count": 8,
    "warehouse_count": 3,
    "store_count": 10,
    "stockout_count": 6,
    "overstock_count": 4,
    "recent_outbound_quantity": 560,
    "ai_recommendation_count": 12,
    "high_risk_recommendation_count": 3,
    "total_inventory_quantity": 8500,
    "top_stockout_products": [
      {
        "product_id": 1,
        "product_name": "矿泉水",
        "location_type": "store",
        "location_name": "门店A",
        "current_quantity": 18,
        "safety_stock": 30,
        "warning_type": "stockout",
        "warning_message": "矿泉水 在 门店A 触发 stockout 预警"
      }
    ],
    "top_overstock_products": [
      {
        "product_id": 2,
        "product_name": "纸巾",
        "location_type": "warehouse",
        "location_name": "中心仓",
        "current_quantity": 1200,
        "safety_stock": 100,
        "max_stock": 500,
        "warning_type": "overstock",
        "warning_message": "纸巾 在 中心仓 触发 overstock 预警"
      }
    ]
  }
}
```

前端必须展示：

| 字段 | 展示名称 |
|---|---|
| `product_count` | 商品数 |
| `supplier_count` | 供应商数 |
| `warehouse_count` | 仓库数 |
| `store_count` | 门店数 |
| `stockout_count` | 缺货预警数 |
| `overstock_count` | 积压预警数 |
| `recent_outbound_quantity` | 近期出库量 |
| `ai_recommendation_count` | AI 建议数 |
| `high_risk_recommendation_count` | 高风险建议数 |
| `total_inventory_quantity` | 库存总量 |

前端可选展示：

- `top_stockout_products`
- `top_overstock_products`

### 5.2 统计摘要文本

```http
GET /api/analytics/summary-text
```

用途：在首页展示一句系统运行摘要，可用于汇报讲解。

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "summary": "当前系统共有 30 个商品、8 个供应商，缺货预警 6 条，积压预警 4 条，高风险补货建议 3 条。",
    "llm_used": false
  }
}
```

---

## 6. 基础数据接口

基础数据接口用于前端列表展示和选择框。Demo 阶段不要求做完整增删改界面，但接口契约保留 CRUD 约定。

### 6.1 商品列表

```http
GET /api/products?page=1&page_size=20&keyword=矿泉水
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "product_code": "P0001",
        "name": "矿泉水",
        "barcode": "690000000001",
        "category_id": 1,
        "spec": "550ml*24",
        "unit": "箱",
        "shelf_life_days": 365,
        "default_safety_stock": 30,
        "is_active": true,
        "created_at": "2026-06-27T10:00:00",
        "updated_at": "2026-06-27T10:00:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### 6.2 商品详情

```http
GET /api/products/{product_id}
```

响应：同单个商品对象。

### 6.3 新增商品

```http
POST /api/products
```

请求：

```json
{
  "product_code": "P0099",
  "name": "测试商品",
  "barcode": "690000009999",
  "category_id": 1,
  "spec": "1箱",
  "unit": "箱",
  "shelf_life_days": 365,
  "default_safety_stock": 20,
  "is_active": true
}
```

响应：新建商品对象。

### 6.4 更新商品

```http
PUT /api/products/{product_id}
```

请求：

```json
{
  "name": "测试商品-修改",
  "default_safety_stock": 30,
  "is_active": true
}
```

### 6.5 删除商品 / 逻辑删除

```http
DELETE /api/products/{product_id}
```

响应：

```json
{
  "success": true,
  "message": "deleted",
  "data": null
}
```

### 6.6 类别列表

```http
GET /api/categories?page=1&page_size=20&keyword=饮料
```

单项字段：

```json
{
  "id": 1,
  "name": "饮料",
  "parent_id": null,
  "description": "饮料类商品",
  "is_active": true,
  "created_at": "2026-06-27T10:00:00"
}
```

### 6.7 供应商列表

```http
GET /api/suppliers?page=1&page_size=20&keyword=供应商
```

单项字段：

```json
{
  "id": 1,
  "name": "供应商S01",
  "contact_person": "张三",
  "phone": "13800000000",
  "email": "s01@example.com",
  "address": "上海市",
  "supplier_level": "A",
  "cooperation_status": "active",
  "is_active": true,
  "created_at": "2026-06-27T10:00:00",
  "updated_at": "2026-06-27T10:00:00"
}
```

### 6.8 仓库列表

```http
GET /api/warehouses?page=1&page_size=20&keyword=中心仓
```

单项字段：

```json
{
  "id": 1,
  "warehouse_code": "W001",
  "name": "中心仓",
  "address": "上海市杨浦区",
  "manager_name": "王五",
  "phone": "13800000001",
  "capacity": 10000,
  "status": "active",
  "created_at": "2026-06-27T10:00:00",
  "updated_at": "2026-06-27T10:00:00"
}
```

如果后端实际字段名是 `manager` 而非 `manager_name`，以当前 schema 为准，前端只展示存在的字段。

### 6.9 门店列表

```http
GET /api/stores?page=1&page_size=20&keyword=门店A
```

单项字段：

```json
{
  "id": 1,
  "store_code": "S001",
  "name": "门店A",
  "region": "杨浦区",
  "address": "上海市杨浦区",
  "longitude": 121.50,
  "latitude": 31.30,
  "contact_person": "李四",
  "phone": "13800000002",
  "business_status": "open",
  "created_at": "2026-06-27T10:00:00",
  "updated_at": "2026-06-27T10:00:00"
}
```

### 6.10 新增供应商

```http
POST /api/suppliers
```

请求字段与 6.7 的供应商字段一致，不传 `id`、`created_at`、`updated_at`。

### 6.11 新增仓库

```http
POST /api/warehouses
```

请求字段与 6.8 的仓库字段一致，不传数据库生成字段。必填字段为 `warehouse_code`、`name`。

### 6.12 新增门店

```http
POST /api/stores
```

请求字段与 6.9 的门店字段一致，不传数据库生成字段。必填字段为 `store_code`、`name`。

以上新增接口均返回统一成功响应，`data` 为新建后的完整对象。

---

## 7. 库存接口

### 7.1 库存列表

```http
GET /api/inventory?page=1&page_size=20&keyword=矿泉水
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "product_id": 1,
        "location_type": "warehouse",
        "warehouse_id": 1,
        "store_id": null,
        "current_quantity": 500,
        "frozen_quantity": 0,
        "safety_stock": 100,
        "max_stock": 1000,
        "last_updated_at": "2026-06-27T10:00:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

前端展示字段：

| 字段 | 展示名称 |
|---|---|
| `product_id` | 商品 ID |
| `location_type` | 位置类型 |
| `warehouse_id` | 仓库 ID |
| `store_id` | 门店 ID |
| `current_quantity` | 当前库存 |
| `frozen_quantity` | 冻结库存 |
| `current_quantity - frozen_quantity` | 可用库存 |
| `safety_stock` | 安全库存 |
| `max_stock` | 最大库存 |
| `last_updated_at` | 更新时间 |

### 7.2 某商品库存分布

```http
GET /api/inventory/product/{product_id}/distribution
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "location_type": "warehouse",
      "warehouse_id": 1,
      "store_id": null,
      "location_name": "中心仓",
      "current_quantity": 500,
      "frozen_quantity": 0,
      "available_quantity": 500,
      "safety_stock": 100,
      "max_stock": 1000
    },
    {
      "location_type": "store",
      "warehouse_id": null,
      "store_id": 1,
      "location_name": "门店A",
      "current_quantity": 18,
      "frozen_quantity": 0,
      "available_quantity": 18,
      "safety_stock": 30,
      "max_stock": 150
    }
  ]
}
```

### 7.3 某门店库存

```http
GET /api/inventory/store/{store_id}
```

响应：库存对象数组。

### 7.4 某仓库库存

```http
GET /api/inventory/warehouse/{warehouse_id}
```

响应：库存对象数组。

### 7.5 库存预警

```http
GET /api/inventory/warnings
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "product_id": 1,
      "product_name": "矿泉水",
      "location_type": "store",
      "location_name": "门店A",
      "current_quantity": 18,
      "frozen_quantity": 0,
      "available_quantity": 18,
      "safety_stock": 30,
      "max_stock": 150,
      "warning_type": "stockout",
      "warning_message": "矿泉水 在 门店A 触发 stockout 预警"
    },
    {
      "product_id": 2,
      "product_name": "纸巾",
      "location_type": "warehouse",
      "location_name": "中心仓",
      "current_quantity": 1200,
      "frozen_quantity": 0,
      "available_quantity": 1200,
      "safety_stock": 100,
      "max_stock": 500,
      "warning_type": "overstock",
      "warning_message": "纸巾 在 中心仓 触发 overstock 预警"
    }
  ]
}
```

`warning_type` 取值：

| 值 | 中文含义 | 规则建议 |
|---|---|---|
| `critical_stockout` | 严重缺货 | `current_quantity <= safety_stock * 0.5` |
| `stockout` | 库存不足 | `current_quantity <= safety_stock` |
| `overstock` | 库存积压 | `current_quantity >= max(max_stock, safety_stock * 4)` |

### 7.6 库存汇总

```http
GET /api/inventory/summary
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "total_inventory_quantity": 8500,
    "warehouse_inventory_quantity": 6000,
    "store_inventory_quantity": 2500,
    "warning_count": 10,
    "inventory_record_count": 120
  }
}
```

### 7.7 库存盘点调整

```http
POST /api/inventory/adjust
```

请求：

```json
{
  "product_id": 1,
  "location_type": "warehouse",
  "warehouse_id": 1,
  "store_id": null,
  "new_quantity": 520,
  "operator_id": 1,
  "remark": "盘点调整"
}
```

响应：调整后的库存对象。

业务规则：

- `new_quantity >= 0`。
- 必须生成库存流水。
- 调整操作必须在事务内完成。

---

## 8. 采购订单接口

### 8.1 创建采购订单

```http
POST /api/purchase-orders
```

请求：

```json
{
  "supplier_id": 1,
  "expected_arrival_date": "2026-06-30",
  "created_by": 1,
  "remark": "演示采购订单",
  "items": [
    {
      "product_id": 1,
      "purchase_quantity": 100,
      "purchase_price": "20.00"
    },
    {
      "product_id": 2,
      "purchase_quantity": 50,
      "purchase_price": "15.00"
    }
  ]
}
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "id": 1,
    "order_no": "PO202606270001",
    "supplier_id": 1,
    "created_by": 1,
    "created_at": "2026-06-27T10:00:00",
    "expected_arrival_date": "2026-06-30",
    "status": "pending",
    "total_amount": "2750.00",
    "remark": "演示采购订单",
    "items": [
      {
        "id": 1,
        "product_id": 1,
        "purchase_quantity": 100,
        "purchase_price": "20.00",
        "subtotal_amount": "2000.00"
      }
    ]
  }
}
```

业务规则：

- `purchase_quantity > 0`。
- `purchase_price >= 0`。
- `total_amount = sum(purchase_quantity * purchase_price)`。

### 8.2 采购订单列表

```http
GET /api/purchase-orders?page=1&page_size=20&keyword=PO
```

响应：分页采购订单。

### 8.3 采购订单详情

```http
GET /api/purchase-orders/{order_id}
```

响应：单个采购订单对象。

### 8.4 确认采购订单

```http
POST /api/purchase-orders/{order_id}/confirm
```

响应：更新后的采购订单对象。

业务规则：

- 只有 `pending` 状态可以确认。
- 确认后状态变为 `confirmed`。

### 8.5 取消采购订单

```http
POST /api/purchase-orders/{order_id}/cancel
```

响应：更新后的采购订单对象。

业务规则：

- 已完成采购订单不应取消。

---

## 9. 入库接口

### 9.1 创建入库单

```http
POST /api/inbound-orders
```

请求：

```json
{
  "purchase_order_id": 1,
  "supplier_id": 1,
  "warehouse_id": 1,
  "handled_by": 1,
  "status": "pending",
  "remark": "采购到货入库",
  "items": [
    {
      "product_id": 1,
      "quantity": 100,
      "batch_no": "B20260627001",
      "production_date": "2026-06-01",
      "expiry_date": "2027-06-01"
    }
  ]
}
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "id": 1,
    "inbound_no": "IN202606270001",
    "purchase_order_id": 1,
    "supplier_id": 1,
    "warehouse_id": 1,
    "inbound_time": "2026-06-27T10:00:00",
    "handled_by": 1,
    "status": "pending",
    "remark": "采购到货入库",
    "items": [
      {
        "id": 1,
        "product_id": 1,
        "quantity": 100,
        "batch_no": "B20260627001",
        "production_date": "2026-06-01",
        "expiry_date": "2027-06-01"
      }
    ]
  }
}
```

### 9.2 根据采购订单生成入库单

```http
POST /api/inbound-orders/from-purchase/{purchase_order_id}?handled_by=1&warehouse_id=1
```

响应：入库单对象。

业务规则：

- 采购订单必须存在；
- 入库仓库必须合法；
- 入库单初始状态为 `pending`。

### 9.3 入库单列表

```http
GET /api/inbound-orders?page=1&page_size=20&keyword=IN
```

响应：分页入库单。

### 9.4 入库单详情

```http
GET /api/inbound-orders/{order_id}
```

响应：单个入库单对象。

### 9.5 完成入库

```http
POST /api/inbound-orders/{order_id}/complete
```

用途：Demo 必须展示。

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "id": 1,
    "inbound_no": "IN202606270001",
    "purchase_order_id": 1,
    "supplier_id": 1,
    "warehouse_id": 1,
    "inbound_time": "2026-06-27T10:00:00",
    "handled_by": 1,
    "status": "completed",
    "remark": "采购到货入库",
    "items": [
      {
        "id": 1,
        "product_id": 1,
        "quantity": 100,
        "batch_no": "B20260627001",
        "production_date": "2026-06-01",
        "expiry_date": "2027-06-01"
      }
    ]
  }
}
```

业务规则：

- 入库单必须存在。
- 只有 `pending` 状态可以完成。
- 每个明细的 `quantity > 0`。
- 完成入库后增加仓库库存。
- 必须生成库存流水。
- 必须在事务内完成。
- 重复调用不能重复增加库存。

失败示例：

```json
{
  "success": false,
  "message": "only pending inbound order can be completed",
  "data": null
}
```

---

## 10. 门店补货申请接口

### 10.1 创建补货申请

```http
POST /api/replenishment-requests
```

请求：

```json
{
  "store_id": 1,
  "product_id": 1,
  "request_quantity": 80,
  "request_reason": "门店库存低于安全库存，申请补货",
  "created_by": 4
}
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "id": 1,
    "request_no": "RR202606270001",
    "store_id": 1,
    "product_id": 1,
    "request_quantity": 80,
    "request_reason": "门店库存低于安全库存，申请补货",
    "request_time": "2026-06-27T10:00:00",
    "audit_status": "pending",
    "audited_by": null,
    "audit_time": null,
    "created_by": 4,
    "generated_outbound_order_id": null
  }
}
```

业务规则：

- `request_quantity > 0`。
- 门店和商品必须存在。

### 10.2 补货申请列表

```http
GET /api/replenishment-requests?page=1&page_size=20&keyword=RR
```

响应：分页补货申请。

前端 Demo 展示字段：

| 字段 | 展示名称 |
|---|---|
| `id` | 申请 ID |
| `request_no` | 申请编号 |
| `store_id` | 门店 ID |
| `product_id` | 商品 ID |
| `request_quantity` | 申请数量 |
| `request_reason` | 申请原因 |
| `audit_status` | 审核状态 |
| `generated_outbound_order_id` | 生成的出库单 ID |

### 10.3 补货申请详情

```http
GET /api/replenishment-requests/{request_id}
```

响应：单个补货申请对象。

### 10.4 审核通过补货申请

```http
POST /api/replenishment-requests/{request_id}/approve?audited_by=1
```

用途：Demo 必须展示。

响应：审核后的补货申请对象：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "id": 1,
    "request_no": "RR202606270001",
    "store_id": 1,
    "product_id": 1,
    "request_quantity": 80,
    "request_reason": "门店库存低于安全库存，申请补货",
    "request_time": "2026-06-27T10:00:00",
    "audit_status": "approved",
    "audited_by": 1,
    "audit_time": "2026-06-27T10:05:00",
    "created_by": 4,
    "generated_outbound_order_id": null
  }
}
```

业务规则：

- 申请必须存在。
- 只有 `pending` 状态可以审核。
- 审核后状态为 `approved`。

### 10.5 拒绝补货申请

```http
POST /api/replenishment-requests/{request_id}/reject?audited_by=1
```

响应：拒绝后的补货申请对象。

业务规则：

- 只有 `pending` 状态可以拒绝。
- 拒绝后不能转出库单。

### 10.6 补货申请转出库单

```http
POST /api/replenishment-requests/{request_id}/convert-to-outbound?source_warehouse_id=1&handled_by=1
```

用途：Demo 必须展示。

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "outbound_order_id": 1,
    "outbound_no": "OUT202606270001"
  }
}
```

业务规则：

- 申请必须存在。
- 只有 `approved` 状态可以转出库单。
- `source_warehouse_id` 必须合法。
- 转出库单后，补货申请的 `generated_outbound_order_id` 应被记录。
- 同一补货申请不能重复生成多个出库单。

失败示例：

```json
{
  "success": false,
  "message": "only approved request can be converted to outbound order",
  "data": null
}
```

---

## 11. 出库接口

### 11.1 创建出库单

```http
POST /api/outbound-orders
```

请求：

```json
{
  "source_warehouse_id": 1,
  "target_store_id": 1,
  "handled_by": 1,
  "source_request_id": 1,
  "remark": "补货申请转出库",
  "items": [
    {
      "product_id": 1,
      "quantity": 80,
      "batch_no": "B20260627001"
    }
  ]
}
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "id": 1,
    "outbound_no": "OUT202606270001",
    "source_warehouse_id": 1,
    "target_store_id": 1,
    "outbound_time": "2026-06-27T10:10:00",
    "handled_by": 1,
    "status": "pending",
    "source_request_id": 1,
    "remark": "补货申请转出库",
    "items": [
      {
        "id": 1,
        "product_id": 1,
        "quantity": 80,
        "batch_no": "B20260627001"
      }
    ]
  }
}
```

业务规则：

- `quantity > 0`。
- 仓库和门店必须合法。
- 初始状态为 `pending`。

### 11.2 出库单列表

```http
GET /api/outbound-orders?page=1&page_size=20&keyword=OUT
```

响应：分页出库单。

### 11.3 出库单详情

```http
GET /api/outbound-orders/{order_id}
```

响应：单个出库单对象。

### 11.4 出库发货

```http
POST /api/outbound-orders/{order_id}/ship
```

用途：Demo 必须展示。

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "id": 1,
    "outbound_no": "OUT202606270001",
    "source_warehouse_id": 1,
    "target_store_id": 1,
    "outbound_time": "2026-06-27T10:10:00",
    "handled_by": 1,
    "status": "shipped",
    "source_request_id": 1,
    "remark": "补货申请转出库",
    "items": [
      {
        "id": 1,
        "product_id": 1,
        "quantity": 80,
        "batch_no": "B20260627001"
      }
    ]
  }
}
```

业务规则：

- 出库单必须存在。
- 只有 `pending` 状态可以发货。
- 发货前必须检查仓库可用库存。
- 可用库存 = `current_quantity - frozen_quantity`。
- 可用库存不足时必须失败，不允许库存为负。
- 发货成功后扣减仓库库存。
- 门店库存增加的时点必须统一：
  - 方案 A：发货时直接增加门店库存；
  - 方案 B：签收时才增加门店库存。
- 本项目建议采用方案 A，演示更直观；如果采用方案 B，前端文案要写“在途”。
- 必须生成库存流水。
- 重复调用不能重复扣减库存。

库存不足失败示例：

```json
{
  "success": false,
  "message": "库存不足，无法出库",
  "data": null
}
```

### 11.5 门店签收

```http
POST /api/outbound-orders/{order_id}/sign
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "id": 1,
    "outbound_no": "OUT202606270001",
    "status": "signed",
    "source_warehouse_id": 1,
    "target_store_id": 1,
    "handled_by": 1,
    "source_request_id": 1,
    "remark": "补货申请转出库",
    "items": [
      {
        "id": 1,
        "product_id": 1,
        "quantity": 80,
        "batch_no": "B20260627001"
      }
    ]
  }
}
```

业务规则：

- 只有 `shipped` 状态可以签收。
- 签收后状态为 `signed`。
- 如果采用“签收时增加门店库存”，则此接口必须增加门店库存并生成流水。
- 如果采用“发货时增加门店库存”，则此接口只更新状态，不重复增加库存。

### 11.6 取消出库单

```http
POST /api/outbound-orders/{order_id}/cancel
```

响应：取消后的出库单对象。

业务规则：

- 只有 `pending` 状态建议允许取消。
- 已发货或已签收不建议取消。

---

## 12. 库存流水接口

### 12.1 库存流水列表

```http
GET /api/transactions?page=1&page_size=20&keyword=TX
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "transaction_no": "TX202606270001",
        "product_id": 1,
        "transaction_type": "purchase_inbound",
        "source_location_type": "supplier",
        "source_warehouse_id": null,
        "source_store_id": null,
        "target_location_type": "warehouse",
        "target_warehouse_id": 1,
        "target_store_id": null,
        "change_quantity": 100,
        "before_quantity": 500,
        "after_quantity": 600,
        "transaction_time": "2026-06-27T10:20:00",
        "operated_by": 1,
        "related_doc_type": "inbound_order",
        "related_doc_id": 1,
        "remark": "采购入库"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

前端展示字段：

| 字段 | 展示名称 |
|---|---|
| `transaction_no` | 流水编号 |
| `product_id` | 商品 ID |
| `transaction_type` | 操作类型 |
| `change_quantity` | 变动数量 |
| `before_quantity` | 操作前库存 |
| `after_quantity` | 操作后库存 |
| `related_doc_type` | 关联单据类型 |
| `related_doc_id` | 关联单据 ID |
| `transaction_time` | 操作时间 |

### 12.2 按商品查询流水

```http
GET /api/transactions/product/{product_id}
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "transaction_no": "TX202606270001",
      "transaction_type": "purchase_inbound",
      "change_quantity": 100
    }
  ]
}
```

建议后续增强为返回完整字段，但 Demo 阶段保留现有字段即可。

### 12.3 按单据查询流水

```http
GET /api/transactions/doc/{doc_type}/{doc_id}
```

示例：

```text
GET /api/transactions/doc/inbound_order/1
GET /api/transactions/doc/outbound_order/1
```

响应：流水数组。

### 12.4 商品流转追溯

```http
GET /api/transactions/product/{product_id}/trace
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "source": "example_data",
      "product": "矿泉水",
      "transaction_no": "TX202606270001",
      "path": "supplier -> warehouse",
      "related_doc_type": "inbound_order"
    },
    {
      "source": "example_data",
      "product": "矿泉水",
      "transaction_no": "TX202606270002",
      "path": "warehouse -> store",
      "related_doc_type": "outbound_order"
    }
  ]
}
```

前端可用时间线展示。

---

## 13. AI 补货建议接口

### 13.1 生成 AI 补货建议

```http
POST /api/recommendations/generate
```

查询参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---:|---:|---:|---|
| `store_id` | int | 否 | null | 只为某门店生成建议 |
| `enhance_with_llm` | bool | 否 | false | 是否用 LLM 增强解释 |

示例：

```text
POST /api/recommendations/generate
POST /api/recommendations/generate?store_id=1&enhance_with_llm=false
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "count": 5
  }
}
```

说明：

- 当前后端生成接口返回数量，前端需要再调用 `GET /api/recommendations` 获取详情。
- Demo 中按钮逻辑应为：先 `POST /generate`，成功后自动刷新建议列表。

业务规则：

- 没有 LLM API 时也必须能生成规则型建议。
- 推荐数量不能为负。
- 建议理由不能为空。

### 13.2 AI 补货建议列表

```http
GET /api/recommendations
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "id": 1,
      "store_id": 1,
      "product_id": 1,
      "current_stock": 18,
      "recent_7_sales": 56.0,
      "recent_30_sales": 210.0,
      "avg_daily_sales": 8.0,
      "safety_stock": 30,
      "recommended_quantity": 80,
      "recommended_supplier_id": 1,
      "shortage_risk": true,
      "risk_level": "high",
      "days_until_stockout": 2.25,
      "reason": "当前库存低于安全库存，近7天日均出库量较高，预计约2天后缺货，建议补货80件。",
      "reason_enhanced": null,
      "llm_provider": "rule",
      "llm_used": false,
      "generated_at": "2026-06-27T10:30:00",
      "adoption_status": "pending"
    }
  ]
}
```

前端展示字段：

| 字段 | 展示名称 |
|---|---|
| `store_id` | 门店 ID |
| `product_id` | 商品 ID |
| `current_stock` | 当前库存 |
| `safety_stock` | 安全库存 |
| `recent_7_sales` | 近 7 天出库量 |
| `recent_30_sales` | 近 30 天出库量 |
| `recommended_quantity` | 建议补货量 |
| `recommended_supplier_id` | 推荐供应商 ID |
| `shortage_risk` | 是否有缺货风险 |
| `risk_level` | 风险等级 |
| `days_until_stockout` | 预计缺货天数 |
| `reason` | 推荐理由 |
| `adoption_status` | 采纳状态 |

### 13.3 按门店查询 AI 建议

```http
GET /api/recommendations/store/{store_id}
```

响应：AI 建议数组。

### 13.4 采纳 AI 建议

```http
POST /api/recommendations/{recommendation_id}/accept
```

响应：更新后的 AI 建议对象。

业务规则：

- 状态变为 `accepted`。
- Demo 阶段不强制自动生成补货申请。
- 如果实现增强接口，可另增 `POST /api/recommendations/{id}/accept-and-create-request`，但不作为最小契约必需项。

### 13.5 拒绝 AI 建议

```http
POST /api/recommendations/{recommendation_id}/reject
```

响应：更新后的 AI 建议对象。

---

## 14. 供应商评分接口

### 14.1 重新计算供应商评分

```http
POST /api/suppliers/recalculate-scores
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "count": 8
  }
}
```

用途：Demo 前重新计算供应商评分。

### 14.2 供应商排行

```http
GET /api/suppliers/ranking
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "supplier_id": 1,
      "score": 92.5,
      "score_source": "price:30, lead_time:25, on_time:25, quality:20"
    }
  ]
}
```

前端展示字段：

| 字段 | 展示名称 |
|---|---|
| `supplier_id` | 供应商 ID |
| `score` | 综合评分 |
| `score_source` | 评分依据 |

### 14.3 某供应商供货商品

```http
GET /api/suppliers/{supplier_id}/products
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "id": 1,
      "supplier_id": 1,
      "product_id": 1,
      "supply_price": "20.00",
      "lead_time_days": 2,
      "on_time_rate": 0.95,
      "quality_score": 98.0,
      "is_preferred": true
    }
  ]
}
```

### 14.4 某供应商评分

```http
GET /api/suppliers/{supplier_id}/score
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "supplier_id": 1,
    "score": 92.5,
    "score_source": "price:30, lead_time:25, on_time:25, quality:20"
  }
}
```

---

## 15. 统计分析接口

### 15.1 商品库存排行

```http
GET /api/analytics/inventory-ranking
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "product_name": "矿泉水",
      "quantity": 1200
    }
  ]
}
```

### 15.2 缺货商品列表

```http
GET /api/analytics/stockout-products
```

响应：库存预警数组，筛选缺货相关项。

### 15.3 积压商品列表

```http
GET /api/analytics/overstock-products
```

响应：库存预警数组，筛选积压项。

### 15.4 门店补货频次统计

```http
GET /api/analytics/store-replenishment-frequency
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "store_name": "门店A",
      "request_count": 12
    }
  ]
}
```

### 15.5 仓库出入库趋势

```http
GET /api/analytics/warehouse-flow-trend
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "year": 2026,
      "month": 6,
      "warehouse_name": "中心仓",
      "warehouse_sales": 1200
    }
  ]
}
```

### 15.6 供应商采购金额排行

```http
GET /api/analytics/supplier-purchase-ranking
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "supplier_name": "供应商S01",
      "total_purchase_amount": 120000.0
    }
  ]
}
```

### 15.7 商品周转分析

```http
GET /api/analytics/product-turnover
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "product_name": "矿泉水",
      "avg_monthly_sales": 850.0
    }
  ]
}
```

### 15.8 门店需求热度

```http
GET /api/analytics/store-demand-heatmap
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "store_name": "门店A",
      "retail_sales": 3200
    }
  ]
}
```

---

## 16. 跨仓调拨接口，可选

该模块不是期末 Demo 的 P0 内容，但如果已有后端接口可展示，可作为加分项。

### 16.1 创建跨仓调拨单

```http
POST /api/inventory/cross-warehouse-transfer
```

请求：

```json
{
  "source_warehouse_id": 1,
  "target_warehouse_id": 2,
  "product_id": 1,
  "quantity": 50,
  "reason": "中心仓向区域仓补货",
  "created_by": 1
}
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "id": 1,
    "transfer_no": "TR202606270001",
    "status": "pending"
  }
}
```

### 16.2 完成跨仓调拨

```http
POST /api/inventory/cross-warehouse-transfer/{transfer_id}/complete
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "id": 1,
    "transfer_no": "TR202606270001",
    "status": "completed"
  }
}
```

### 16.3 跨仓调拨建议

```http
GET /api/inventory/rebalance-suggestions
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": [
    {
      "product_id": 1,
      "source_warehouse_id": 1,
      "target_warehouse_id": 2,
      "suggested_quantity": 50
    }
  ]
}
```

---

## 17. Demo 前端最小页面与接口映射

| 页面区域 | 按钮 / 操作 | 接口 |
|---|---|---|
| 系统状态 | 刷新系统状态 | `GET /api/health`、`GET /api/health/db` |
| 首页看板 | 加载看板 | `GET /api/analytics/dashboard` |
| 库存预警 | 查看预警 | `GET /api/inventory/warnings` |
| 库存查询 | 查看库存列表 | `GET /api/inventory` |
| 采购入库 | 查看入库单 | `GET /api/inbound-orders` |
| 采购入库 | 完成入库 | `POST /api/inbound-orders/{id}/complete` |
| 库存流水 | 查看流水 | `GET /api/transactions` |
| 门店补货 | 查看申请 | `GET /api/replenishment-requests` |
| 门店补货 | 审核通过 | `POST /api/replenishment-requests/{id}/approve?audited_by=1` |
| 门店补货 | 转出库单 | `POST /api/replenishment-requests/{id}/convert-to-outbound?source_warehouse_id=1&handled_by=1` |
| 出库配送 | 查看出库单 | `GET /api/outbound-orders` |
| 出库配送 | 发货 | `POST /api/outbound-orders/{id}/ship` |
| 出库配送 | 签收 | `POST /api/outbound-orders/{id}/sign` |
| AI 补货 | 生成建议 | `POST /api/recommendations/generate` |
| AI 补货 | 查看建议 | `GET /api/recommendations` |
| 供应商 | 查看排行 | `GET /api/suppliers/ranking` |
| 统计分析 | 库存排行 | `GET /api/analytics/inventory-ranking` |
| 统计分析 | 出入库趋势 | `GET /api/analytics/warehouse-flow-trend` |

---

## 18. 一键 Demo 脚本接口顺序

`scripts/demo_flow.py` 应按以下顺序调用：

```text
1. GET  /api/health
2. GET  /api/health/db
3. GET  /api/example/status
4. GET  /api/analytics/dashboard
5. GET  /api/inventory/warnings
6. GET  /api/inbound-orders
7. POST /api/inbound-orders/{first_pending_inbound_id}/complete
8. GET  /api/transactions
9. GET  /api/replenishment-requests
10. POST /api/replenishment-requests/{first_pending_request_id}/approve?audited_by=1
11. POST /api/replenishment-requests/{request_id}/convert-to-outbound?source_warehouse_id=1&handled_by=1
12. POST /api/outbound-orders/{outbound_order_id}/ship
13. POST /api/outbound-orders/{outbound_order_id}/sign
14. GET  /api/inventory/warnings
15. POST /api/recommendations/generate
16. GET  /api/recommendations
17. GET  /api/analytics/dashboard
```

脚本输出格式建议：

```text
[1/17] Health Check: ok
[2/17] Database: sqlite connected
[3/17] Example Data: products=30, stores=10
[4/17] Dashboard: stockout=6, overstock=4
...
```

---

## 19. 错误码与前端提示建议

当前后端可能只返回 `message`，不一定有 `error_code`。如果有时间，建议后端补充以下错误码；如果没时间，前端只显示 `message` 即可。

| 错误场景 | 建议 message | 建议 error_code |
|---|---|---|
| 数据不存在 | `not found` | `NOT_FOUND` |
| 库存不足 | `库存不足，无法出库` | `INSUFFICIENT_STOCK` |
| 状态不允许 | `当前状态不允许执行该操作` | `INVALID_STATUS` |
| 重复操作 | `该单据已处理，不能重复操作` | `DUPLICATE_OPERATION` |
| 参数错误 | `参数错误` | `BAD_REQUEST` |
| 数据库错误 | `数据库操作失败` | `DB_ERROR` |

失败响应增强格式，可选：

```json
{
  "success": false,
  "message": "库存不足，无法出库",
  "data": {
    "error_code": "INSUFFICIENT_STOCK"
  }
}
```

---

## 20. 前后端联调验收标准

### 20.1 P0 验收

- [ ] `GET /api/health` 成功。
- [ ] `GET /api/analytics/dashboard` 成功。
- [ ] `GET /api/inventory/warnings` 成功。
- [ ] `GET /api/inbound-orders` 能找到至少一张 `pending` 入库单。
- [ ] `POST /api/inbound-orders/{id}/complete` 成功。
- [ ] 完成入库后 `GET /api/transactions` 能看到新增流水。
- [ ] `GET /api/replenishment-requests` 能找到至少一张 `pending` 补货申请。
- [ ] `POST /api/replenishment-requests/{id}/approve?audited_by=1` 成功。
- [ ] `POST /api/replenishment-requests/{id}/convert-to-outbound?source_warehouse_id=1&handled_by=1` 成功并返回 `outbound_order_id`。
- [ ] `POST /api/outbound-orders/{id}/ship` 成功。
- [ ] `POST /api/outbound-orders/{id}/sign` 成功。
- [ ] `POST /api/recommendations/generate` 成功。
- [ ] `GET /api/recommendations` 能看到建议。
- [ ] 前端 `/demo` 能完整点击上述流程。

### 20.2 P1 验收

- [ ] `GET /api/health/db` 成功。
- [ ] SQLite 和 OceanBase 至少有一种能完整跑通。
- [ ] `GET /api/suppliers/ranking` 成功。
- [ ] 至少 2 个统计图表能显示。
- [ ] `scripts/demo_flow.py` 能跑完。

---

## 21. 契约冻结规则

### 21.1 可以改的内容

- 文档中的中文说明；
- 前端展示名称；
- 非 P0 接口；
- 示例 JSON 中的具体数值；
- Mock 数据。

### 21.2 不要随意改的内容

- P0 接口路径；
- P0 接口请求方法；
- 通用响应格式 `{success, message, data}`；
- 关键字段名，如 `id`、`status`、`current_quantity`、`request_quantity`、`recommended_quantity`；
- 单据状态枚举。

### 21.3 必须改接口时的流程

```text
1. 在群里说明要改哪个接口、为什么改、影响谁。
2. 修改 docs/api_contract.md。
3. 后端修改接口。
4. 前端修改 api.js 或页面映射。
5. C 更新 demo_flow.py。
6. D 更新文档和 demo_script。
7. 全员拉 main 后重新跑一遍 Demo。
```
