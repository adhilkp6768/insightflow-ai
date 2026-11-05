"""Load and store the analytical copy of a dataset."""

from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import Dataset, DatasetVersion
from app.services.sql_guard import validate_table_name


def data_root() -> Path:
    configured = Path(get_settings().data_dir)
    root = configured if configured.is_absolute() else Path.cwd() / configured
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def table_name_for(dataset_id: uuid.UUID) -> str:
    return validate_table_name(f"ds_{dataset_id.hex}")


def latest_version(db: Session, dataset_id: uuid.UUID) -> DatasetVersion | None:
    return db.scalar(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id, DatasetVersion.table_name.is_not(None))
        .order_by(DatasetVersion.version_number.desc())
    )


def require_version(db: Session, dataset: Dataset) -> DatasetVersion:
    version = latest_version(db, dataset.id)
    if version is None:
        raise AppError(
            "not_ready",
            "Create a cleaned version before running analytics. The uploaded file is left unchanged.",
            422,
        )
    return version


def write_query_table(table: str, frame: pd.DataFrame, connection) -> None:
    validate_table_name(table)
    frame.to_sql(table, connection, if_exists="replace", index=False, chunksize=5000)


def drop_query_table(table: str | None, connection) -> None:
    if not table:
        return
    validate_table_name(table)
    connection.execute(text(f"DROP TABLE IF EXISTS {table}"))


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    work["invoice_date"] = pd.to_datetime(work["invoice_date"], errors="coerce")
    work["is_valid"] = work["is_valid"].fillna(0).astype(int).astype(bool)
    for column in ("quantity", "unit_price", "unit_cost", "revenue"):
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    for column in ("invoice_id", "stock_code", "description", "customer_id", "country", "category"):
        if column not in work.columns:
            work[column] = None
        work[column] = work[column].map(lambda value: None if pd.isna(value) else str(value).strip() or None)
    return work


def load_frame(version: DatasetVersion, connection) -> pd.DataFrame:
    table = validate_table_name(version.table_name or "")
    frame = pd.read_sql(f"SELECT * FROM {table}", connection)
    return normalize_frame(frame)


def apply_filters(
    frame: pd.DataFrame,
    *,
    product: str | None = None,
    country: str | None = None,
    customer: str | None = None,
) -> pd.DataFrame:
    selected = frame
    if product:
        selected = selected.loc[selected["stock_code"].fillna("").astype(str) == product]
    if country:
        selected = selected.loc[selected["country"].fillna("").astype(str) == country]
    if customer:
        selected = selected.loc[selected["customer_id"].fillna("").astype(str) == customer]
    return selected.copy()
