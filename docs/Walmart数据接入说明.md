# Walmart 数据接入说明

## 数据来源文件结构

当前仓库 `backend/data/` 实际检测到的是 M5 Walmart 数据集结构，而不是常见的 `train.csv + features.csv + stores.csv` 周销售结构：

- `sales_train_validation.csv`
- `calendar.csv`
- `sell_prices.csv`
- `sales_train_evaluation.csv`
- `sample_submission.csv`

导入器会优先使用：

- `sales_train_validation.csv`
- `calendar.csv`
- `sell_prices.csv`

如果输入目录或 ZIP 中存在标准 Walmart Weekly Sales 文件：

- `train.csv`
- `features.csv`
- `stores.csv`

导入器也会自动识别并按标准周销售映射处理。

## 实际检测到的表头

### 本地实际 M5 数据

`sales_train_validation.csv`

- `id`
- `item_id`
- `dept_id`
- `cat_id`
- `store_id`
- `state_id`
- `d_1 ... d_1913`

`calendar.csv`

- `date`
- `wm_yr_wk`
- `weekday`
- `wday`
- `month`
- `year`
- `d`
- `event_name_1`
- `event_type_1`
- `event_name_2`
- `event_type_2`
- `snap_CA`
- `snap_TX`
- `snap_WI`

`sell_prices.csv`

- `store_id`
- `item_id`
- `wm_yr_wk`
- `sell_price`

### 标准 Walmart Weekly Sales 兼容表头

导入器同时兼容大小写无关、下划线兼容的常见字段：

- `Store` / `store`
- `Dept` / `department`
- `Date` / `date`
- `Weekly_Sales` / `weekly_sales`
- `IsHoliday` / `is_holiday`

以及 `features.csv` / `stores.csv` 中常见的：

- `Type`
- `Size`
- `Temperature`
- `Fuel_Price`
- `MarkDown1` ~ `MarkDown5`
- `CPI`
- `Unemployment`

## 字段映射表

### 标准周销售结构

| 原始字段 | 写入位置 |
| --- | --- |
| `Store` | `stores.store_code/name` + `walmart_store_profiles.walmart_store_no` |
| `Dept` | `products.product_code/name` + `categories` |
| `Date` | `walmart_weekly_sales_facts.sales_date` |
| `Weekly_Sales` | `walmart_weekly_sales_facts.weekly_sales`，并按月汇总到 `monthly_sales_facts.retail_sales` |
| `IsHoliday` | `walmart_weekly_sales_facts.is_holiday`，并汇总到 `monthly_sales_facts.promo_flag` |
| `Type` / `Size` | `walmart_store_profiles.store_type/store_size` |
| `Temperature` / `Fuel_Price` / `MarkDown1~5` / `CPI` / `Unemployment` | 对应写入 `walmart_weekly_sales_facts` 可空特征列 |

### 本地实际 M5 结构适配

| 实际字段 | 适配方式 |
| --- | --- |
| `store_id` | 作为 Walmart 原始门店编号，映射到 `WM-STORE-CA-1`、`WM-STORE-TX-2` 这类门店编码 |
| `dept_id` | 作为 Walmart 部门编号，映射到 `WM-DEPT-HOBBIES_1`、`WM-DEPT-FOODS_3` 这类部门商品 |
| `cat_id` | 作为原始分类标识，保存在周事实原始字段中 |
| `d_1...d_1913` + `calendar.date` | 还原实际销售日期 |
| `calendar.wm_yr_wk` | 作为周分组键；周事实 `sales_date` 取该周最后一天 |
| `sell_price` | 与日销量相乘，得到销售额；再聚合成周销售额和月销售额 |
| `event_name_1/2`、`event_type_1/2` | 保存在周事实事件字段；任一事件存在时，该周 `is_holiday=true` |
| `snap_CA/TX/WI` | 按州映射到 `snap_flag` |
| `Temperature` / `Fuel_Price` / `MarkDown1~5` / `CPI` / `Unemployment` | M5 本地数据中不存在，因此写入 `NULL` |
| `stores.csv` 中 `Type` / `Size` | M5 本地数据中不存在，因此 `walmart_store_profiles.store_type/store_size` 为空 |

## 数据库表说明

新增表：

- `walmart_store_profiles`
  保存 Walmart 门店原始编号与现有 `stores` 的映射，以及可选的 `Type/Size`。
- `walmart_weekly_sales_facts`
  保存 Walmart 周销售事实、原始门店/部门/分类标识、事件、SNAP 标记以及可用特征。

复用表：

- `stores`
- `categories`
- `products`
- `monthly_sales_facts`

其中 `monthly_sales_facts` 写入规则为：

- `retail_sales = Walmart 销售额`
- `retail_transfers = 0`
- `warehouse_sales = 0`
- `promo_flag = 当月任一周为节假日/事件周`
- `is_example_data = false`

## 导入命令

在 `backend/` 目录执行：

```powershell
python scripts/init_db.py --rebuild
python scripts/import_walmart_data.py --input data --dry-run
python scripts/import_walmart_data.py --input data
python scripts/import_walmart_data.py --input data --replace-walmart
```

也支持 ZIP：

```powershell
python scripts/import_walmart_data.py --input ..\data.zip --dry-run
```

ZIP 会先解压到临时目录，不会污染项目目录。

## 如何验证 OceanBase 是否真的被使用

导入前后调用：

- `GET /api/health/db`
- `GET /api/external-data/walmart/status`

只有当 `GET /api/health/db` 返回：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "mode": "oceanbase-primary",
    "dialect": "mysql"
  }
}
```

才能说明当前运行中的导入结果确实落在 OceanBase / MySQL 方言数据库。

如果接口显示：

- `mode = sqlite-fallback`
- `dialect = sqlite`

则说明导入成功，但当前使用的是 SQLite fallback，而不是 OceanBase。

## 数据边界

Walmart 数据在当前项目中的语义边界非常重要：

- 只表示 Walmart 销售额及可用环境/事件特征。
- 不代表真实采购单、入库单、出库单、库存流水、供应商履约或运输过程。
- `dept_id` 在适配时被映射成“部门商品”，并不等于真实 SKU。
- 本地 M5 数据中的 `item_id` 仅用于计算销售额，不会伪造为现有采购或库存业务对象。
- 页面或分析接口中，`monthly_sales_facts.retail_sales` 对应的是 Walmart 销售额，不是库存数量。

## 如何清空并重新导入 Walmart 数据

仅清空 Walmart 周事实和 Walmart 月度销售事实：

```powershell
python scripts/import_walmart_data.py --input data --replace-walmart
```

这不会删除：

- 现有示例数据
- 采购单 / 入库单 / 出库单
- 补货申请
- 用户
- 仓库
- 库存流水

如果需要彻底重建当前数据库后重新导入：

```powershell
python scripts/init_db.py --rebuild
python scripts/load_example_data.py
python scripts/import_walmart_data.py --input data --replace-walmart
```
