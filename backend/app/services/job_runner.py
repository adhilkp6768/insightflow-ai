"""Run cleaning, training, and UCI import outside the request when configured.

Jobs stay in this API process. A multi-process deployment still needs a shared worker.
Tests set JOBS_INLINE so a request finishes the job before it returns.
"""

from __future__ import annotations

import logging
import threading
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.exceptions import AppError
from app.models import ProcessingJob, User
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

ACTIVE = ("queued", "running")


def serialize_job(job: ProcessingJob) -> dict:
    return {
        "id": str(job.id),
        "workspace_id": str(job.workspace_id),
        "dataset_id": None if job.dataset_id is None else str(job.dataset_id),
        "job_type": job.job_type,
        "status": job.status,
        "message": job.message,
        "created_at": job.created_at.isoformat(),
        "finished_at": None if job.finished_at is None else job.finished_at.isoformat(),
    }


def get_visible_job(db: Session, user: User, job_id: uuid.UUID) -> dict:
    from app.services.access import require_workspace

    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise AppError("not_found", "Job not found.", 404)
    require_workspace(db, user, job.workspace_id)
    return serialize_job(job)


def list_jobs(db: Session, user: User, workspace_id: uuid.UUID) -> list[dict]:
    from app.services.access import require_workspace

    require_workspace(db, user, workspace_id)
    rows = db.scalars(
        select(ProcessingJob)
        .where(ProcessingJob.workspace_id == workspace_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(20)
    ).all()
    return [serialize_job(row) for row in rows]


def enqueue(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user: User,
    job_type: str,
    dataset_id: uuid.UUID | None,
    payload: dict,
    message: str,
) -> ProcessingJob:
    existing = db.scalar(
        select(ProcessingJob).where(
            ProcessingJob.workspace_id == workspace_id,
            ProcessingJob.job_type == job_type,
            ProcessingJob.dataset_id == dataset_id,
            ProcessingJob.status.in_(ACTIVE),
        )
    )
    if existing is not None:
        if get_settings().jobs_inline:
            run_job(existing.id)
            db.expire_all()
            db.refresh(existing)
        return existing
    job = ProcessingJob(
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        job_type=job_type,
        status="queued",
        message=message[:500],
        payload=payload,
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    if get_settings().jobs_inline:
        run_job(job.id)
        db.expire_all()
        db.refresh(job)
    else:
        threading.Thread(target=run_job, args=(job.id,), daemon=True, name=f"insightflow-{job.id.hex[:8]}").start()
    return job


def run_job(job_id: uuid.UUID) -> None:
    from app.services import dataset_service, prediction_service

    session = get_session_factory()()
    try:
        job = session.get(ProcessingJob, job_id)
        if job is None or job.status in {"succeeded", "failed"}:
            return
        user = session.get(User, job.created_by)
        if user is None:
            raise AppError("not_found", "The user who started this job no longer exists.", 404)
        job.status = "running"
        session.commit()
        if job.job_type == "prepare":
            dataset_service.run_prepare(session, user, job)
        elif job.job_type.startswith("train_"):
            prediction_service.run_train(session, user, job)
        elif job.job_type == "uci":
            dataset_service.run_uci_import(session, user, job)
        else:
            raise AppError("unknown_job", "This job type is not supported.", 422)
        job.status = "succeeded"
        job.finished_at = utcnow()
        session.commit()
    except Exception as exc:
        logger.exception("background job failed")
        session.rollback()
        job = session.get(ProcessingJob, job_id)
        if job is not None and job.status != "succeeded":
            job.status = "failed"
            job.message = str(exc)[:500] if isinstance(exc, (AppError, ValueError)) else "The job failed."
            job.finished_at = utcnow()
            session.commit()
        if get_settings().jobs_inline:
            raise
    finally:
        session.close()
