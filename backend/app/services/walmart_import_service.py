from __future__ import annotations

import csv
import tempfile
import zipfile
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.cache import invalidate_business_cache
from app.core.database import get_database_runtime_profile
from app.models.analytics import MonthlySalesFact
from app.models.product import Category, Product
from app.models.store import Store
from app.models.walmart import WalmartStoreProfile, WalmartWeeklySalesFact


DECIMAL_ZERO = Decimal("0")
MONEY_QUANT = Decimal("0.01")
PRICE_QUANT = Decimal("0.0001")
WALMART_PARENT_CATEGORY_NAME = "Walmart Department"
WALMART_PRODUCT_CODE_PREFIX = "WM-DEPT-"
WALMART_STORE_CODE_PREFIX = "WM-STORE-"
STANDARD_WEEKLY_DATASET = "standard_weekly_sales"
M5_DATASET = "m5_daily_sales"


@dataclass
class DatasetInspection:
    dataset_kind: str
    files: dict[str, Path]
    detected_files: list[str]
    file_headers: dict[str, list[str]]
    file_samples: dict[str, list[dict[str, str]]]


@dataclass
class WeeklyFactPayload:
    raw_store_code: str
    raw_department_code: str
    raw_category_code: str | None
    state_code: str | None
    sales_date: date
    weekly_sales: Decimal
    is_holiday: bool
    temperature: Decimal | None = None
    fuel_price: Decimal | None = None
    markdown1: Decimal | None = None
    markdown2: Decimal | None = None
    markdown3: Decimal | None = None
    markdown4: Decimal | None = None
    markdown5: Decimal | None = None
    cpi: Decimal | None = None
    unemployment: Decimal | None = None
    raw_week_key: str | None = None
    weekly_units: Decimal | None = None
    avg_sell_price: Decimal | None = None
    event_name_1: str | None = None
    event_type_1: str | None = None
    event_name_2: str | None = None
    event_type_2: str | None = None
    snap_flag: bool | None = None
    source_row_key: str = ""


@dataclass
class MonthlyFactPayload:
    year: int
    month: int
    raw_store_code: str
    raw_department_code: str
    raw_category_code: str | None
    retail_sales: Decimal
    promo_flag: bool


@dataclass
class PreparedWalmartImport:
    dataset_kind: str
    stores: dict[str, dict[str, Any]] = field(default_factory=dict)
    departments: dict[str, dict[str, Any]] = field(default_factory=dict)
    weekly_facts: list[WeeklyFactPayload] = field(default_factory=list)
    monthly_facts: list[MonthlyFactPayload] = field(default_factory=list)
    raw_weekly_sales_count: int = 0
    skipped_row_count: int = 0
    unparsed_row_count: int = 0
    feature_missing_count: int = 0
    min_sales_date: date | None = None
    max_sales_date: date | None = None


@dataclass
class WalmartImportSummary:
    dataset_kind: str
    dry_run: bool
    detected_files: list[str]
    file_headers: dict[str, list[str]]
    raw_weekly_sales_count: int
    imported_row_count: int
    skipped_row_count: int
    unparsed_row_count: int
    feature_missing_count: int
    store_count: int
    department_product_count: int
    monthly_sales_fact_count: int
    min_sales_date: date | None
    max_sales_date: date | None
    database_runtime: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_kind": self.dataset_kind,
            "dry_run": self.dry_run,
            "detected_files": self.detected_files,
            "file_headers": self.file_headers,
            "raw_weekly_sales_count": self.raw_weekly_sales_count,
            "imported_row_count": self.imported_row_count,
            "skipped_row_count": self.skipped_row_count,
            "unparsed_row_count": self.unparsed_row_count,
            "feature_missing_count": self.feature_missing_count,
            "store_count": self.store_count,
            "department_product_count": self.department_product_count,
            "monthly_sales_fact_count": self.monthly_sales_fact_count,
            "min_sales_date": self.min_sales_date.isoformat() if self.min_sales_date else None,
            "max_sales_date": self.max_sales_date.isoformat() if self.max_sales_date else None,
            "database_runtime": self.database_runtime,
        }


@dataclass
class StandardFieldMap:
    store: str
    department: str
    sales_date: str
    weekly_sales: str
    is_holiday: str | None = None
    temperature: str | None = None
    fuel_price: str | None = None
    markdown1: str | None = None
    markdown2: str | None = None
    markdown3: str | None = None
    markdown4: str | None = None
    markdown5: str | None = None
    cpi: str | None = None
    unemployment: str | None = None
    store_type: str | None = None
    store_size: str | None = None


@dataclass
class M5DayMeta:
    sales_date: date
    year: int
    month: int
    wm_yr_wk: str
    event_name_1: str | None
    event_type_1: str | None
    event_name_2: str | None
    event_type_2: str | None
    snap_flags: dict[str, bool]


@dataclass
class M5WeekStateMeta:
    sales_date: date
    is_holiday: bool = False
    snap_flag: bool = False
    event_name_1: str | None = None
    event_type_1: str | None = None
    event_name_2: str | None = None
    event_type_2: str | None = None


def normalize_header(value: str) -> str:
    return "".join(ch for ch in value.strip().lower() if ch.isalnum())


def _sanitize_token(value: str, *, separator: str = "_") -> str:
    chars: list[str] = []
    for ch in value.strip().upper():
        if ch.isalnum():
            chars.append(ch)
        elif ch in {"-", "_", " "}:
            chars.append(separator)
    sanitized = "".join(chars).strip(separator)
    return sanitized or "UNKNOWN"


