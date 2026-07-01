# Supply_Chain_Management

本项目为供应链库存协同与智能补货管理系统。系统面向中小型连锁企业、校园商超、社区便利店等多仓库、多门店零售场景，以库存管理为核心，对商品从供应商采购进入仓库，再由仓库配送至门店的全过程进行统一建模、记录和分析。

项目通过需求分析和数据库建模，在商品、供应商、仓库、门店、采购订单、入库单、出库单、库存和库存流水等基础实体上，结合项目实际，补充了库存预警、门店补货申请、供应商管理与排行、统计分析、AI API 增强的智能补货建议、OceanBase 主数据库部署、系统状态检查、角色化演示界面和多端共享数据访问等内容。

## Demo演示视频

- [Demo视频](/docs/demo视频.mp4)

## 1. Repository Structure

```text
Supply_Chain_Management/
├── backend/
│   ├── app/
│   │   ├── api/             # API 路由
│   │   ├── core/            # 配置、数据库、响应、异常
│   │   ├── models/          # SQLAlchemy 数据模型
│   │   ├── schemas/         # Pydantic 请求和响应结构
│   │   ├── services/        # 业务逻辑
│   │   └── utils/           # 工具函数
│   ├── docs/                # 后端文档
│   ├── example/             # 示例 JSON 数据
│   ├── schema/              # 数据库 schema 和 SQLite 文件
│   ├── scripts/             # 初始化、导入、重置数据脚本
│   ├── tests/               # 自动化测试
│   ├── .env.example
│   └── requirements.txt
├── frontend/                # 前端演示页面
│   ├── index.html           # 演示页面入口
│   ├── api.js               # 统一请求封装
│   ├── app.js               # 页面逻辑、角色控制、图表渲染
│   ├── style.css            # 当前演示页面主样式
│   └── styles.css           # 历史样式文件，保留
├── docs/                    # 项目文档
└── README.md
```

## 2. 系统安装、运行与使用说明

本节用于完成系统部署、后端启动、前端访问和基础功能使用。按照以下步骤执行后，可以在本地运行完整演示系统。

### 2.1 安装后端环境

进入后端目录：

```bash
cd Supply_Chain_Management/backend
```

创建并激活虚拟环境：

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

macOS / Linux：

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

### 2.2 配置运行环境

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

正式演示建议在 `.env` 中配置 OceanBase 和 AI API：

```env
DATABASE_URL=mysql+pymysql://root:your-password@127.0.0.1:2881/supply_chain?charset=utf8mb4
SQLITE_FALLBACK_URL=sqlite:///./schema/supply_chain.db
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_MODEL=deepseek-chat
```

### 2.3 Docker / OceanBase 环境准备

本项目优先使用 OceanBase 作为主数据库，SQLite 作为应急回退。若只做本地快速演示，可直接使用 SQLite；若需要展示 OceanBase，请按以下步骤准备。

确认 Docker 已启动：

```bash
docker --version
docker ps
```

启动 OceanBase 容器：

```bash
docker run -d --name oceanbase-ce --restart unless-stopped -p 2881:2881 -e MODE=mini -e OB_TENANT_PASSWORD=ObDemo2026 -e OB_DATABASE=supply_chain oceanbase/oceanbase-ce
```

如果容器已经存在但处于停止状态，使用：

```bash
docker start oceanbase-ce
```

在 `backend/.env` 中配置：

```env
DATABASE_URL=mysql+pymysql://root%40test:ObDemo2026@127.0.0.1:2881/supply_chain?charset=utf8mb4
SQLITE_FALLBACK_URL=sqlite:///./schema/supply_chain.db
DATABASE_CONNECT_TIMEOUT_SECONDS=10
```

启动后端后访问以下接口确认实际数据库：

```text
http://127.0.0.1:8000/api/health/db
```

当 `mode` 显示 `oceanbase-primary` 时，表示当前连接 OceanBase；如果显示 `sqlite-fallback`，表示系统正在使用 SQLite 回退数据库。

### 2.4 初始化数据库和示例数据

```bash
python scripts/init_db.py --rebuild
python scripts/generate_example_data.py
python scripts/load_example_data.py
```

### 2.5 启动系统

```bash
uvicorn app.main:app --reload --port 8000
```

### 2.6 访问系统

```text
演示入口：http://127.0.0.1:8000/demo
API 文档：http://127.0.0.1:8000/docs
前端演示：http://127.0.0.1:8000/ui/
健康检查：http://127.0.0.1:8000/api/health
数据库健康检查：http://127.0.0.1:8000/api/health/db
```

说明：`/demo` 是推荐演示入口，会进入带登录页的前端演示；`/ui/` 是前端页面直接入口。


## 3. 使用说明与功能验证

前端演示登录说明：

- 用户名：任意演示名，默认可用 `demo`
- 密码：`demo123`
- 角色：从下拉框选择系统管理员、采购人员、仓库人员、门店人员或业务主管

后端用户登录接口也可用于接口测试：

```text
POST /api/users/login
```

系统启动后，可按以下顺序进行功能验证：

