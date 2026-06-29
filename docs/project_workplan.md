## 0. 总原则

### 0.1 本阶段目标

优先做出一条完整、稳定、可演示的业务闭环：

```text
示例数据初始化
→ 首页看板
→ 库存查询与预警
→ 采购入库
→ 仓库库存增加
→ 库存流水生成
→ 门店补货申请
→ 审核补货申请
→ 转出库单
→ 出库发货
→ 仓库库存减少，门店库存增加
→ 门店签收
→ AI 补货建议
→ 统计分析展示
```

### 0.2 本阶段不做什么

为了保证 3 天内能交付，暂时不做：

- 完整登录注册与复杂权限控制；
- 复杂前端工程化框架，如 React/Vue + 路由 + 状态管理；
- 真实大模型 Agent 流程；
- 复杂机器学习预测模型；
- 大规模数据库重构；
- 公网部署、域名、备案、HTTPS；
- 手机端适配；
- WebSocket 实时推送。

### 0.3 代码协作原则

- 接口契约先行：先冻结 `docs/api_contract.md`，再分头开发。
- 文件所有权先行：每个人只改自己负责的目录和文件。
- SQLite 保底，OceanBase 加分。
- 演示优先，功能完整性其次，美观最后。
- 第三天中午后代码冻结，只修 bug，不加新功能。

---

## 1. 简单 To Do List

### P0：必须完成

- [ ] 建立并冻结 `docs/api_contract.md`。
- [ ] 后端可通过 `uvicorn app.main:app --reload` 启动。
- [ ] `python scripts/init_db.py --rebuild` 可以重建数据库。
- [ ] `python scripts/load_example_data.py` 可以导入示例数据。
- [ ] `/docs` 可以打开并看到主要接口。
- [ ] `/demo` 演示页面可以打开。
- [ ] 首页看板能显示商品数、供应商数、仓库数、门店数、库存总量、缺货/积压数量。
- [ ] 库存预警能展示低库存与积压库存。
- [ ] 采购入库流程能完成，并能证明仓库库存增加。
- [ ] 门店补货申请能审核、转出库单、发货、签收。
- [ ] 出库时库存不足会报错，不能扣成负数。
- [ ] 每次入库/出库都会生成库存流水。
- [ ] AI 补货建议能生成，包含建议数量、风险等级、推荐理由。
- [ ] 至少 4 个核心测试能通过。
- [ ] 项目文档、安装说明、使用说明、测试报告完整。
- [ ] 准备 3~5 分钟备用演示视频。

### P1：尽量完成

- [ ] OceanBase Docker 本地部署成功。
- [ ] 后端通过 `DATABASE_URL` 切换 SQLite / OceanBase。
- [ ] `/api/health/db` 能显示当前数据库方言。
- [ ] 前端首页能显示当前数据库类型。
- [ ] 供应商评分与排行展示。
- [ ] ECharts 展示库存排行、出入库趋势、供应商采购排行。
- [ ] `scripts/demo_flow.py` 一键跑完整演示流程。

### P2：有时间再做

- [ ] AI 建议一键采纳并自动生成补货申请。
- [ ] 文档导出 PDF。
- [ ] Docker Compose 一键启动后端 + OceanBase。
- [ ] 更漂亮的 UI。
- [ ] 更完整的角色权限控制。

---

## 2. 团队分工总览