def _to_decimal(value: str | None, *, quant: Decimal | None = None) -> Decimal | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        decimal_value = Decimal(text)
    except InvalidOperation:
        return None
    return decimal_value.quantize(quant, rounding=ROUND_HALF_UP) if quant else decimal_value


def _to_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "t", "yes", "y"}


def _chunked(items: list[Any], chunk_size: int = 500) -> Iterator[list[Any]]:
    for index in range(0, len(items), chunk_size):
        yield items[index:index + chunk_size]


def _read_csv_preview(csv_path: Path, sample_size: int = 2) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        samples: list[dict[str, str]] = []
        for index, row in enumerate(reader):
            samples.append({key: (value or "") for key, value in row.items()})
            if index + 1 >= sample_size:
                break
    return headers, samples


def _collect_csv_files(root: Path) -> dict[str, Path]:
    return {path.name.lower(): path for path in root.rglob("*.csv")}


@contextmanager
def open_walmart_dataset(input_path: str | Path) -> Iterator[DatasetInspection]:
    source = Path(input_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Input path not found: {source}")

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        if source.is_file() and source.suffix.lower() == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="walmart_import_")
            with zipfile.ZipFile(source) as archive:
                archive.extractall(temp_dir.name)
            working_root = Path(temp_dir.name)
        elif source.is_dir():
            working_root = source
        else:
            raise ValueError("Only zip archives and directories are supported by --input")

        files = _collect_csv_files(working_root)
        standard_required = {"train.csv", "features.csv", "stores.csv"}
        if standard_required.issubset(files):
            logical_files = {
                "train": files["train.csv"],
                "features": files["features.csv"],
                "stores": files["stores.csv"],
            }
            dataset_kind = STANDARD_WEEKLY_DATASET
        elif "calendar.csv" in files and "sell_prices.csv" in files and (
            "sales_train_validation.csv" in files or "sales_train_evaluation.csv" in files
        ):
            sales_name = "sales_train_validation.csv" if "sales_train_validation.csv" in files else "sales_train_evaluation.csv"
            logical_files = {
                "sales": files[sales_name],
                "calendar": files["calendar.csv"],
                "sell_prices": files["sell_prices.csv"],
            }
            dataset_kind = M5_DATASET
        else:
            detected = ", ".join(sorted(files))
            raise ValueError(f"Unsupported Walmart dataset layout. Detected CSV files: {detected}")

        file_headers: dict[str, list[str]] = {}
        file_samples: dict[str, list[dict[str, str]]] = {}
        detected_files: list[str] = []
        for logical_name, csv_path in logical_files.items():
            headers, samples = _read_csv_preview(csv_path)
            file_headers[logical_name] = headers
            file_samples[logical_name] = samples
            detected_files.append(str(csv_path.relative_to(working_root)))

        yield DatasetInspection(
            dataset_kind=dataset_kind,
            files=logical_files,
            detected_files=sorted(detected_files),
            file_headers=file_headers,
            file_samples=file_samples,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def describe_dataset(inspection: DatasetInspection) -> dict[str, Any]:
    return {
        "dataset_kind": inspection.dataset_kind,
        "detected_files": inspection.detected_files,
        "file_headers": inspection.file_headers,
        "file_samples": inspection.file_samples,
    }


def _resolve_field(fieldnames: list[str], candidates: list[str]) -> str | None:
    normalized = {normalize_header(name): name for name in fieldnames}
    for candidate in candidates:
        resolved = normalized.get(normalize_header(candidate))
        if resolved:
            return resolved
    return None


def _require_field(fieldnames: list[str], candidates: list[str], logical_name: str) -> str:
    resolved = _resolve_field(fieldnames, candidates)
    if not resolved:
        raise ValueError(f"Unable to resolve required field '{logical_name}' from headers: {fieldnames}")
    return resolved


def _build_standard_field_map(inspection: DatasetInspection) -> StandardFieldMap:
    train_headers = inspection.file_headers["train"]
    features_headers = inspection.file_headers["features"]
    stores_headers = inspection.file_headers["stores"]
    return StandardFieldMap(
        store=_require_field(train_headers, ["Store", "store"], "Store"),
        department=_require_field(train_headers, ["Dept", "Department", "department"], "Dept"),
        sales_date=_require_field(train_headers, ["Date", "date"], "Date"),
        weekly_sales=_require_field(train_headers, ["Weekly_Sales", "weekly_sales", "sales"], "Weekly_Sales"),
        is_holiday=_resolve_field(train_headers, ["IsHoliday", "is_holiday"]) or _resolve_field(features_headers, ["IsHoliday", "is_holiday"]),
        temperature=_resolve_field(features_headers, ["Temperature", "temperature"]),
        fuel_price=_resolve_field(features_headers, ["Fuel_Price", "fuel_price"]),
        markdown1=_resolve_field(features_headers, ["MarkDown1", "markdown1"]),
        markdown2=_resolve_field(features_headers, ["MarkDown2", "markdown2"]),
        markdown3=_resolve_field(features_headers, ["MarkDown3", "markdown3"]),
        markdown4=_resolve_field(features_headers, ["MarkDown4", "markdown4"]),
        markdown5=_resolve_field(features_headers, ["MarkDown5", "markdown5"]),
        cpi=_resolve_field(features_headers, ["CPI", "cpi"]),
        unemployment=_resolve_field(features_headers, ["Unemployment", "unemployment"]),
        store_type=_resolve_field(stores_headers, ["Type", "type"]),
        store_size=_resolve_field(stores_headers, ["Size", "size"]),
    )


def _update_date_bounds(prepared: PreparedWalmartImport, sales_date: date) -> None:
    prepared.min_sales_date = sales_date if prepared.min_sales_date is None else min(prepared.min_sales_date, sales_date)
    prepared.max_sales_date = sales_date if prepared.max_sales_date is None else max(prepared.max_sales_date, sales_date)


def _prepare_standard_weekly_dataset(inspection: DatasetInspection) -> PreparedWalmartImport:
    field_map = _build_standard_field_map(inspection)
    prepared = PreparedWalmartImport(dataset_kind=STANDARD_WEEKLY_DATASET)
    features_index: dict[tuple[str, str], dict[str, str]] = {}
    store_metadata: dict[str, dict[str, Any]] = {}

    with inspection.files["stores"].open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        store_field = _require_field(list(reader.fieldnames or []), ["Store", "store"], "Store")
        for row in reader:
            raw_store = (row.get(store_field) or "").strip()
            if not raw_store:
                continue
            store_metadata[raw_store] = {
                "store_type": row.get(field_map.store_type) if field_map.store_type else None,
                "store_size": _to_decimal(row.get(field_map.store_size), quant=MONEY_QUANT) if field_map.store_size else None,
                "state_code": None,
            }

    with inspection.files["features"].open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        feature_store_field = _require_field(list(reader.fieldnames or []), ["Store", "store"], "Store")
        feature_date_field = _require_field(list(reader.fieldnames or []), ["Date", "date"], "Date")
        for row in reader:
            raw_store = (row.get(feature_store_field) or "").strip()
            raw_date = (row.get(feature_date_field) or "").strip()
            if raw_store and raw_date:
                features_index[(raw_store, raw_date)] = row

    monthly_index: dict[tuple[int, int, str, str], MonthlyFactPayload] = {}
    with inspection.files["train"].open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw_store = (row.get(field_map.store) or "").strip()
            raw_department = (row.get(field_map.department) or "").strip()
            raw_date = (row.get(field_map.sales_date) or "").strip()
            raw_sales = row.get(field_map.weekly_sales)
            if not raw_store or not raw_department or not raw_date or raw_sales is None:
                prepared.unparsed_row_count += 1
                continue
            try:
                sales_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                prepared.unparsed_row_count += 1
                continue
            weekly_sales = _to_decimal(raw_sales, quant=MONEY_QUANT)
            if weekly_sales is None:
                prepared.unparsed_row_count += 1
                continue

            feature_row = features_index.get((raw_store, raw_date))
            if feature_row is None:
                prepared.feature_missing_count += 1
                feature_row = {}

            is_holiday = _to_bool(row.get(field_map.is_holiday)) if field_map.is_holiday and field_map.is_holiday in row else _to_bool(feature_row.get(field_map.is_holiday)) if field_map.is_holiday else False
            payload = WeeklyFactPayload(
                raw_store_code=raw_store,
                raw_department_code=raw_department,
                raw_category_code=None,
                state_code=None,
                sales_date=sales_date,
                weekly_sales=weekly_sales,
                is_holiday=is_holiday,
                temperature=_to_decimal(feature_row.get(field_map.temperature), quant=MONEY_QUANT) if field_map.temperature else None,
                fuel_price=_to_decimal(feature_row.get(field_map.fuel_price), quant=PRICE_QUANT) if field_map.fuel_price else None,
                markdown1=_to_decimal(feature_row.get(field_map.markdown1), quant=MONEY_QUANT) if field_map.markdown1 else None,
                markdown2=_to_decimal(feature_row.get(field_map.markdown2), quant=MONEY_QUANT) if field_map.markdown2 else None,
                markdown3=_to_decimal(feature_row.get(field_map.markdown3), quant=MONEY_QUANT) if field_map.markdown3 else None,
                markdown4=_to_decimal(feature_row.get(field_map.markdown4), quant=MONEY_QUANT) if field_map.markdown4 else None,
                markdown5=_to_decimal(feature_row.get(field_map.markdown5), quant=MONEY_QUANT) if field_map.markdown5 else None,
                cpi=_to_decimal(feature_row.get(field_map.cpi), quant=PRICE_QUANT) if field_map.cpi else None,
                unemployment=_to_decimal(feature_row.get(field_map.unemployment), quant=PRICE_QUANT) if field_map.unemployment else None,
                source_row_key=f"weekly|standard|{raw_store}|{raw_department}|{sales_date.isoformat()}",
            )
            prepared.weekly_facts.append(payload)
            prepared.raw_weekly_sales_count += 1
            _update_date_bounds(prepared, sales_date)

            prepared.stores.setdefault(raw_store, store_metadata.get(raw_store, {"store_type": None, "store_size": None, "state_code": None}))
            prepared.departments.setdefault(raw_department, {"raw_category_code": None})

            month_key = (sales_date.year, sales_date.month, raw_store, raw_department)
            monthly = monthly_index.get(month_key)
            if not monthly:
                monthly = MonthlyFactPayload(
                    year=sales_date.year,
                    month=sales_date.month,
                    raw_store_code=raw_store,
                    raw_department_code=raw_department,
                    raw_category_code=None,
                    retail_sales=DECIMAL_ZERO,
                    promo_flag=False,
                )
                monthly_index[month_key] = monthly
            monthly.retail_sales = (monthly.retail_sales + weekly_sales).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            monthly.promo_flag = monthly.promo_flag or is_holiday

    prepared.monthly_facts = list(monthly_index.values())
    return prepared


def _build_m5_calendar_maps(calendar_path: Path) -> tuple[dict[str, M5DayMeta], dict[tuple[str, str], M5WeekStateMeta]]:
    day_map: dict[str, M5DayMeta] = {}
    week_state_map: dict[tuple[str, str], M5WeekStateMeta] = {}
    with calendar_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sales_date = datetime.strptime((row.get("date") or "").strip(), "%Y-%m-%d").date()
            day_code = (row.get("d") or "").strip()
            week_key = (row.get("wm_yr_wk") or "").strip()
            event_name_1 = (row.get("event_name_1") or "").strip() or None
            event_type_1 = (row.get("event_type_1") or "").strip() or None
            event_name_2 = (row.get("event_name_2") or "").strip() or None
            event_type_2 = (row.get("event_type_2") or "").strip() or None
            snap_flags = {
                "CA": _to_bool(row.get("snap_CA")),
                "TX": _to_bool(row.get("snap_TX")),
                "WI": _to_bool(row.get("snap_WI")),
            }
            day_map[day_code] = M5DayMeta(
                sales_date=sales_date,
                year=int(row["year"]),
                month=int(row["month"]),
                wm_yr_wk=week_key,
                event_name_1=event_name_1,
                event_type_1=event_type_1,
                event_name_2=event_name_2,
                event_type_2=event_type_2,
                snap_flags=snap_flags,
            )
            for state_code, snap_flag in snap_flags.items():
                meta = week_state_map.setdefault((week_key, state_code), M5WeekStateMeta(sales_date=sales_date))
                if sales_date > meta.sales_date:
                    meta.sales_date = sales_date
                meta.is_holiday = meta.is_holiday or bool(event_name_1 or event_name_2)
                meta.snap_flag = meta.snap_flag or snap_flag
                if event_name_1 and not meta.event_name_1:
                    meta.event_name_1 = event_name_1
                if event_type_1 and not meta.event_type_1:
                    meta.event_type_1 = event_type_1
                if event_name_2 and not meta.event_name_2:
                    meta.event_name_2 = event_name_2
                if event_type_2 and not meta.event_type_2:
                    meta.event_type_2 = event_type_2
    return day_map, week_state_map


def _split_sell_prices_by_store(sell_prices_path: Path) -> dict[str, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix="walmart_prices_"))
    file_handles: dict[str, Any] = {}
    writers: dict[str, csv.writer] = {}
    created_files: dict[str, Path] = {}
    try:
        with sell_prices_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            headers = next(reader)
            for row in reader:
                store_code = row[0]
                if store_code not in writers:
                    store_file = temp_root / f"{_sanitize_token(store_code)}.csv"
                    file_handle = store_file.open("w", encoding="utf-8", newline="")
                    writer = csv.writer(file_handle)
                    writer.writerow(headers)
                    file_handles[store_code] = file_handle
                    writers[store_code] = writer
                    created_files[store_code] = store_file
                writers[store_code].writerow(row)
    finally:
        for handle in file_handles.values():
            handle.close()
    return created_files


