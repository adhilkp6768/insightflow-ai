"""Dataset, analytics, model, and notification routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.models import ActivityLog, User
from app.services import analytics_service, dataset_service, prediction_service
from app.services.access import require_workspace
from app.services.job_runner import get_visible_job, list_jobs

router = APIRouter()


class MappingRequest(BaseModel):
    mapping: dict[str, str | None]


class PrepareRequest(BaseModel):
    drop_exact_duplicates: bool = False


class TrainRequest(BaseModel):
    inactivity_days: int = Field(default=90, ge=14, le=365)


def _notifications(db: Session, user: User, workspace_id: uuid.UUID) -> list[dict]:
    require_workspace(db, user, workspace_id)
    rows = db.scalars(
        select(ActivityLog)
        .where(ActivityLog.workspace_id == workspace_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(8)
    ).all()
    labels = {
        "dataset.uploaded": "Dataset uploaded",
        "dataset.cleaned": "Cleaned version created",
        "dataset.deleted": "Dataset deleted",
        "model.churn": "Churn model finished",
        "model.segments": "Segmentation finished",
        "model.forecast": "Forecast finished",
        "report.created": "Report ready",
        "auth.register": "Account created",
        "auth.login": "Signed in",
        "auth.logout": "Signed out",
        "member.added": "Member added",
        "member.invited": "Invitation sent",
        "member.removed": "Member removed",
        "member.role_changed": "Role updated",
    }
    payload = []
    for row in rows:
        context = row.context or {}
        name = context.get("name") or context.get("title") or context.get("model_type")
        message = labels.get(row.action, row.action)
        if name:
            message = f"{message}: {name}"
        payload.append(
            {
                "id": str(row.id),
                "action": row.action,
                "message": message,
                "created_at": row.created_at.isoformat(),
            }
        )
    return payload


@router.get("/workspaces/{workspace_id}/notifications")
def notifications(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return _notifications(db, user, workspace_id)


@router.get("/workspaces/{workspace_id}/datasets")
def list_datasets(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return dataset_service.list_datasets(db, user, workspace_id)


@router.post("/workspaces/{workspace_id}/datasets", status_code=201)
async def upload_dataset(
    workspace_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    chunks: list[bytes] = []
    size = 0
    limit = get_settings().max_upload_bytes
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise AppError("file_too_large", f"Files must be {limit // (1024 * 1024)} MB or smaller.", 413)
        chunks.append(chunk)
    return dataset_service.ingest_upload(
        db,
        user,
        workspace_id,
        filename=file.filename or "upload.csv",
        content=b"".join(chunks),
        name=name,
    )


@router.get("/workspaces/{workspace_id}/jobs")
def workspace_jobs(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_jobs(db, user, workspace_id)


@router.get("/jobs/{job_id}")
def job_status(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return get_visible_job(db, user, job_id)


@router.post("/workspaces/{workspace_id}/datasets/uci", status_code=202)
def load_uci(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return dataset_service.start_uci_import(db, user, workspace_id)


@router.post("/workspaces/{workspace_id}/datasets/sample", status_code=201)
def load_sample(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return dataset_service.ingest_sample(db, user, workspace_id)


@router.get("/datasets/{dataset_id}")
def get_dataset(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return dataset_service.get_dataset(db, user, dataset_id)


@router.put("/datasets/{dataset_id}/mapping")
def update_mapping(
    dataset_id: uuid.UUID,
    body: MappingRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return dataset_service.update_mapping(db, user, dataset_id, body.mapping)


@router.post("/datasets/{dataset_id}/prepare")
def prepare_dataset(
    dataset_id: uuid.UUID,
    body: PrepareRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return dataset_service.prepare_dataset(db, user, dataset_id, body.drop_exact_duplicates)


@router.get("/datasets/{dataset_id}/preview")
def preview_dataset(
    dataset_id: uuid.UUID,
    stage: str = "raw",
    limit: int = 25,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if stage not in {"raw", "processed"}:
        raise AppError("invalid_stage", "Choose the raw or processed stage.", 422)
    return dataset_service.preview_dataset(db, user, dataset_id, stage=stage, limit=limit, offset=offset)


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    dataset_service.delete_dataset(db, user, dataset_id)


@router.get("/datasets/{dataset_id}/analytics/filters")
def analytics_filters(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return analytics_service.filter_options(db, user, dataset_id)


@router.get("/datasets/{dataset_id}/analytics/sales")
def sales_analytics(
    dataset_id: uuid.UUID,
    date_from: str | None = None,
    date_to: str | None = None,
    product: str | None = None,
    country: str | None = None,
    customer: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return analytics_service.sales_analytics(
        db,
        user,
        dataset_id,
        date_from=date_from,
        date_to=date_to,
        product=product,
        country=country,
        customer=customer,
    )


@router.get("/datasets/{dataset_id}/analytics/customers")
def customer_analytics(
    dataset_id: uuid.UUID,
    date_from: str | None = None,
    date_to: str | None = None,
    country: str | None = None,
    customer_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if customer_id:
        return analytics_service.customer_detail(db, user, dataset_id, customer_id)
    return analytics_service.customer_analytics(
        db, user, dataset_id, date_from=date_from, date_to=date_to, country=country
    )


@router.get("/datasets/{dataset_id}/analytics/products")
def product_analytics(
    dataset_id: uuid.UUID,
    date_from: str | None = None,
    date_to: str | None = None,
    country: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return analytics_service.product_analytics(
        db, user, dataset_id, date_from=date_from, date_to=date_to, country=country
    )


@router.get("/datasets/{dataset_id}/models")
def list_models(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return prediction_service.list_models(db, user, dataset_id)


@router.post("/datasets/{dataset_id}/models/{model_type}")
def train_model(
    dataset_id: uuid.UUID,
    model_type: str,
    body: TrainRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if model_type not in {"segments", "churn", "forecast"}:
        raise AppError("unknown_model", "Choose segments, churn, or forecast.", 422)
    return prediction_service.train_model(db, user, dataset_id, model_type, body.inactivity_days)
