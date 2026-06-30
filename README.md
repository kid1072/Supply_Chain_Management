# Supply_Chain_Management

## Real Walmart Import

后端现在支持从本地 Walmart 数据集导入真实销售额，并同时兼容：

- 标准 `train.csv + features.csv + stores.csv`
- 当前仓库实际提供的 M5 `sales_train_validation.csv + calendar.csv + sell_prices.csv`

导入命令、字段映射、OceanBase/SQLite 验证方式和数据边界见：

- [Walmart 数据接入说明](docs/Walmart数据接入说明.md)

供应链库存协同与智能补货管理系统。这个项目面向数据库课程期末演示，围绕“采购入库 → 库存变更 → 门店补货 → 审核流转 → 出库发货 → 门店签收 → AI 补货建议 → 统计分析”搭建了一条可完整演示的业务闭环。

当前版本采用：

- 后端：FastAPI + SQLAlchemy + Pydantic
- 数据库：OceanBase / MySQL 兼容数据库优先，SQLite 自动兜底
- 前端：Bootstrap CDN + ECharts CDN + 原生 JavaScript
- 接口风格：统一返回 `{success, message, data}`
- 演示入口：`/demo`（会跳转到 `/ui/`）

## 项目演示链路

```text
系统状态检查
  -> 首页看板
  -> 基础数据录入
  -> 库存查询与预警
  -> 采购入库
  -> 库存流水追溯
  -> 门店补货申请
  -> 审核通过 / 拒绝
  -> 转出库单
  -> 出库发货
  -> 门店签收
  -> AI 补货建议
  -> 供应商排行与统计分析
```

## 核心功能

- 基础数据管理：商品、供应商、仓库、门店等基础信息维护。
- 采购与入库：创建采购入库单，完成入库后自动增加库存并生成库存流水。
- 补货与出库：支持门店补货申请、审核、拒绝、转出库单、发货、签收。
- 库存预警：展示低库存、缺货、积压等风险状态。
- AI 补货建议：根据库存与业务数据生成建议数量、风险等级和推荐理由。
- 统计分析：展示库存排行、仓库流转趋势、供应商排行等分析结果。
- 系统状态：查看服务状态、数据库连接情况以及示例数据状态。
- 角色化演示界面：同一套前端可按角色切换可见模块，适合课堂现场演示。

## 角色与可见模块

`/demo` 页面提供轻量级角色登录入口。当前角色保存在浏览器 `localStorage` 中，用于演示不同岗位看到的工作台差异。

| 角色 | 可见模块 |
|---|---|
| 系统管理员 `admin` | 首页看板、基础数据录入、库存查询与预警、采购入库演示、门店补货与出库、库存流水追溯、AI 补货建议、统计分析、供应商排行、系统状态 |
| 采购人员 `purchaser` | 首页看板、库存查询与预警、采购入库演示、供应商排行、系统状态 |
| 仓库人员 `warehouse` | 首页看板、库存查询与预警、采购入库演示、门店补货与出库、库存流水追溯、系统状态 |
| 门店人员 `store` | 首页看板、门店补货与出库、AI 补货建议、系统状态 |
| 业务主管 `manager` | 首页看板、库存查询与预警、门店补货与出库、AI 补货建议、统计分析、供应商排行、系统状态 |

演示页默认登录方式：

- 用户名：任意演示名，默认是 `demo`
- 密码：`demo123`
- 角色：从下拉框中选择

说明：

- 这套角色控制是前端演示级隔离，不是企业级真实认证。
- 当前没有 JWT、数据库权限表、后端强校验 RBAC。
- 如果需要真实权限系统，需要后续在后端继续扩展。

## Repository Structure