| 成员    | 角色                       | 核心目标                        | 主要文件范围                                                                                                                              |
| ----- | ------------------------ | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| A：郭玥彤 | 后端基础设施 / 数据库 / OceanBase | 保证系统能跑、数据库可切换、OceanBase 可展示 | `app/core/`、`app/api/routers/health.py`、`.env.example`、`requirements.txt`、`Dockerfile`、`docker-compose.yml`、`docs/OceanBase部署说明.md` |
| B：董霈兴 | 前端 Demo / 展示页面           | 做一个老师能点击观看的演示系统             | `frontend/`、必要时少量修改 `app/main.py` 用于挂载静态页面                                                                                          |
| C：覃梦媛 | 业务流程 / 事务 / 测试           | 保证入库、出库、补货、流水、AI 建议流程不翻车    | `app/api/routers/` 中业务接口、`app/services/`、`tests/`、`scripts/demo_flow.py`                                                            |
| D：叶雨茜 | 文档 / PPT / 示例数据 / 演示脚本   | 把项目包装完整，确保提交材料齐全            | `docs/`、`README.md`、`example/`、`scripts/load_example_data.py`、`scripts/reset_demo_data.py`                                          |

---

## 3. 成员 A：后端基础设施、数据库与 OceanBase

### 3.1 可操作范围

允许主要修改：

```text
app/core/config.py
app/core/database.py
app/api/routers/health.py
requirements.txt
.env.example
Dockerfile
docker-compose.yml
docs/OceanBase部署说明.md
```

不建议修改：

```text
app/models/*
app/services/inbound_service.py
app/services/outbound_service.py
frontend/*
docs/项目文档.md
```

如果必须修改模型或业务服务，先在群里说明原因，并等 C 确认。

### 3.2 需要实现的功能

#### 功能 A1：SQLite / OceanBase 数据库连接兼容

目标：通过 `.env` 中的 `DATABASE_URL` 切换数据库。

推荐规则：

```python
is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)
```

注意：

- `check_same_thread=False` 只给 SQLite 用。
- `PRAGMA foreign_keys=ON` 只给 SQLite 用。
- OceanBase/MySQL 不要执行 SQLite 专用 PRAGMA。
- `requirements.txt` 增加 `pymysql`。

#### 功能 A2：数据库健康检查接口

新增或增强：

```text
GET /api/health/db
```

返回示例：

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

OceanBase 连接时返回示例：

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

#### 功能 A3：OceanBase 本地部署说明

文档需要包含：

- Docker 启动 OceanBase；
- 创建数据库；
- 修改 `.env`；
- 初始化表结构；
- 导入示例数据；
- 启动后端；
- 访问 `/api/health/db` 验证；
- 失败时切回 SQLite 的保底方案。

推荐最小命令：

```bash
docker run -p 2881:2881 --name oceanbase-ce -e MODE=mini -d oceanbase/oceanbase-ce
```

如果本机资源不足，可以只在文档中说明 OceanBase 部署流程，并保留 SQLite 现场演示。

### 3.3 Git 操作指南

```bash
git checkout main
git pull origin main
git checkout -b feat/db-oceanbase

# 修改代码
pytest -q
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
uvicorn app.main:app --reload

# 自测 /api/health 和 /api/health/db

git add app/core app/api/routers/health.py requirements.txt .env.example docs/OceanBase部署说明.md Dockerfile docker-compose.yml
git commit -m "feat: support database health check and oceanbase config"
git push origin feat/db-oceanbase
gh pr create --base main --head feat/db-oceanbase --title "feat: support oceanbase database config"
```

### 3.4 Codex Prompt 建议

```text
请修改当前 FastAPI 项目，使数据库连接同时兼容 SQLite 和 MySQL/OceanBase。只允许修改 app/core/database.py、app/core/config.py、app/api/routers/health.py、requirements.txt、.env.example。要求：1）SQLite 时使用 check_same_thread=False，并启用 PRAGMA foreign_keys=ON；2）非 SQLite 时不要传 check_same_thread，不要执行 PRAGMA；3）新增 GET /api/health/db，返回数据库连接状态、SQLAlchemy dialect 名称、脱敏后的 DATABASE_URL；4）保持现有 success_response 响应格式；5）不要修改业务接口和模型。修改后给出运行与测试命令。
```

