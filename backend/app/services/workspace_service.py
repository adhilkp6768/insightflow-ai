from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import User, Workspace, WorkspaceMembership
from app.schemas.workspace import WorkspaceResponse


def list_workspaces(db: Session, user: User) -> list[WorkspaceResponse]:
    rows = db.execute(
        select(Workspace, WorkspaceMembership.role)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user.id)
        .order_by(Workspace.created_at)
    ).all()
    return [
        WorkspaceResponse(id=workspace.id, name=workspace.name, slug=workspace.slug, role=role)
        for workspace, role in rows
    ]


def get_workspace(db: Session, user: User, workspace_id: UUID) -> WorkspaceResponse:
    row = db.execute(
        select(Workspace, WorkspaceMembership.role)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(Workspace.id == workspace_id, WorkspaceMembership.user_id == user.id)
    ).one_or_none()
    if row is None:
        raise AppError("not_found", "Workspace not found.", 404)
    workspace, role = row
    return WorkspaceResponse(id=workspace.id, name=workspace.name, slug=workspace.slug, role=role)