def _load_store_price_map(price_file: Path) -> dict[tuple[str, str], Decimal]:
    price_map: dict[tuple[str, str], Decimal] = {}
    with price_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for row in reader:
            price = _to_decimal(row[3], quant=PRICE_QUANT)
            if price is not None:
                price_map[(row[1], row[2])] = price
    return price_map


def _prepare_m5_dataset(inspection: DatasetInspection) -> PreparedWalmartImport:
    prepared = PreparedWalmartImport(dataset_kind=M5_DATASET)
    day_map, week_state_map = _build_m5_calendar_maps(inspection.files["calendar"])
    price_files = _split_sell_prices_by_store(inspection.files["sell_prices"])
    weekly_index: dict[tuple[str, str, date], WeeklyFactPayload] = {}
    monthly_index: dict[tuple[int, int, str, str], MonthlyFactPayload] = {}

    try:
        with inspection.files["sales"].open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            headers = next(reader)
            day_columns = headers[6:]
            day_metas = [day_map.get(column) for column in day_columns]
            current_store: str | None = None
            current_price_map: dict[tuple[str, str], Decimal] = {}

            for row in reader:
                if len(row) < 7:
                    prepared.unparsed_row_count += 1
                    continue
                item_id = row[1].strip()
                dept_id = row[2].strip()
                cat_id = row[3].strip()
                store_id = row[4].strip()
                state_id = row[5].strip()
                if not item_id or not dept_id or not store_id:
                    prepared.unparsed_row_count += 1
                    continue

                if store_id != current_store:
                    current_store = store_id
                    price_file = price_files.get(store_id)
                    current_price_map = _load_store_price_map(price_file) if price_file else {}

                prepared.stores.setdefault(store_id, {"store_type": None, "store_size": None, "state_code": state_id})
                prepared.departments.setdefault(dept_id, {"raw_category_code": cat_id or None})

                for day_meta, raw_qty in zip(day_metas, row[6:]):
                    if day_meta is None:
                        prepared.feature_missing_count += 1
                        continue
                    qty_text = raw_qty.strip()
                    if not qty_text or qty_text == "0":
                        continue
                    qty = _to_decimal(qty_text)
                    if qty is None:
                        prepared.unparsed_row_count += 1
                        continue
                    price = current_price_map.get((item_id, day_meta.wm_yr_wk))
                    if price is None:
                        prepared.feature_missing_count += 1
                        continue
                    amount = (qty * price).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
                    week_meta = week_state_map[(day_meta.wm_yr_wk, state_id)]
                    weekly_key = (store_id, dept_id, week_meta.sales_date)
                    weekly = weekly_index.get(weekly_key)
                    if not weekly:
                        weekly = WeeklyFactPayload(
                            raw_store_code=store_id,
                            raw_department_code=dept_id,
                            raw_category_code=cat_id or None,
                            state_code=state_id or None,
                            sales_date=week_meta.sales_date,
                            weekly_sales=DECIMAL_ZERO,
                            is_holiday=week_meta.is_holiday,
                            raw_week_key=day_meta.wm_yr_wk,
                            weekly_units=DECIMAL_ZERO,
                            avg_sell_price=None,
                            event_name_1=week_meta.event_name_1,
                            event_type_1=week_meta.event_type_1,
                            event_name_2=week_meta.event_name_2,
                            event_type_2=week_meta.event_type_2,
                            snap_flag=week_meta.snap_flag,
                            source_row_key=f"weekly|m5|{store_id}|{dept_id}|{week_meta.sales_date.isoformat()}",
                        )
                        weekly_index[weekly_key] = weekly
                    weekly.weekly_sales = (weekly.weekly_sales + amount).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
                    weekly.weekly_units = ((weekly.weekly_units or DECIMAL_ZERO) + qty).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

                    month_key = (day_meta.year, day_meta.month, store_id, dept_id)
                    monthly = monthly_index.get(month_key)
                    if not monthly:
                        monthly = MonthlyFactPayload(
                            year=day_meta.year,
                            month=day_meta.month,
                            raw_store_code=store_id,
                            raw_department_code=dept_id,
                            raw_category_code=cat_id or None,
                            retail_sales=DECIMAL_ZERO,
                            promo_flag=False,
                        )
                        monthly_index[month_key] = monthly
                    monthly.retail_sales = (monthly.retail_sales + amount).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
                    monthly.promo_flag = monthly.promo_flag or week_meta.is_holiday
                    _update_date_bounds(prepared, day_meta.sales_date)

        for weekly in weekly_index.values():
            if weekly.weekly_units and weekly.weekly_units != DECIMAL_ZERO:
                weekly.avg_sell_price = (weekly.weekly_sales / weekly.weekly_units).quantize(PRICE_QUANT, rounding=ROUND_HALF_UP)
        prepared.weekly_facts = list(weekly_index.values())
        prepared.monthly_facts = list(monthly_index.values())
        prepared.raw_weekly_sales_count = len(prepared.weekly_facts)
        return prepared
    finally:
        for price_file in price_files.values():
            if price_file.exists():
                price_file.unlink()
        if price_files:
            next(iter(price_files.values())).parent.rmdir()