```text
Supply_Chain_Management/
├── backend/
│   ├── app/
│   │   ├── api/routers/            # 各业务接口
│   │   ├── core/                   # 配置、数据库连接、统一响应等基础设施
│   │   ├── models/                 # ORM 模型
│   │   ├── schemas/                # Pydantic 模型
│   │   └── services/               # 业务服务层
│   ├── example/                    # 示例业务数据 JSON
│   ├── schema/                     # SQLite schema 与本地数据库文件
│   ├── scripts/                    # 初始化数据库、生成/导入示例数据
│   ├── tests/                      # pytest 测试
│   ├── docs/                       # 后端补充文档
│   ├── .env.example                # 环境变量模板
│   └── requirements.txt            # 后端依赖
├── frontend/
│   ├── index.html                  # 演示页面入口
│   ├── api.js                      # 前端统一请求封装
│   ├── app.js                      # 页面逻辑、权限控制、图表渲染
│   ├── style.css                   # 当前演示页面主样式
│   └── styles.css                  # 历史样式文件（保留）
├── docs/
│   ├── api_contract.md             # 前后端冻结接口契约
│   └── project_workplan.md         # 项目分工与开发计划
├── requirements.txt                # 根目录依赖清单
└── README.md
```

## Quick Start

### 1. 获取项目

如果你已经有项目文件，直接进入根目录即可：

```powershell
cd C:\Users\Nancy\Desktop\大学\大二下\数据库\Supply_Chain_Management
```

### 2. 配置后端环境

进入后端目录：

```powershell
cd backend
```

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

如果你只是想最快跑通本地 demo，推荐把 `backend/.env` 中的 `DATABASE_URL` 改成 SQLite：

```env
DATABASE_URL=sqlite:///./schema/supply_chain.db
```

如果你希望展示 OceanBase / MySQL 兼容数据库，也可以保留或修改为对应连接串。当前系统在首选数据库不可用时，会自动回退到 `SQLITE_FALLBACK_URL`。

### 3. 安装依赖

```powershell
pip install -r requirements.txt
```

### 4. 初始化数据库

```powershell
python scripts/init_db.py --rebuild
```

### 5. 生成并导入示例数据

```powershell
python scripts/generate_example_data.py
python scripts/load_example_data.py
```

### 6. 启动服务

```powershell
uvicorn app.main:app --reload --port 8000
```

### 7. 打开页面

启动后可访问：

- 演示入口：http://127.0.0.1:8000/demo
- 前端页面：http://127.0.0.1:8000/ui/
- Swagger 文档：http://127.0.0.1:8000/docs
- 根路径信息：http://127.0.0.1:8000/
- 数据库健康检查：http://127.0.0.1:8000/api/health/db

## API 约定

本项目前后端协作以 `docs/api_contract.md` 为准，核心约定如下：

- API 前缀：`/api`
- 响应格式统一为 `{success, message, data}`
- 前端请求统一封装在 `frontend/api.js`
- 页面逻辑不散写 `fetch`

成功响应示例：

```json
{
  "success": true,
  "message": "ok",
  "data": {}
}
```

失败响应示例：

```json
{
  "success": false,
  "message": "错误信息",
  "data": null
}
```

## 本地测试

进入后端目录后运行：

```powershell
pytest -q
```

当前仓库已包含的测试覆盖包括：

- 登录接口
- 健康检查
- 示例数据导入
- 入库与库存事务
- 出库库存校验
- AI 补货建议
- 分布式库存核对
- 若干接口修复项

## 演示建议

适合课堂展示的最短路径如下：

1. 运行初始化脚本并导入示例数据
2. 打开 `/demo`
3. 先用系统管理员角色展示全模块
4. 再切换为采购、仓库、门店、业务主管，展示不同导航与按钮权限
5. 重点演示一条完整业务流：
   采购入库 → 库存变化 → 补货申请 → 审核/拒绝 → 转出库单 → 发货 → 签收 → AI 建议 → 统计分析

## 相关文档

- [接口契约](docs/api_contract.md)
- [项目工作计划](docs/project_workplan.md)
- [OceanBase 部署说明](backend/docs/OceanBase部署说明.md)
- [后端结构与运行逻辑说明](backend/docs/后端结构与运行逻辑说明.md)
- [示例数据说明](backend/example/README.md)

## 当前限制说明

- 角色登录目前以课堂演示为目标，主要依赖前端 `localStorage`，不是后端强认证。
- 没有实现完整的 JWT、刷新令牌、后端鉴权中间件、权限数据库表。
- 当前前端以 demo 展示为主，没有引入 React/Vue 等工程化框架。
- SQLite 数据库文件 `backend/schema/supply_chain.db` 属于本地运行产物，可通过脚本重新生成。

如果后续继续扩展，这个项目很适合往“真实登录鉴权”“审批流细化”“数据库部署切换”“一键演示脚本”几个方向继续完善。
