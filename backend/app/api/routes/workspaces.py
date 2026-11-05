from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.workspace import WorkspaceResponse
from app.services import membership_service, workspace_service

router = APIRouter()


def list_workspaces(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WorkspaceResponse]:
    return workspace_service.list_workspaces(db, user)


router.add_api_route("", list_workspaces, methods=["GET"], response_model=list[WorkspaceResponse])
router.add_api_route(
    "/",
    list_workspaces,
    methods=["GET"],
    response_model=list[WorkspaceResponse],
    include_in_schema=False,
)


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="analyst")


class RoleRequest(BaseModel):
    role: str


@router.get("/{workspace_id}/members")
def list_members(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return membership_service.list_members(db, user, workspace_id)


@router.post("/{workspace_id}/members")
def invite_member(
    workspace_id: UUID,
    body: InviteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return membership_service.invite_member(db, user, workspace_id, body.email, body.role)


@router.patch("/{workspace_id}/members/{member_id}")
def update_member(
    workspace_id: UUID,
    member_id: UUID,
    body: RoleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return membership_service.update_role(db, user, workspace_id, member_id, body.role)


@router.delete("/{workspace_id}/members/{member_id}")
def remove_member(
    workspace_id: UUID,
    member_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return membership_service.remove_member(db, user, workspace_id, member_id)


@router.delete("/{workspace_id}/invites/{invite_id}")
def revoke_invite(
    workspace_id: UUID,
    invite_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return membership_service.revoke_invite(db, user, workspace_id, invite_id)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkspaceResponse:
    return workspace_service.get_workspace(db, user, workspace_id)