def prepare_walmart_import(inspection: DatasetInspection) -> PreparedWalmartImport:
    if inspection.dataset_kind == STANDARD_WEEKLY_DATASET:
        return _prepare_standard_weekly_dataset(inspection)
    if inspection.dataset_kind == M5_DATASET:
        return _prepare_m5_dataset(inspection)
    raise ValueError(f"Unsupported dataset kind: {inspection.dataset_kind}")


def _build_store_code(raw_store_code: str, width: int) -> str:
    if raw_store_code.isdigit():
        return f"{WALMART_STORE_CODE_PREFIX}{int(raw_store_code):0{width}d}"
    return f"{WALMART_STORE_CODE_PREFIX}{_sanitize_token(raw_store_code, separator='-')}"


def _build_store_name(raw_store_code: str, width: int) -> str:
    if raw_store_code.isdigit():
        return f"Walmart Store {int(raw_store_code):0{width}d}"
    return f"Walmart Store {raw_store_code}"


def _build_department_token(raw_department_code: str) -> str:
    if raw_department_code.isdigit():
        return f"{int(raw_department_code):03d}"
    return _sanitize_token(raw_department_code)


def _build_department_label(raw_department_code: str) -> str:
    if raw_department_code.isdigit():
        return f"{int(raw_department_code):03d}"
    return raw_department_code