```text
请为本项目编写 docs/OceanBase部署说明.md。要求面向数据库课程期末项目，说明 OceanBase 是作为数据库服务本地 Docker 部署，不需要上传到网站；包含 Docker 启动、创建数据库、配置 DATABASE_URL、初始化表结构、导入示例数据、启动 FastAPI、验证 /api/health/db、失败回退 SQLite 的步骤。不要夸大已经完成的内容。
```

---

## 4. 成员 B：前端 Demo 与展示页面

### 4.1 可操作范围

允许主要修改：

```text
frontend/index.html
frontend/app.js
frontend/api.js
frontend/style.css
```

必要时可让 A 或合并负责人协助修改：

```text
app/main.py
```

不建议修改：

```text
app/api/routers/*
app/services/*
app/models/*
scripts/*
```

### 4.2 需要实现的功能

推荐技术：

```text
HTML + Bootstrap CDN + ECharts CDN + 原生 fetch API
```

不建议使用 React/Vue，避免构建问题。

#### 页面结构

一个页面即可：

```text
/demo
```

左侧或顶部导航：

```text
1. 首页看板
2. 库存查询与预警
3. 采购入库演示
4. 门店补货与出库演示
5. 库存流水追溯
6. AI 补货建议
7. 统计分析
8. 系统状态
```

#### 前端必须调用的接口

- `GET /api/analytics/dashboard`
- `GET /api/inventory/warnings`
- `GET /api/inbound-orders`
- `POST /api/inbound-orders/{order_id}/complete`
- `GET /api/replenishment-requests`
- `POST /api/replenishment-requests/{request_id}/approve?audited_by=1`
- `POST /api/replenishment-requests/{request_id}/convert-to-outbound?source_warehouse_id=1&handled_by=1`
- `POST /api/outbound-orders/{order_id}/ship`
- `POST /api/outbound-orders/{order_id}/sign`
- `GET /api/transactions`
- `POST /api/recommendations/generate`
- `GET /api/recommendations`
- `GET /api/suppliers/ranking`
- `GET /api/health/db`

#### 前端数据访问规则

统一写在 `frontend/api.js`：

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
```

页面中不要散写 `fetch`。所有请求都通过 `request()`。

### 4.3 Git 操作指南

```bash
git checkout main
git pull origin main
git checkout -b feat/demo-frontend

mkdir -p frontend
# 编写 index.html app.js api.js style.css

# 本地启动后访问 /demo
uvicorn app.main:app --reload

git add frontend app/main.py
git commit -m "feat: add demo frontend page"
git push origin feat/demo-frontend
gh pr create --base main --head feat/demo-frontend --title "feat: add demo frontend"
```

如果需要修改 `app/main.py`，只加静态页面挂载，不改路由导入顺序和业务逻辑。

推荐挂载方式：

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/demo")
def demo_page():
    return FileResponse("frontend/index.html")
```

### 4.4 Codex Prompt 建议

```text
请在 frontend/index.html、frontend/api.js、frontend/app.js、frontend/style.css 中实现一个供应链管理系统演示页面。只允许修改 frontend 目录，不要修改后端。技术使用 Bootstrap CDN、ECharts CDN、原生 JavaScript。页面包含：首页看板、库存预警、采购入库演示、门店补货出库演示、库存流水、AI 补货建议、供应商排行、系统状态。所有请求统一通过 frontend/api.js 的 request() 调用，响应格式为 {success,message,data}。每个按钮要有 loading 状态、错误提示和成功提示。字段以 docs/api_contract.md 为准。
```

```text
请为前端增加 mock 模式：当 USE_MOCK=true 时，首页看板、库存预警、补货申请、入库单、出库单、库存流水、AI 建议都返回可展示的假数据；当 USE_MOCK=false 时调用真实后端。只修改 frontend/api.js，不要改其他文件。
```

---

## 5. 成员 C：业务流程、事务与测试

### 5.1 可操作范围

允许主要修改：

