# OceanBase 部署说明

## 1. 定位

OceanBase 在本项目中承担主数据库角色，分布式相关日志、调拨和对账能力默认围绕 OceanBase 运行；SQLite 只作为本地保底回退。

## 2. 前置要求

- Docker
- Python 3.11+
- 项目虚拟环境或可用的本地 Python 依赖环境

## 3. 安装依赖

```bash
pip install -r requirements.txt
```

## 4. 启动 OceanBase
```bash
docker run -p 2881:2881 --name oceanbase-ce -e MODE=mini -d oceanbase/oceanbase-ce
```

说明：

- 不同 OceanBase 镜像版本的启动耗时、root 密码、租户、初始化 SQL 和连接方式可能不同。
- 请以容器实际日志与官方镜像说明为准，不要假设所有环境都能一键复现。

## 5. 创建数据库

请在 OceanBase 容器可连接后，按容器日志或官方文档给出的账号信息登录，并创建数据库：

```sql
CREATE DATABASE supply_chain;
```

如果镜像要求先切换租户、设置密码或使用 MySQL 兼容端口，请以实际容器输出为准。

## 6. 配置 `.env`

推荐主库配置：

```env
DATABASE_URL=mysql+pymysql://root:your-password@127.0.0.1:2881/supply_chain?charset=utf8mb4
SQLITE_FALLBACK_URL=sqlite:///./schema/supply_chain.db
```

说明：

- 应用会优先连接 `DATABASE_URL` 指向的 OceanBase。
- 若当前环境未启动 OceanBase，应用会自动回退到 `SQLITE_FALLBACK_URL`。
- 请自行填写真实密码，不要把密码写进仓库。

## 7. 初始化数据库并导入示例数据

```bash
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
```

说明：

- OceanBase 主库可用时，`--rebuild` 会直接在 OceanBase 上执行 `drop_all/create_all`。
- 若 OceanBase 不可用并回退到 SQLite，`--rebuild` 会删除本地 `.db` 文件后重建。
- 当前仓库的 `schema.sql` / `seed.sql` 仍主要用于 SQLite 演示；OceanBase 建表更推荐直接运行 `init_db.py`。

## 8. 启动 FastAPI

```bash
uvicorn app.main:app --reload
```

## 9. 验证数据库连接

应用启动后访问：

```text
GET /api/health
GET /api/health/db
```

`/api/health/db` 会执行轻量 SQL 校验连接，并返回：

- `status`
- `dialect`
- `database_url_masked`
- `preferred_database_url_masked`
- `mode`

其中 `database_url_masked` 会显示当前实际运行的数据库，`preferred_database_url_masked` 会显示首选主库配置，密码都会被隐藏。

## 10. OceanBase 连接失败时的保底方案

如果本机没有 Docker、OceanBase 容器未成功启动，或数据库尚未创建，应用会自动切回 SQLite；也可以显式配置：

```env
DATABASE_URL=sqlite:///./schema/supply_chain.db
SQLITE_FALLBACK_URL=sqlite:///./schema/supply_chain.db
```

然后重新执行：

```bash
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
uvicorn app.main:app --reload
```