def _ensure_walmart_master_data(
    db: Session,
    stores: dict[str, dict[str, Any]],
    departments: dict[str, dict[str, Any]],
) -> tuple[dict[str, Store], dict[str, Product], dict[str, Category]]:
    numeric_store_width = max(max((len(str(int(code))) for code in stores if code.isdigit()), default=0), 3)
    walmart_parent = db.execute(
        select(Category).where(Category.name == WALMART_PARENT_CATEGORY_NAME, Category.parent_id.is_(None))
    ).scalar_one_or_none()
    if not walmart_parent:
        walmart_parent = Category(name=WALMART_PARENT_CATEGORY_NAME, parent_id=None, description="Walmart department hierarchy", is_active=True)
        db.add(walmart_parent)
        db.flush()

    store_codes = {_build_store_code(raw_store, numeric_store_width): raw_store for raw_store in stores}
    existing_stores = {
        item.store_code: item
        for item in db.execute(select(Store).where(Store.store_code.in_(list(store_codes)))).scalars()
    }
    existing_profiles = {
        item.walmart_store_no: item
        for item in db.execute(
            select(WalmartStoreProfile).where(WalmartStoreProfile.walmart_store_no.in_(list(stores)))
        ).scalars()
    }

    store_objects: dict[str, Store] = {}
    for raw_store, metadata in stores.items():
        store_code = _build_store_code(raw_store, numeric_store_width)
        store_name = _build_store_name(raw_store, numeric_store_width)
        store = existing_profiles.get(raw_store).store if existing_profiles.get(raw_store) else existing_stores.get(store_code)
        if not store:
            store = Store(
                store_code=store_code,
                name=store_name,
                region=metadata.get("state_code"),
                business_status="active",
                is_synthetic=False,
            )
            db.add(store)
            db.flush()
        else:
            store.name = store_name
            store.business_status = "active"
            store.is_synthetic = False
            if metadata.get("state_code") and not store.region:
                store.region = metadata["state_code"]

        profile = existing_profiles.get(raw_store)
        if not profile:
            profile = WalmartStoreProfile(
                store_id=store.id,
                walmart_store_no=raw_store,
                store_type=metadata.get("store_type"),
                store_size=metadata.get("store_size"),
            )
            db.add(profile)
        else:
            profile.store_id = store.id
            profile.store_type = metadata.get("store_type")
            profile.store_size = metadata.get("store_size")
        store_objects[raw_store] = store

    child_names = [f"Walmart Dept {_build_department_label(raw_department)}" for raw_department in departments]
    existing_categories = {
        item.name: item
        for item in db.execute(
            select(Category).where(Category.parent_id == walmart_parent.id, Category.name.in_(child_names))
        ).scalars()
    }
    product_codes = {
        f"{WALMART_PRODUCT_CODE_PREFIX}{_build_department_token(raw_department)}": raw_department
        for raw_department in departments
    }
    existing_products = {
        item.product_code: item
        for item in db.execute(select(Product).where(Product.product_code.in_(list(product_codes)))).scalars()
    }

    category_objects: dict[str, Category] = {}
    product_objects: dict[str, Product] = {}
    for raw_department, metadata in departments.items():
        department_label = _build_department_label(raw_department)
        category_name = f"Walmart Dept {department_label}"
        category = existing_categories.get(category_name)
        if not category:
            category = Category(
                name=category_name,
                parent_id=walmart_parent.id,
                description=f"Walmart raw department {raw_department}",
                is_active=True,
            )
            db.add(category)
            db.flush()
        else:
            category.description = f"Walmart raw department {raw_department}"
        category_objects[raw_department] = category

        product_code = f"{WALMART_PRODUCT_CODE_PREFIX}{_build_department_token(raw_department)}"
        product = existing_products.get(product_code)
        if not product:
            product = Product(
                product_code=product_code,
                name=f"Walmart Department {department_label}",
                category_id=category.id,
                unit="sales_amount",
                is_active=True,
            )
            db.add(product)
        else:
            product.name = f"Walmart Department {department_label}"
            product.category_id = category.id
            product.unit = "sales_amount"
            product.is_active = True
        product_objects[raw_department] = product

    db.flush()
    return store_objects, product_objects, category_objects