```text
app/api/routers/inbound_orders.py
app/api/routers/outbound_orders.py
app/api/routers/replenishment_requests.py
app/api/routers/inventory.py
app/api/routers/transactions.py
app/api/routers/recommendations.py
app/services/inbound_service.py
app/services/outbound_service.py
app/services/replenishment_service.py
app/services/inventory_service.py
app/services/recommendation_service.py
tests/*
scripts/demo_flow.py
```

不建议修改：

```text
frontend/*
app/core/database.py
app/models/*
docs/项目文档.md
```

如果必须修改表结构，先和 A、D 确认，因为会影响数据库初始化、文档和前端字段。

### 5.2 需要实现的功能

#### 功能 C1：采购入库流程稳定

需要保证：

- 入库单状态从 `pending` 变为 `completed`；
- 仓库库存增加；
- 生成 `StockTransaction`；
- 重复完成同一入库单应报错或不重复增加库存；
- 整个流程在一个事务内完成。

核心接口：

```text
GET  /api/inbound-orders
POST /api/inbound-orders/{order_id}/complete
```

#### 功能 C2：门店补货与出库流程稳定

需要保证：

- 补货申请可创建；
- 申请可审核通过；
- 只有审核通过才能转出库单；
- 出库前检查仓库可用库存；
- 库存不足不能出库；
- 出库成功后仓库库存减少；
- 门店签收后状态变为 `signed`；
- 如果当前业务设计为“发货时即增加门店库存”，需要在文档中写清楚；如果设计为“签收时增加门店库存”，前后端和文档也要统一。

核心接口：

```text
GET  /api/replenishment-requests
POST /api/replenishment-requests/{request_id}/approve?audited_by=1
POST /api/replenishment-requests/{request_id}/convert-to-outbound?source_warehouse_id=1&handled_by=1
POST /api/outbound-orders/{order_id}/ship
POST /api/outbound-orders/{order_id}/sign
```

#### 功能 C3：库存流水与追溯

需要保证：

- 入库生成流水；
- 出库生成流水；
- 能按商品查询流水；
- 能按单据查询流水；
- 前端能拿到可展示字段。

核心接口：

```text
GET /api/transactions
GET /api/transactions/product/{product_id}
GET /api/transactions/doc/{doc_type}/{doc_id}
GET /api/transactions/product/{product_id}/trace
```

#### 功能 C4：AI 补货建议稳定

需要保证：

- `POST /api/recommendations/generate` 能生成建议；
- `GET /api/recommendations` 能列出建议；
- 建议数量不为负数；
- 建议包含风险等级、缺货风险、推荐理由；
- 没有 LLM API 时也能用规则模型生成。

#### 功能 C5：一键 Demo 脚本

新增：

```text
scripts/demo_flow.py
```

脚本目标：自动调用接口并打印关键结果。

推荐流程：

```text
1. 检查 /api/health
2. 检查 /api/example/status
3. 获取 dashboard
4. 获取库存预警
5. 获取第一张 pending 入库单
6. 完成入库
7. 查询库存和流水
8. 获取第一张 pending 补货申请
9. 审核补货申请
10. 转出库单
11. 完成出库
12. 签收
13. 查询库存和流水
14. 生成 AI 补货建议
15. 查询 AI 补货建议
```

### 5.3 测试要求

至少保留或新增以下测试：

```text
tests/test_inbound_complete.py
tests/test_outbound_stock_check.py
tests/test_inventory_transaction.py
tests/test_recommendation.py
```

核心断言：

- 入库完成后仓库库存增加；
- 入库完成后生成流水；
- 出库库存不足时报错；
- 出库成功后仓库库存减少；
- 门店库存变化符合设计；
- AI 补货建议 `recommended_quantity >= 0`；
- AI 补货建议有 `reason`。

### 5.4 Git 操作指南

