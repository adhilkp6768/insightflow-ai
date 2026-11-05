"""Upload, profile, clean, and delete datasets."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.domain.columns import (
    ROLE_LABELS,
    clean_mapping,
    missing_sales_roles,
    suggest_mapping,
)
from app.models import (
    Dataset,
    DatasetColumn,
    DatasetProfile,
    DatasetVersion,
    ProcessingJob,
    User,
)
from app.services.access import record_activity, require_dataset, require_workspace
from app.services.frames import (
    data_root,
    drop_query_table,
    latest_version,
    table_name_for,
    write_query_table,
)
from app.utils.json_safe import json_safe
from app.utils.preprocessing import clean_transactions
from app.utils.profiling import quality_report
from app.utils.sample_data import build_sample_frame
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


def _iso(value: datetime | date | None) -> str | None:
    return None if value is None else value.isoformat()


def read_upload(path: Path, file_format: str) -> pd.DataFrame:
    if file_format == "csv":
        frame = None
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                frame = pd.read_csv(path, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        if frame is None:
            raise ValueError("The CSV encoding is not supported.")
    else:
        sheets = pd.read_excel(path, sheet_name=None)
        frames = []
        for name, sheet in sheets.items():
            copy = sheet.copy()
            copy["source_sheet"] = str(name)
            frames.append(copy)
        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    frame.columns = [str(column).strip() for column in frame.columns]
    if len(frame.columns) > 200:
        raise ValueError("Files with more than 200 columns are not accepted.")
    if frame.empty:
        raise ValueError("The file has no rows.")
    return frame


def _store_profile(
    db: Session,
    dataset_id: uuid.UUID,
    stage: str,
    summary: dict,
    version_id: uuid.UUID | None = None,
) -> None:
    db.execute(
        delete(DatasetColumn).where(DatasetColumn.dataset_id == dataset_id, DatasetColumn.stage == stage)
    )
    db.execute(
        delete(DatasetProfile).where(DatasetProfile.dataset_id == dataset_id, DatasetProfile.stage == stage)
    )
    safe = json_safe(summary)
    db.add(
        DatasetProfile(
            dataset_id=dataset_id,
            version_id=version_id,
            stage=stage,
            quality_score=float(safe["score"]),
            breakdown={
                "completeness": safe["completeness"],
                "uniqueness": safe["uniqueness"],
                "validity": safe["validity"],
                "consistency": safe["consistency"],
                "formula": safe["formula"],
            },
            summary=safe,
        )
    )
    for column in safe["columns"]:
        db.add(
            DatasetColumn(
                dataset_id=dataset_id,
                version_id=version_id,
                stage=stage,
                name=column["name"][:200],
                ordinal=column["ordinal"],
                inferred_type=column["inferred_type"],
                semantic_role=column["semantic_role"],
                null_count=column["null_count"],
                distinct_count=column["distinct_count"],
            )
        )


def _profile(db: Session, dataset: Dataset) -> dict | None:
    return db.scalar(
        select(DatasetProfile)
        .where(DatasetProfile.dataset_id == dataset.id, DatasetProfile.stage == "raw")
        .order_by(DatasetProfile.created_at.desc())
    )


def serialize_dataset(db: Session, dataset: Dataset) -> dict:
    version = latest_version(db, dataset.id)
    profile = _profile(db, dataset)
    mapping = clean_mapping(dataset.column_mapping)
    return {
        "id": str(dataset.id),
        "workspace_id": str(dataset.workspace_id),
        "name": dataset.name,
        "status": dataset.status,
        "source_type": dataset.source_type,
        "original_filename": dataset.original_filename,
        "file_format": dataset.file_format,
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
        "quality_score": None if profile is None else profile.quality_score,
        "mapping": mapping,
        "missing_roles": missing_sales_roles(mapping),
        "customer_ready": bool(mapping.get("customer_id")),
        "has_processed": version is not None,
        "processed_rows": None if version is None else version.valid_row_count,
        "min_date": None if version is None else _iso(version.min_date),
        "max_date": None if version is None else _iso(version.max_date),
        "error_message": dataset.error_message,
        "created_at": _iso(dataset.created_at),
        "role_labels": ROLE_LABELS,
    }


def list_datasets(db: Session, user: User, workspace_id: uuid.UUID) -> list[dict]:
    require_workspace(db, user, workspace_id)
    rows = db.scalars(
        select(Dataset).where(Dataset.workspace_id == workspace_id).order_by(Dataset.created_at.desc())
    ).all()
    return [serialize_dataset(db, dataset) for dataset in rows]


def get_dataset(db: Session, user: User, dataset_id: uuid.UUID) -> dict:
    dataset = require_dataset(db, user, dataset_id)
    payload = serialize_dataset(db, dataset)
    profile = _profile(db, dataset)
    payload["profile"] = None if profile is None else profile.summary
    version = latest_version(db, dataset.id)
    payload["cleaning"] = None if version is None else version.decisions
    return payload


def _create_dataset(
    db: Session,
    user: User,
    workspace_id: uuid.UUID,
    *,
    name: str,
    filename: str,
    file_format: str,
    content: bytes,
    source_type: str,
) -> Dataset:
    require_workspace(db, user, workspace_id, write=True)
    dataset_id = uuid.uuid4()
    directory = data_root() / "uploads" / dataset_id.hex
    directory.mkdir(parents=True, exist_ok=True)
    raw_path = directory / filename
    raw_path.write_bytes(content)
    dataset = Dataset(
        id=dataset_id,
        workspace_id=workspace_id,
        name=name[:160],
        status="ready",
        source_type=source_type,
        original_filename=filename[:255],
        file_format=file_format,
        raw_path=str(raw_path),
        checksum=hashlib.sha256(content).hexdigest(),
        column_mapping={},
        row_count=0,
        column_count=0,
        created_by=user.id,
    )
    db.add(dataset)
    job = ProcessingJob(
        workspace_id=workspace_id,
        dataset_id=dataset.id,
        job_type="profile",
        status="running",
        payload={},
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    try:
        frame = read_upload(raw_path, file_format)
        mapping = suggest_mapping([str(column) for column in frame.columns])
        summary = quality_report(frame, mapping)
        dataset.column_mapping = mapping
        dataset.row_count = int(len(frame))
        dataset.column_count = int(len(frame.columns))
        dataset.status = "ready"
        _store_profile(db, dataset.id, "raw", summary)
        job.status = "succeeded"
        job.message = f"Profiled {dataset.row_count} rows."
        job.finished_at = utcnow()
        record_activity(
            db,
            workspace_id=workspace_id,
            user=user,
            action="dataset.uploaded",
            resource_type="dataset",
            resource_id=str(dataset.id),
            context={"name": dataset.name, "rows": dataset.row_count, "source_type": source_type},
        )
        db.commit()
    except Exception as exc:
        logger.exception("dataset profiling failed")
        dataset.status = "failed"
        dataset.error_message = str(exc)[:500] if isinstance(exc, ValueError) else "The file could not be profiled."
        job.status = "failed"
        job.message = dataset.error_message
        job.finished_at = utcnow()
        db.commit()
        raise AppError("invalid_file", dataset.error_message, 422) from exc
    db.refresh(dataset)
    return dataset


def ingest_upload(
    db: Session,
    user: User,
    workspace_id: uuid.UUID,
    *,
    filename: str,
    content: bytes,
    name: str | None,
) -> dict:
    settings = get_settings()
    if len(content) > settings.max_upload_bytes:
        limit = settings.max_upload_bytes // (1024 * 1024)
        raise AppError("file_too_large", f"Files must be {limit} MB or smaller.", 413)
    if not content:
        raise AppError("invalid_file", "The file is empty.", 422)
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".csv":
        file_format = "csv"
        if b"\x00" in content[:8192]:
            raise AppError("invalid_file", "This file does not look like a CSV.", 422)
    elif suffix == ".xlsx":
        file_format = "xlsx"
        if content[:2] != b"PK":
            raise AppError("invalid_file", "This file does not look like an Excel workbook.", 422)
    else:
        raise AppError("invalid_file", "Upload a .csv or .xlsx file.", 422)
    safe_name = Path(filename).name.replace("/", "")[:255]
    display = (name or Path(safe_name).stem).strip() or "Dataset"
    dataset = _create_dataset(
        db,
        user,
        workspace_id,
        name=display,
        filename=safe_name,
        file_format=file_format,
        content=content,
        source_type="upload",
    )
    return serialize_dataset(db, dataset)


def ingest_sample(db: Session, user: User, workspace_id: uuid.UUID) -> dict:
    require_workspace(db, user, workspace_id, write=True)
    existing = db.scalar(
        select(Dataset).where(
            Dataset.workspace_id == workspace_id,
            Dataset.source_type == "sample",
            Dataset.status == "ready",
        )
    )
    if existing is not None:
        return serialize_dataset(db, existing)
    frame = build_sample_frame()
    content = frame.to_csv(index=False).encode("utf-8")
    dataset = _create_dataset(
        db,
        user,
        workspace_id,
        name="Sample retail transactions",
        filename="sample-retail-transactions.csv",
        file_format="csv",
        content=content,
        source_type="sample",
    )
    return serialize_dataset(db, dataset)


def update_mapping(db: Session, user: User, dataset_id: uuid.UUID, mapping: dict) -> dict:
    dataset = require_dataset(db, user, dataset_id, write=True)
    if dataset.status != "ready":
        raise AppError("invalid_file", dataset.error_message or "This dataset is not ready.", 422)
    cleaned = clean_mapping(mapping)
    frame = read_upload(Path(dataset.raw_path), dataset.file_format)
    columns = {str(column) for column in frame.columns}
    unknown = [column for column in cleaned.values() if column and column not in columns]
    if unknown:
        raise AppError("invalid_mapping", "Choose columns that exist in the uploaded file.", 422)
    dataset.column_mapping = cleaned
    dataset.updated_at = utcnow()
    _store_profile(db, dataset.id, "raw", quality_report(frame, cleaned))
    db.commit()
    return get_dataset(db, user, dataset.id)


def prepare_dataset(db: Session, user: User, dataset_id: uuid.UUID, drop_exact_duplicates: bool) -> dict:
    from app.services.job_runner import enqueue, serialize_job

    dataset = require_dataset(db, user, dataset_id, write=True)
    if dataset.status != "ready":
        raise AppError("invalid_file", dataset.error_message or "This dataset is not ready.", 422)
    mapping = clean_mapping(dataset.column_mapping)
    missing = missing_sales_roles(mapping)
    if missing:
        labels = ", ".join(missing)
        raise AppError("missing_roles", f"Map these columns before cleaning: {labels}.", 422)
    job = enqueue(
        db,
        workspace_id=dataset.workspace_id,
        user=user,
        job_type="prepare",
        dataset_id=dataset.id,
        payload={"drop_exact_duplicates": drop_exact_duplicates},
        message="Cleaning is queued.",
    )
    if get_settings().jobs_inline:
        return get_dataset(db, user, dataset.id)
    return {"job": serialize_job(job)}


def run_prepare(db: Session, user: User, job: ProcessingJob) -> None:
    dataset = db.get(Dataset, job.dataset_id)
    if dataset is None:
        raise AppError("not_found", "Dataset not found.", 404)
    drop_exact_duplicates = bool((job.payload or {}).get("drop_exact_duplicates"))
    mapping = clean_mapping(dataset.column_mapping)
    job.message = "Reading the original file."
    db.commit()
    frame = read_upload(Path(dataset.raw_path), dataset.file_format)
    try:
        cleaned, decisions = clean_transactions(frame, mapping, {"drop_exact_duplicates": drop_exact_duplicates})
    except ValueError as exc:
        raise AppError("missing_roles", str(exc), 422) from exc
    version_number = 1 + (
        db.scalar(
            select(DatasetVersion.version_number)
            .where(DatasetVersion.dataset_id == dataset.id)
            .order_by(DatasetVersion.version_number.desc())
        )
        or 0
    )
    job.message = "Writing the cleaned copy. The original file stays unchanged."
    db.commit()
    connection = db.connection()
    previous = latest_version(db, dataset.id)
    if previous is not None:
        drop_query_table(previous.table_name, connection)
        previous.table_name = None
    version = DatasetVersion(
        dataset_id=dataset.id,
        version_number=version_number,
        storage_path="",
        table_name=None,
        row_count=int(len(cleaned)),
        valid_row_count=int(cleaned["is_valid"].sum()),
        cleaning_config={"drop_exact_duplicates": drop_exact_duplicates},
        decisions=json_safe(decisions),
    )
    db.add(version)
    db.flush()
    directory = data_root() / "processed" / dataset.id.hex
    directory.mkdir(parents=True, exist_ok=True)
    storage = directory / f"v{version_number}.csv"
    cleaned.to_csv(storage, index=False)
    table = table_name_for(dataset.id)
    write_query_table(table, cleaned, connection)
    dated = pd.to_datetime(cleaned.loc[cleaned["is_valid"] == 1, "invoice_date"], errors="coerce").dropna()
    version.storage_path = str(storage)
    version.table_name = table
    version.min_date = None if dated.empty else dated.min().date()
    version.max_date = None if dated.empty else dated.max().date()
    canonical = {role: role for role in mapping if role in cleaned.columns}
    _store_profile(db, dataset.id, "processed", quality_report(cleaned, canonical), version.id)
    record_activity(
        db,
        workspace_id=dataset.workspace_id,
        user=user,
        action="dataset.cleaned",
        resource_type="dataset",
        resource_id=str(dataset.id),
        context={"version": version_number, "valid_rows": version.valid_row_count},
    )
    job.message = f"Cleaned version {version_number} is ready. {version.valid_row_count} rows stay in the KPI set."


def start_uci_import(db: Session, user: User, workspace_id: uuid.UUID) -> dict:
    from app.services.job_runner import enqueue, serialize_job

    require_workspace(db, user, workspace_id, write=True)
    existing = db.scalar(
        select(Dataset).where(
            Dataset.workspace_id == workspace_id,
            Dataset.source_type == "uci",
            Dataset.status == "ready",
        )
    )
    if existing is not None:
        return {"dataset": serialize_dataset(db, existing), "job": None}
    job = enqueue(
        db,
        workspace_id=workspace_id,
        user=user,
        job_type="uci",
        dataset_id=None,
        payload={},
        message="Online Retail II is queued.",
    )
    if not get_settings().jobs_inline:
        return {"dataset": None, "job": serialize_job(job)}
    imported = db.scalar(
        select(Dataset).where(
            Dataset.workspace_id == workspace_id,
            Dataset.source_type == "uci",
            Dataset.status == "ready",
        )
    )
    return {
        "dataset": None if imported is None else serialize_dataset(db, imported),
        "job": serialize_job(job),
    }


def run_uci_import(db: Session, user: User, job: ProcessingJob) -> None:
    from app.services.uci_data import ensure_uci_workbook

    def progress(message: str) -> None:
        job.message = message[:500]
        db.commit()

    path = ensure_uci_workbook(progress)
    progress("Reading the workbook and calculating the quality score.")
    content = path.read_bytes()
    dataset = _create_dataset(
        db,
        user,
        job.workspace_id,
        name="Online Retail II",
        filename=path.name[:255],
        file_format="xlsx",
        content=content,
        source_type="uci",
    )
    job.dataset_id = dataset.id
    job.message = (
        f"Profiled {dataset.row_count} rows from Online Retail II. "
        "Create a cleaned version when you are ready. The original workbook is unchanged."
    )


def preview_dataset(
    db: Session,
    user: User,
    dataset_id: uuid.UUID,
    *,
    stage: str,
    limit: int,
    offset: int,
) -> dict:
    dataset = require_dataset(db, user, dataset_id)
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    if stage == "processed":
        version = latest_version(db, dataset.id)
        if version is None:
            raise AppError("not_ready", "This dataset does not have a cleaned version yet.", 422)
        frame = pd.read_csv(version.storage_path)
        total = int(len(frame))
        page = frame.iloc[offset : offset + limit]
    else:
        frame = read_upload(Path(dataset.raw_path), dataset.file_format)
        total = int(len(frame))
        page = frame.iloc[offset : offset + limit]
    rows = json_safe(page.where(page.notna(), None).to_dict(orient="records"))
    return {
        "stage": stage,
        "columns": [str(column) for column in page.columns],
        "rows": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def delete_dataset(db: Session, user: User, dataset_id: uuid.UUID) -> None:
    dataset = require_dataset(db, user, dataset_id, write=True)
    version = latest_version(db, dataset.id)
    if version is not None:
        drop_query_table(version.table_name, db.connection())
    for folder in (
        data_root() / "uploads" / dataset.id.hex,
        data_root() / "processed" / dataset.id.hex,
    ):
        if folder.exists():
            for path in folder.rglob("*"):
                if path.is_file():
                    path.unlink()
            for path in sorted(folder.rglob("*"), reverse=True):
                if path.is_dir():
                    path.rmdir()
            folder.rmdir()
    record_activity(
        db,
        workspace_id=dataset.workspace_id,
        user=user,
        action="dataset.deleted",
        resource_type="dataset",
        resource_id=str(dataset.id),
        context={"name": dataset.name},
    )
    db.delete(dataset)
    db.commit()