def clear_walmart_fact_data(db: Session) -> dict[str, int]:
    weekly_deleted = db.query(WalmartWeeklySalesFact).count()
    db.execute(delete(WalmartWeeklySalesFact))

    walmart_product_ids = list(
        db.execute(select(Product.id).where(Product.product_code.like(f"{WALMART_PRODUCT_CODE_PREFIX}%"))).scalars()
    )
    walmart_store_ids = list(db.execute(select(WalmartStoreProfile.store_id)).scalars())
    monthly_deleted = 0
    if walmart_product_ids and walmart_store_ids:
        monthly_deleted = db.query(MonthlySalesFact).filter(
            MonthlySalesFact.is_example_data.is_(False),
            MonthlySalesFact.product_id.in_(walmart_product_ids),
            MonthlySalesFact.store_id.in_(walmart_store_ids),
        ).count()
        db.execute(
            delete(MonthlySalesFact).where(
                MonthlySalesFact.is_example_data.is_(False),
                MonthlySalesFact.product_id.in_(walmart_product_ids),
                MonthlySalesFact.store_id.in_(walmart_store_ids),
            )
        )
    return {"weekly_deleted": weekly_deleted, "monthly_deleted": monthly_deleted}


def _weekly_fact_changed(existing: WalmartWeeklySalesFact, payload: WeeklyFactPayload, store_id: int, product_id: int) -> bool:
    expected_values = (
        store_id,
        product_id,
        payload.sales_date,
        payload.weekly_sales,
        payload.is_holiday,
        payload.temperature,
        payload.fuel_price,
        payload.markdown1,
        payload.markdown2,
        payload.markdown3,
        payload.markdown4,
        payload.markdown5,
        payload.cpi,
        payload.unemployment,
        payload.raw_store_code,
        payload.raw_department_code,
        payload.raw_category_code,
        payload.raw_week_key,
        payload.weekly_units,
        payload.avg_sell_price,
        payload.event_name_1,
        payload.event_type_1,
        payload.event_name_2,
        payload.event_type_2,
        payload.snap_flag,
    )
    actual_values = (
        existing.store_id,
        existing.product_id,
        existing.sales_date,
        Decimal(str(existing.weekly_sales)).quantize(MONEY_QUANT),
        existing.is_holiday,
        _to_decimal(str(existing.temperature), quant=MONEY_QUANT) if existing.temperature is not None else None,
        _to_decimal(str(existing.fuel_price), quant=PRICE_QUANT) if existing.fuel_price is not None else None,
        _to_decimal(str(existing.markdown1), quant=MONEY_QUANT) if existing.markdown1 is not None else None,
        _to_decimal(str(existing.markdown2), quant=MONEY_QUANT) if existing.markdown2 is not None else None,
        _to_decimal(str(existing.markdown3), quant=MONEY_QUANT) if existing.markdown3 is not None else None,
        _to_decimal(str(existing.markdown4), quant=MONEY_QUANT) if existing.markdown4 is not None else None,
        _to_decimal(str(existing.markdown5), quant=MONEY_QUANT) if existing.markdown5 is not None else None,
        _to_decimal(str(existing.cpi), quant=PRICE_QUANT) if existing.cpi is not None else None,
        _to_decimal(str(existing.unemployment), quant=PRICE_QUANT) if existing.unemployment is not None else None,
        existing.raw_store_code,
        existing.raw_department_code,
        existing.raw_category_code,
        existing.raw_week_key,
        _to_decimal(str(existing.weekly_units), quant=MONEY_QUANT) if existing.weekly_units is not None else None,
        _to_decimal(str(existing.avg_sell_price), quant=PRICE_QUANT) if existing.avg_sell_price is not None else None,
        existing.event_name_1,
        existing.event_type_1,
        existing.event_name_2,
        existing.event_type_2,
        existing.snap_flag,
    )
    return actual_values != expected_values