```bash
git checkout main
git pull origin main
git checkout -b feat/business-flow-tests

# 修改业务代码与测试
pytest -q
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
python scripts/demo_flow.py

git add app/api/routers app/services tests scripts/demo_flow.py
git commit -m "feat: stabilize demo business flow"
git push origin feat/business-flow-tests
gh pr create --base main --head feat/business-flow-tests --title "feat: stabilize inbound outbound recommendation flow"
```

### 5.5 Codex Prompt 建议

```text
请检查并修复供应链项目的入库流程。只允许修改 app/services/inbound_service.py、app/api/routers/inbound_orders.py、tests/test_inbound_complete.py。要求：POST /api/inbound-orders/{order_id}/complete 在一个事务内完成：校验入库单存在且未完成、增加对应仓库库存、生成库存流水、更新入库单状态为 completed、防止重复完成导致重复入库。保持现有 success_response 格式。补充 pytest 测试，验证库存增加和流水生成。
```

```text
请检查并修复门店补货和出库流程。只允许修改 app/services/replenishment_service.py、app/services/outbound_service.py、app/api/routers/replenishment_requests.py、app/api/routers/outbound_orders.py、tests/test_outbound_stock_check.py。要求：只有审核通过的补货申请能转出库单；出库时检查仓库可用库存，不足时抛出 BusinessException；出库成功后扣减仓库库存、增加门店库存或在签收时增加门店库存，但必须保持一致并写入测试；生成库存流水；防止重复 ship 重复扣减库存。
```

```text
请新增 scripts/demo_flow.py，使用 requests 调用本地 http://127.0.0.1:8000 的接口，自动跑通：health、dashboard、库存预警、完成入库、审核补货申请、转出库单、出库、签收、库存流水、生成 AI 补货建议。脚本需要打印每一步的标题和关键字段，失败时给出清晰错误。不要修改后端业务代码。
```

---

## 6. 成员 D：文档、PPT、示例数据与演示脚本

### 6.1 可操作范围

允许主要修改：

```text
docs/项目文档.md
docs/安装使用说明.md
docs/OceanBase部署说明.md
docs/测试报告.md
docs/中期后改进说明.md
docs/demo_script.md
README.md
example/*
scripts/load_example_data.py
scripts/reset_demo_data.py
```

不建议修改：

```text
app/core/*
app/api/routers/*
app/services/*
frontend/*
```

如果示例数据字段与模型不一致，需要先和 C 确认。

### 6.2 需要完成的文档

#### 文档 D1：最终项目文档

文件：

```text
docs/项目文档.md
```

建议目录：

```text
1. 系统概述
2. 系统需求分析
   2.1 业务背景
   2.2 用户角色
   2.3 功能性需求
   2.4 非功能性需求
3. 数据库概念模型设计
   3.1 实体说明
   3.2 实体关系
   3.3 ER 图
4. 数据库逻辑设计
   4.1 表结构
   4.2 主键、外键、唯一约束、检查约束
   4.3 第三范式分析
   4.4 索引设计
5. 功能设计与模块划分
6. 系统实现
   6.1 技术栈
   6.2 后端接口
   6.3 库存事务处理
   6.4 AI 补货规则
   6.5 统计分析与可视化
   6.6 OceanBase 适配
7. 系统安装与使用说明
8. 系统测试
9. 中期汇报后新增与优化
10. 总结与不足
```

#### 文档 D2：安装使用说明

文件：

```text
docs/安装使用说明.md
```

必须包括：

```bash
gh repo clone kid1072/Supply_Chain_Management
cd Supply_Chain_Management
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
uvicorn app.main:app --reload
```

访问地址：

```text
后端文档：http://127.0.0.1:8000/docs
演示页面：http://127.0.0.1:8000/demo
健康检查：http://127.0.0.1:8000/api/health
```

#### 文档 D3：测试报告

文件：

```text
docs/测试报告.md
```

至少列出：

