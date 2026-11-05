"""Workspace authorization. A missing membership is a 404, not a 403."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import ActivityLog, Dataset, User, WorkspaceMembership

WRITER_ROLES = {"owner", "admin", "analyst"}


def require_workspace(
    db: Session,
    user: User,
    workspace_id: uuid.UUID,
    *,
    write: bool = False,
) -> WorkspaceMembership:
    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user.id,
        )
    )
    if membership is None:
        raise AppError("not_found", "Workspace not found.", 404)
    if write and membership.role not in WRITER_ROLES:
        raise AppError("forbidden", "Viewers can read this workspace but cannot change it.", 403)
    return membership


def require_dataset(db: Session, user: User, dataset_id: uuid.UUID, *, write: bool = False) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise AppError("not_found", "Dataset not found.", 404)
    require_workspace(db, user, dataset.workspace_id, write=write)
    return dataset


def record_activity(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user: User,
    action: str,
    resource_type: str,
    resource_id: str,
    context: dict,
) -> None:
    db.add(
        ActivityLog(
            workspace_id=workspace_id,
            user_id=user.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            context=context,
        )
    )