def _apply_weekly_upsert(
    db: Session,
    weekly_payloads: list[WeeklyFactPayload],
    store_map: dict[str, Store],
    product_map: dict[str, Product],
) -> tuple[int, int]:
    existing_by_key: dict[str, WalmartWeeklySalesFact] = {}
    source_keys = [payload.source_row_key for payload in weekly_payloads]
    for chunk in _chunked(source_keys, 500):
        rows = db.execute(select(WalmartWeeklySalesFact).where(WalmartWeeklySalesFact.source_row_key.in_(chunk))).scalars()
        existing_by_key.update({row.source_row_key: row for row in rows})

    imported_count = 0
    skipped_count = 0
    for payload in weekly_payloads:
        store_id = store_map[payload.raw_store_code].id
        product_id = product_map[payload.raw_department_code].id
        existing = existing_by_key.get(payload.source_row_key)
        if existing:
            if not _weekly_fact_changed(existing, payload, store_id, product_id):
                skipped_count += 1
                continue
            existing.store_id = store_id
            existing.product_id = product_id
            existing.sales_date = payload.sales_date
            existing.weekly_sales = payload.weekly_sales
            existing.is_holiday = payload.is_holiday
            existing.temperature = payload.temperature
            existing.fuel_price = payload.fuel_price
            existing.markdown1 = payload.markdown1
            existing.markdown2 = payload.markdown2
            existing.markdown3 = payload.markdown3
            existing.markdown4 = payload.markdown4
            existing.markdown5 = payload.markdown5
            existing.cpi = payload.cpi
            existing.unemployment = payload.unemployment
            existing.raw_store_code = payload.raw_store_code
            existing.raw_department_code = payload.raw_department_code
            existing.raw_category_code = payload.raw_category_code
            existing.raw_week_key = payload.raw_week_key
            existing.weekly_units = payload.weekly_units
            existing.avg_sell_price = payload.avg_sell_price
            existing.event_name_1 = payload.event_name_1
            existing.event_type_1 = payload.event_type_1
            existing.event_name_2 = payload.event_name_2
            existing.event_type_2 = payload.event_type_2
            existing.snap_flag = payload.snap_flag
            imported_count += 1
            continue

        db.add(
            WalmartWeeklySalesFact(
                store_id=store_id,
                product_id=product_id,
                sales_date=payload.sales_date,
                weekly_sales=payload.weekly_sales,
                is_holiday=payload.is_holiday,
                temperature=payload.temperature,
                fuel_price=payload.fuel_price,
                markdown1=payload.markdown1,
                markdown2=payload.markdown2,
                markdown3=payload.markdown3,
                markdown4=payload.markdown4,
                markdown5=payload.markdown5,
                cpi=payload.cpi,
                unemployment=payload.unemployment,
                raw_store_code=payload.raw_store_code,
                raw_department_code=payload.raw_department_code,
                raw_category_code=payload.raw_category_code,
                raw_week_key=payload.raw_week_key,
                weekly_units=payload.weekly_units,
                avg_sell_price=payload.avg_sell_price,
                event_name_1=payload.event_name_1,
                event_type_1=payload.event_type_1,
                event_name_2=payload.event_name_2,
                event_type_2=payload.event_type_2,
                snap_flag=payload.snap_flag,
                source_row_key=payload.source_row_key,
            )
        )
        imported_count += 1
    return imported_count, skipped_count


def _monthly_fact_changed(existing: MonthlySalesFact, retail_sales: Decimal, category_id: int, promo_flag: bool) -> bool:
    actual_sales = Decimal(str(existing.retail_sales)).quantize(MONEY_QUANT)
    return (
        actual_sales != retail_sales
        or float(existing.retail_transfers or 0) != 0
        or float(existing.warehouse_sales or 0) != 0
        or existing.category_id != category_id
        or existing.promo_flag != promo_flag
        or existing.supplier_id is not None
        or existing.warehouse_id is not None
        or existing.is_example_data is not False
    )