| 测试项 | 操作 | 期望结果 | 实际结果 | 是否通过 |
|---|---|---|---|---|
| 初始化数据 | 执行 load_example_data | 数据导入成功 |  |  |
| 采购入库 | 完成入库单 | 仓库库存增加，生成流水 |  |  |
| 库存不足出库 | 发起超量出库 | 系统报错，库存不变 |  |  |
| 门店补货出库 | 审核、转单、发货 | 仓库减少，门店增加 |  |  |
| AI 补货建议 | 生成建议 | 有建议数量和理由 |  |  |

#### 文档 D4：中期后改进说明

文件：

```text
docs/中期后改进说明.md
```

建议写：

```text
1. 从数据库设计扩展为可运行的 FastAPI 后端系统。
2. 增加演示前端，实现可点击的系统 Demo。
3. 完成采购入库、门店补货、仓库出库、门店签收业务闭环。
4. 增加库存事务控制，保证库存表与库存流水同步更新。
5. 增加库存预警、库存追溯和统计分析接口。
6. 增加规则型 AI 补货建议，输出建议数量、风险等级和推荐理由。
7. 增加示例数据初始化脚本和一键演示流程。
8. 增加 OceanBase 兼容部署方案。
```

#### 文档 D5：Demo 讲解脚本

文件：

```text
docs/demo_script.md
```

需要写清楚：

- 演示前准备命令；
- 每一步点击哪个按钮；
- 应该看到什么结果；
- 如果现场失败，如何切换到备用演示视频。

### 6.3 示例数据要求

示例数据需要保证：

- 至少 5 个商品；
- 至少 3 个供应商；
- 至少 2 个仓库；
- 至少 3 个门店；
- 至少 1 张待完成入库单；
- 至少 1 张待审核补货申请；
- 至少 1 个低库存预警；
- 至少 1 个积压库存预警；
- 至少 10 条库存流水；
- 至少能生成 3 条 AI 补货建议。

### 6.4 Git 操作指南

```bash
git checkout main
git pull origin main
git checkout -b docs/final-deliverables

# 修改 docs、README、example、scripts
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
pytest -q

git add docs README.md example scripts/load_example_data.py scripts/reset_demo_data.py
git commit -m "docs: add final project deliverables"
git push origin docs/final-deliverables
gh pr create --base main --head docs/final-deliverables --title "docs: add final deliverables"
```

### 6.5 Codex Prompt 建议

```text
请根据当前项目代码结构和供应链库存协同项目背景，编写 docs/项目文档.md。要求包含：系统需求分析、数据库概念模型设计、数据库逻辑设计、功能设计、模块划分、系统实现、安装使用说明、测试说明、中期汇报后新增与优化。重点突出采购入库、门店补货出库、库存流水、库存预警、AI 补货建议、OceanBase 适配。不要虚构尚未实现的公网部署或真实大模型训练。
```

```text
请编写 docs/demo_script.md，面向期末现场汇报。要求包含演示前准备命令、演示顺序、每一步点击的页面/按钮、预期展示结果、讲解词、失败应急方案。演示主线为：首页看板 → 库存预警 → 采购入库 → 库存流水 → 门店补货申请 → 审核 → 转出库 → 发货/签收 → AI 补货建议 → 统计分析。
```

---

## 7. 整体 Workflow：按工作顺序执行

### 阶段 1：冻结接口与分支

负责人：全员。

```text
1. 所有人一起阅读 docs/api_contract.md。
2. 确认前端 Demo 只调用契约中的接口。
3. 确认后端只保证契约中的接口稳定。
4. 确认文件所有权。
5. 创建各自分支。
```

命令：

```bash
git checkout main
git pull origin main

git checkout -b feat/db-oceanbase              # A
git checkout -b feat/demo-frontend            # B
git checkout -b feat/business-flow-tests      # C
git checkout -b docs/final-deliverables       # D
```

### 阶段 2：本地基线跑通

负责人：A 主导，全员同步。

```bash
python -m venv .venv
source .venv/bin/activate      # Windows 用 .venv\Scripts\activate
pip install -r requirements.txt
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
pytest -q
uvicorn app.main:app --reload
```