1. 访问 `/api/health` 和 `/api/health/db`，确认后端服务和数据库连接正常。
2. 打开 `/demo`，使用 `demo / demo123` 进入前端演示界面。
3. 在系统状态页确认 API、数据库和数据导入状态。
4. 在首页看板查看商品、供应商、库存、补货建议等统计指标。
5. 完成一张采购入库单，验证仓库库存增加并生成库存流水。
6. 新建门店补货申请，依次验证审核、拒绝、转出库单、发货和签收流程。
7. 生成 AI 补货建议，查看推荐数量、风险等级、推荐理由和采用状态。
8. 打开 `/docs`，测试用户登录、商品新增、库存调整、补货建议采用或拒绝等接口。

## 4. Demo 视频

Demo 视频用于展示系统从启动、登录、看板查看到采购入库、门店补货、出库签收和 AI 补货建议的完整业务流程。

```text
Demo 视频：待补充
```

## 5. 多电脑共享访问

如果希望一台电脑新增或修改数据后，其他电脑也能看到，需要让所有电脑访问同一个后端服务和同一个数据库。

在作为服务器的电脑上启动：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

查询服务器电脑的局域网 IP，例如 `192.168.1.23`。其他电脑访问：

```text
演示入口：http://192.168.1.23:8000/demo
API 文档：http://192.168.1.23:8000/docs
前端演示：http://192.168.1.23:8000/ui/
```

共享访问模式下，所有新增商品、库存调整、补货申请、出库发货等操作都会写入同一份数据库，因此其他电脑刷新页面后可以看到最新记录。

说明：

- `127.0.0.1` 只代表当前电脑。
- 多电脑演示时不能每个人各自运行一套本地后端。
- 推荐使用 OceanBase/MySQL 作为共享数据库；SQLite 仅作为本地开发或应急排查时的回退数据库。

## 6. OceanBase 说明

OceanBase 在本项目中作为主数据库服务，不是网站部署平台。系统通过 SQLAlchemy + PyMySQL 接入 OceanBase 的 MySQL 兼容协议，并通过数据库健康检查接口展示当前运行模式。

本地 Docker 启动示例：

```bash
docker run -p 2881:2881 --name oceanbase-ce -e MODE=mini -d oceanbase/oceanbase-ce
```

`.env` 配置示例：

```env
DATABASE_URL=mysql+pymysql://root:your-password@127.0.0.1:2881/supply_chain?charset=utf8mb4
SQLITE_FALLBACK_URL=sqlite:///./schema/supply_chain.db
```

SQLite 保留为应急回退数据库，用于本地开发、环境排查或主数据库临时不可连接时的保底运行。

## 7. AI API 说明

系统已接入 LLM 路由层，可根据 `backend/.env` 配置选择 DeepSeek、Ollama 或规则模型。AI API 用于对补货建议理由和经营摘要进行文本增强；库存预警、补货数量和风险等级仍由系统规则模型计算，因此 AI 服务不可用时，核心业务流程仍可运行。

### 7.1 配置文件位置

AI 相关配置写在后端目录下的 `.env` 文件中：

```text
Supply_Chain_Management/backend/.env
```

如果还没有 `.env`，先在 `backend` 目录复制模板：

```powershell
cd Supply_Chain_Management/backend
Copy-Item .env.example .env
```

### 7.2 使用 DeepSeek API

在 `backend/.env` 中填写：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
```

其中 `DEEPSEEK_API_KEY` 为 API Key 填写位置。修改 `.env` 后需要重启后端服务：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

### 7.3 使用本地 Ollama

如果使用本地 Ollama，不需要外部 API Key，但需要本机已启动 Ollama 服务并已下载模型。`backend/.env` 示例：

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b
```

### 7.4 不使用外部 AI

如果不配置 DeepSeek API Key，也不使用 Ollama，可以使用规则模型：

```env
LLM_PROVIDER=rule
```

规则模型会返回系统自动生成的补货理由，不调用外部 AI 服务。

### 7.5 检查 AI 配置是否生效

启动后端后访问：

```text
GET http://127.0.0.1:8000/api/llm/status
```

返回结果中重点查看：

- `provider`：当前提供方，例如 `deepseek`、`ollama` 或 `rule`；
- `model`：当前模型名称；
- `available`：是否可用；
- `key_configured`：DeepSeek API Key 是否已配置。

### 7.6 生成 AI 智能补货建议

前端可以在“智能补货建议”模块点击“生成补货建议”。也可以在 Swagger 中调用：

```text
POST http://127.0.0.1:8000/api/recommendations/generate?enhance_with_llm=true
GET http://127.0.0.1:8000/api/recommendations
```

当 `enhance_with_llm=true` 时，系统会先用规则模型计算补货数量、风险等级和基础理由，再尝试调用 AI API 增强推荐理由。如果 AI API 调用失败，系统会保留规则理由并继续返回建议结果。



## 8. 相关文档

- [接口契约](/docs/接口契约.md)
- [OceanBase 简介](/docs/OceanBase简介.md)
- [手动数据操作示例](/docs/手动数据操作示例.md)