def _apply_monthly_upsert(
    db: Session,
    monthly_payloads: list[MonthlyFactPayload],
    store_map: dict[str, Store],
    product_map: dict[str, Product],
    category_map: dict[str, Category],
) -> tuple[int, int]:
    existing_rows = db.execute(
        select(MonthlySalesFact).where(MonthlySalesFact.is_example_data.is_(False))
    ).scalars()
    existing_map = {
        (row.year, row.month, row.store_id, row.product_id): row
        for row in existing_rows
        if row.store_id is not None
    }

    imported_count = 0
    skipped_count = 0
    for payload in monthly_payloads:
        store_id = store_map[payload.raw_store_code].id
        product = product_map[payload.raw_department_code]
        category = category_map[payload.raw_department_code]
        key = (payload.year, payload.month, store_id, product.id)
        existing = existing_map.get(key)
        if existing:
            if not _monthly_fact_changed(existing, payload.retail_sales, category.id, payload.promo_flag):
                skipped_count += 1
                continue
            existing.category_id = category.id
            existing.retail_sales = float(payload.retail_sales)
            existing.retail_transfers = 0
            existing.warehouse_sales = 0
            existing.promo_flag = payload.promo_flag
            existing.supplier_id = None
            existing.warehouse_id = None
            existing.is_example_data = False
            imported_count += 1
            continue

        db.add(
            MonthlySalesFact(
                year=payload.year,
                month=payload.month,
                supplier_id=None,
                product_id=product.id,
                category_id=category.id,
                retail_sales=float(payload.retail_sales),
                retail_transfers=0,
                warehouse_sales=0,
                store_id=store_id,
                warehouse_id=None,
                promo_flag=payload.promo_flag,
                is_example_data=False,
            )
        )
        imported_count += 1
    return imported_count, skipped_count


def import_walmart_data(
    db: Session,
    input_path: str | Path,
    *,
    dry_run: bool = False,
    replace_walmart: bool = False,
) -> WalmartImportSummary:
    with open_walmart_dataset(input_path) as inspection:
        prepared = prepare_walmart_import(inspection)
        runtime_profile = get_database_runtime_profile(db)
        imported_weekly = 0
        skipped_weekly = prepared.skipped_row_count
        imported_monthly = 0
        skipped_monthly = 0

        if not dry_run:
            if replace_walmart:
                clear_walmart_fact_data(db)
                db.flush()
                db.expunge_all()
            store_map, product_map, category_map = _ensure_walmart_master_data(db, prepared.stores, prepared.departments)
            imported_weekly, skipped_weekly_from_upsert = _apply_weekly_upsert(db, prepared.weekly_facts, store_map, product_map)
            imported_monthly, skipped_monthly = _apply_monthly_upsert(db, prepared.monthly_facts, store_map, product_map, category_map)
            skipped_weekly += skipped_weekly_from_upsert + skipped_monthly
            db.flush()
            invalidate_business_cache()
        else:
            imported_weekly = len(prepared.weekly_facts)
            imported_monthly = len(prepared.monthly_facts)

        return WalmartImportSummary(
            dataset_kind=inspection.dataset_kind,
            dry_run=dry_run,
            detected_files=inspection.detected_files,
            file_headers=inspection.file_headers,
            raw_weekly_sales_count=prepared.raw_weekly_sales_count,
            imported_row_count=imported_weekly,
            skipped_row_count=skipped_weekly,
            unparsed_row_count=prepared.unparsed_row_count,
            feature_missing_count=prepared.feature_missing_count,
            store_count=len(prepared.stores),
            department_product_count=len(prepared.departments),
            monthly_sales_fact_count=imported_monthly if dry_run else len(prepared.monthly_facts),
            min_sales_date=prepared.min_sales_date,
            max_sales_date=prepared.max_sales_date,
            database_runtime=runtime_profile,
        )


def get_walmart_status(db: Session) -> dict[str, Any]:
    raw_weekly_sales_count = db.scalar(select(func.count(WalmartWeeklySalesFact.id))) or 0
    monthly_sales_fact_count = db.scalar(
        select(func.count(MonthlySalesFact.id))
        .join(Product, Product.id == MonthlySalesFact.product_id)
        .where(
            MonthlySalesFact.is_example_data.is_(False),
            Product.product_code.like(f"{WALMART_PRODUCT_CODE_PREFIX}%"),
        )
    ) or 0
    store_count = db.scalar(select(func.count(WalmartStoreProfile.id))) or 0
    department_product_count = db.scalar(
        select(func.count(Product.id)).where(Product.product_code.like(f"{WALMART_PRODUCT_CODE_PREFIX}%"))
    ) or 0
    min_sales_date, max_sales_date = db.execute(
        select(func.min(WalmartWeeklySalesFact.sales_date), func.max(WalmartWeeklySalesFact.sales_date))
    ).one()
    runtime = get_database_runtime_profile(db)
    return {
        "raw_weekly_sales_count": raw_weekly_sales_count,
        "monthly_sales_fact_count": monthly_sales_fact_count,
        "store_count": store_count,
        "department_product_count": department_product_count,
        "min_sales_date": min_sales_date.isoformat() if min_sales_date else None,
        "max_sales_date": max_sales_date.isoformat() if max_sales_date else None,
        "database_runtime": {
            "mode": runtime["mode"],
            "active_dialect": runtime["active_dialect"],
        },
    }
