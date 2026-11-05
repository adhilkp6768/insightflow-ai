"""Train and read segmentation, churn, and forecast runs."""

from __future__ import annotations

import uuid

import joblib
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.ml.churn_model import train_churn
from app.ml.forecasting_model import forecast_revenue
from app.ml.segmentation_model import segment_customers
from app.models import Dataset, ModelRun, User
from app.services.access import record_activity, require_dataset
from app.services.frames import data_root, load_frame, require_version
from app.utils.json_safe import json_safe


def _save_run(db: Session, user: User, dataset, version, model_type: str, result: dict) -> dict:
    status = "succeeded" if result.get("sufficient") else "insufficient"
    artifact = None
    if status == "succeeded" and model_type != "forecast":
        directory = data_root() / "models"
        directory.mkdir(parents=True, exist_ok=True)
        artifact_path = directory / f"{uuid.uuid4().hex}.joblib"
        joblib.dump({"model_type": model_type, "summary": result}, artifact_path)
        artifact = str(artifact_path)
    safe = json_safe(result)
    run = ModelRun(
        dataset_id=dataset.id,
        version_id=version.id,
        model_type=model_type,
        status=status,
        label_definition={"text": safe.get("label_definition") or safe.get("reason")},
        metrics=safe,
        summary=safe,
        artifact_path=artifact,
        created_by=user.id,
    )
    db.add(run)
    record_activity(
        db,
        workspace_id=dataset.workspace_id,
        user=user,
        action=f"model.{model_type}",
        resource_type="model_run",
        resource_id=str(run.id),
        context={"status": status, "model_type": model_type},
    )
    db.commit()
    db.refresh(run)
    return _serialize(run)


def _serialize(run: ModelRun) -> dict:
    return {
        "id": str(run.id),
        "dataset_id": str(run.dataset_id),
        "model_type": run.model_type,
        "status": run.status,
        "created_at": run.created_at.isoformat(),
        "result": run.summary,
    }


def train_model(db: Session, user: User, dataset_id: uuid.UUID, model_type: str, inactivity_days: int) -> dict:
    from app.services.job_runner import enqueue, serialize_job

    dataset = require_dataset(db, user, dataset_id, write=True)
    require_version(db, dataset)
    job = enqueue(
        db,
        workspace_id=dataset.workspace_id,
        user=user,
        job_type=f"train_{model_type}",
        dataset_id=dataset.id,
        payload={"model_type": model_type, "inactivity_days": inactivity_days},
        message=f"{model_type} training is queued.",
    )
    if get_settings().jobs_inline:
        saved = latest_model(db, dataset.id, model_type)
        if saved is None:
            raise AppError("job_failed", job.message or "Training did not produce a model.", 422)
        return _serialize(saved)
    return {"job": serialize_job(job)}


def run_train(db: Session, user: User, job) -> None:
    dataset = db.get(Dataset, job.dataset_id)
    if dataset is None:
        raise AppError("not_found", "Dataset not found.", 404)
    version = require_version(db, dataset)
    payload = job.payload or {}
    model_type = str(payload.get("model_type") or "")
    inactivity_days = int(payload.get("inactivity_days") or 90)
    job.message = f"Training {model_type} on the cleaned rows."
    db.commit()
    frame = load_frame(version, db.connection())
    if model_type == "segments":
        result = segment_customers(frame)
    elif model_type == "churn":
        result = train_churn(frame, inactivity_days)
    elif model_type == "forecast":
        result = forecast_revenue(frame)
    else:
        raise AppError("unknown_model", "Choose segments, churn, or forecast.", 422)
    _save_run(db, user, dataset, version, model_type, result)
    job.message = f"{model_type} training finished with status {'ready' if result.get('sufficient') else 'insufficient'}."


def list_models(db: Session, user: User, dataset_id: uuid.UUID) -> list[dict]:
    dataset = require_dataset(db, user, dataset_id)
    runs = db.scalars(
        select(ModelRun).where(ModelRun.dataset_id == dataset.id).order_by(ModelRun.created_at.desc())
    ).all()
    return [_serialize(run) for run in runs]


def latest_model(db: Session, dataset_id: uuid.UUID, model_type: str) -> ModelRun | None:
    return db.scalar(
        select(ModelRun)
        .where(ModelRun.dataset_id == dataset_id, ModelRun.model_type == model_type)
        .order_by(ModelRun.created_at.desc())
    )