确认：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/api/analytics/dashboard
http://127.0.0.1:8000/api/inventory/warnings
```

### 阶段 3：并行开发

| 成员 | 工作 |
|---|---|
| A | 数据库兼容、`/api/health/db`、OceanBase 文档初稿 |
| B | 前端页面骨架、Mock 数据、Dashboard、Warnings |
| C | 入库、出库、补货、流水、AI 建议流程梳理与测试 |
| D | 文档目录、安装说明、测试报告模板、中期后改进说明 |

合并要求：

```bash
git pull --rebase origin main
pytest -q
```

### 阶段 4：第一轮集成

负责人：合并负责人。

```text
1. 依次合并 A、C、B、D 的 PR。
2. 合并后所有人重新拉 main。
3. 重新初始化数据库。
4. 启动后端。
5. 访问 /demo。
6. 前端从 Mock 切到真实后端。
```

命令：

```bash
git checkout main
git pull origin main
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
pytest -q
uvicorn app.main:app --reload
```

### 阶段 5：核心业务闭环

上午目标：采购入库闭环。

```text
入库单列表 → 完成入库 → 仓库库存增加 → 库存流水生成
```

下午目标：门店补货出库闭环。

```text
补货申请列表 → 审核通过 → 转出库单 → 出库发货 → 门店签收 → 库存变化 → 流水追溯
```

晚上目标：AI 和统计。

```text
生成 AI 补货建议 → 查看推荐理由 → 供应商排行 → 出入库趋势 → 库存排行
```

第二天结束前必须完成一次完整演示。

### 阶段 6：OceanBase 部署

负责人：A，C 配合。

```text
1. Docker 启动 OceanBase。
2. 修改 .env 的 DATABASE_URL。
3. 初始化表结构。
4. 导入示例数据。
5. 启动后端。
6. 访问 /api/health/db。
7. 跑 demo_flow.py。
8. 截图写入 docs/OceanBase部署说明.md。
```

如果 OceanBase 花费超过 2 小时仍不稳定，立即停止，保留 SQLite 演示，把 OceanBase 作为文档加分项。

### 阶段 7：代码冻结与排练

第三天中午前：

```text
1. 最后一轮合并。
2. 所有人拉 main。
3. 全量重装、初始化、跑测试。
4. 修阻断 bug。
```

第三天下午后：

```text
1. 不再加新功能。
2. 完成文档和 PPT。
3. 录制备用 Demo 视频。
4. 排练至少 3 次。
```

---

## 8. Git 协作规范

### 8.1 禁止直接改 main

所有人必须从分支提交 PR。

```bash
git checkout main
git pull origin main
git checkout -b feat/your-feature
```

### 8.2 提交前必须做的事

```bash
git status
git pull --rebase origin main
pytest -q
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
```

如果是前端修改，还需要：

```bash
uvicorn app.main:app --reload
# 浏览器访问 /demo 手动检查
```

### 8.3 Commit Message 规范

```text
feat: 新功能
fix: 修 bug
docs: 文档
test: 测试
chore: 配置、依赖、脚本
refactor: 重构，但三天冲刺期尽量不要用
```

示例：

```bash
git commit -m "feat: add demo dashboard page"
git commit -m "fix: prevent duplicate outbound shipment"
git commit -m "docs: add installation guide"
```

### 8.4 PR 合并顺序建议

```text
1. A 的基础设施 PR
2. C 的业务流程 PR
3. B 的前端 PR
4. D 的文档 PR
```

原因：

- A 的数据库配置影响所有人；
- C 的接口稳定后，B 前端才能接真实接口；
- D 文档最后根据真实实现更新。

### 8.5 避免冲突的具体办法

- 同一时间只允许一个人修改 `app/main.py`。
- `app/models/*` 第一天后冻结。
- `docs/api_contract.md` 一旦冻结，字段名不再随意改。
- 前端所有请求集中在 `frontend/api.js`。
- 后端所有返回统一 `success_response`。
- 改跨组文件前先在群里发：

```text
我要修改 xxx 文件，原因是 xxx，预计影响 xxx，10 分钟内没有异议我再改。
```

---

## 9. Codex 使用规范

### 9.1 每次给 Codex 的通用约束

每个 prompt 开头都加：

```text
你正在修改一个数据库课程期末项目。请只修改我指定的文件，不要重构项目结构，不要修改无关文件，不要删除已有测试，不要改变已冻结接口契约。保持现有 FastAPI + SQLAlchemy 风格，保持 {success,message,data} 响应格式。修改后说明改了什么、如何运行、如何测试。
```

### 9.2 不要让 Codex 做的事

不要让 Codex：

- 一次性“优化整个项目”；
- “重构所有模型”；
- “升级成完整企业级系统”；
- “自动设计全套权限系统”；
- “把前端改成 React/Vue”；
- “删除所有旧文件重新生成”。

### 9.3 推荐让 Codex 做的小任务

适合：

```text
修复某一个接口
补充某一个测试
写某一个页面区域
写某一个文档章节
增加一个健康检查
增加一个前端错误提示
```

不适合：

```text
请完成整个项目
请自动部署所有内容
请重构数据库和后端
```

---

## 10. OceanBase 注意事项

### 10.1 OceanBase 是数据库，不是网站部署平台

OceanBase 在本项目中只承担数据库角色。你们不需要把项目上传到 OceanBase 网站才能使用。正确理解是：

```text
FastAPI 后端 → SQLAlchemy → PyMySQL → OceanBase 数据库服务
```

不是：

```text
把整个项目上传到 OceanBase 平台
```

### 10.2 推荐方案

推荐本地 Docker：

```bash
docker run -p 2881:2881 --name oceanbase-ce -e MODE=mini -d oceanbase/oceanbase-ce
```

然后 `.env`：

```env
DATABASE_URL=mysql+pymysql://root:@127.0.0.1:2881/supply_chain?charset=utf8mb4
```

如果 root 密码或租户连接方式与本机环境不同，以本机实际连接测试为准。

### 10.3 OceanBase 只作为加分项

现场演示策略：

```text
1. 主演示使用 SQLite，确保不翻车。
2. OceanBase 用截图、文档、/api/health/db 展示兼容能力。
3. 如果 OceanBase 当场可用，再切换 DATABASE_URL 演示。
4. 如果 OceanBase 当场不可用，不影响主系统演示。
```

---

## 11. 最终交付物检查清单

```text
代码文件
├── app/
├── frontend/
├── scripts/
├── tests/
├── schema/
├── example/
├── requirements.txt
├── .env.example
├── README.md
└── docker-compose.yml / Dockerfile

文档文件
├── docs/api_contract.md
├── docs/项目文档.md
├── docs/安装使用说明.md
├── docs/OceanBase部署说明.md
├── docs/测试报告.md
├── docs/中期后改进说明.md
└── docs/demo_script.md

汇报材料
├── 期末汇报 PPT
├── 备用演示视频
└── 演示截图
```

---

## 12. 最后排练清单

每次排练前执行：

```bash
git checkout main
git pull origin main
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
pytest -q
uvicorn app.main:app --reload
```

浏览器打开：

```text
http://127.0.0.1:8000/demo
```

按照顺序演示：

```text
1. 首页看板
2. 数据库状态
3. 库存预警
4. 完成入库
5. 查看库存流水
6. 审核补货申请
7. 转出库单
8. 出库发货
9. 门店签收
10. 查看库存变化
11. 生成 AI 补货建议
12. 查看统计分析
```

排练通过标准：

- 全流程 8 分钟内讲完；
- 不依赖现场网络；
- 出错时知道如何恢复；
- 每个人都知道自己讲哪一部分；
- 备用视频能正常播放。
