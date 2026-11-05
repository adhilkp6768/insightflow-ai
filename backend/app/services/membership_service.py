"""Invite people into a workspace and change their roles."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import User, WorkspaceInvite, WorkspaceMembership
from app.services.access import record_activity, require_workspace
from app.utils.time import utcnow

ASSIGNABLE = {"admin", "analyst", "viewer"}
MANAGERS = {"owner", "admin"}


def _managers_only(membership: WorkspaceMembership) -> None:
    if membership.role not in MANAGERS:
        raise AppError("forbidden", "Only an owner or admin can manage members.", 403)


def _owner_count(db: Session, workspace_id: uuid.UUID) -> int:
    count = db.scalar(
        select(func.count())
        .select_from(WorkspaceMembership)
        .where(WorkspaceMembership.workspace_id == workspace_id, WorkspaceMembership.role == "owner")
    )
    return int(count or 0)


def _member_payload(user: User, membership: WorkspaceMembership) -> dict:
    return {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": membership.role,
        "created_at": membership.created_at.isoformat(),
    }


def _invite_payload(invite: WorkspaceInvite) -> dict:
    return {
        "id": str(invite.id),
        "email": invite.email,
        "role": invite.role,
        "status": invite.status,
        "created_at": invite.created_at.isoformat(),
    }


def list_members(db: Session, user: User, workspace_id: uuid.UUID) -> dict:
    require_workspace(db, user, workspace_id)
    rows = db.execute(
        select(User, WorkspaceMembership)
        .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
        .where(WorkspaceMembership.workspace_id == workspace_id)
        .order_by(WorkspaceMembership.created_at)
    ).all()
    invites = db.scalars(
        select(WorkspaceInvite)
        .where(WorkspaceInvite.workspace_id == workspace_id, WorkspaceInvite.status == "pending")
        .order_by(WorkspaceInvite.created_at.desc())
    ).all()
    return {
        "members": [_member_payload(member, membership) for member, membership in rows],
        "invites": [_invite_payload(invite) for invite in invites],
    }


def invite_member(db: Session, user: User, workspace_id: uuid.UUID, email: str, role: str) -> dict:
    membership = require_workspace(db, user, workspace_id)
    _managers_only(membership)
    if role not in ASSIGNABLE:
        raise AppError("invalid_role", "Invite an admin, analyst, or viewer.", 422)
    if role == "admin" and membership.role != "owner":
        raise AppError("forbidden", "Only an owner can invite an admin.", 403)
    normalized = email.lower().strip()
    if normalized == user.email:
        raise AppError("invalid_invite", "You are already in this workspace.", 422)
    existing_user = db.scalar(select(User).where(User.email == normalized))
    if existing_user is not None:
        already = db.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == existing_user.id,
            )
        )
        if already is not None:
            raise AppError("already_member", "That person is already in this workspace.", 409)
        db.add(WorkspaceMembership(workspace_id=workspace_id, user_id=existing_user.id, role=role))
        db.add(
            WorkspaceInvite(
                workspace_id=workspace_id,
                email=normalized,
                role=role,
                status="accepted",
                invited_by=user.id,
                accepted_at=utcnow(),
            )
        )
        record_activity(
            db,
            workspace_id=workspace_id,
            user=user,
            action="member.added",
            resource_type="user",
            resource_id=str(existing_user.id),
            context={"email": normalized, "role": role},
        )
        db.commit()
        return list_members(db, user, workspace_id)
    pending = db.scalar(
        select(WorkspaceInvite).where(
            WorkspaceInvite.workspace_id == workspace_id,
            WorkspaceInvite.email == normalized,
            WorkspaceInvite.status == "pending",
        )
    )
    if pending is None:
        pending = WorkspaceInvite(
            workspace_id=workspace_id,
            email=normalized,
            role=role,
            status="pending",
            invited_by=user.id,
        )
        db.add(pending)
    else:
        pending.role = role
    record_activity(
        db,
        workspace_id=workspace_id,
        user=user,
        action="member.invited",
        resource_type="invite",
        resource_id=normalized,
        context={"email": normalized, "role": role},
    )
    db.commit()
    return list_members(db, user, workspace_id)


def update_role(db: Session, user: User, workspace_id: uuid.UUID, member_id: uuid.UUID, role: str) -> dict:
    actor = require_workspace(db, user, workspace_id)
    _managers_only(actor)
    if role not in {"owner", "admin", "analyst", "viewer"}:
        raise AppError("invalid_role", "Choose owner, admin, analyst, or viewer.", 422)
    if role == "owner" and actor.role != "owner":
        raise AppError("forbidden", "Only an owner can grant ownership.", 403)
    if role == "admin" and actor.role != "owner":
        raise AppError("forbidden", "Only an owner can grant the admin role.", 403)
    target = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == member_id,
        )
    )
    if target is None:
        raise AppError("not_found", "That person is not in this workspace.", 404)
    if actor.role == "admin" and target.role in {"owner", "admin"}:
        raise AppError("forbidden", "An admin cannot change an owner or another admin.", 403)
    if target.role == "owner" and role != "owner" and _owner_count(db, workspace_id) <= 1:
        raise AppError("last_owner", "The workspace needs at least one owner.", 422)
    target.role = role
    record_activity(
        db,
        workspace_id=workspace_id,
        user=user,
        action="member.role_changed",
        resource_type="user",
        resource_id=str(member_id),
        context={"role": role},
    )
    db.commit()
    return list_members(db, user, workspace_id)


def remove_member(db: Session, user: User, workspace_id: uuid.UUID, member_id: uuid.UUID) -> dict:
    actor = require_workspace(db, user, workspace_id)
    target = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == member_id,
        )
    )
    if target is None:
        raise AppError("not_found", "That person is not in this workspace.", 404)
    removing_self = member_id == user.id
    if not removing_self:
        _managers_only(actor)
        if actor.role == "admin" and target.role in {"owner", "admin"}:
            raise AppError("forbidden", "An admin cannot remove an owner or another admin.", 403)
    if target.role == "owner" and _owner_count(db, workspace_id) <= 1:
        raise AppError("last_owner", "The workspace needs at least one owner.", 422)
    db.delete(target)
    record_activity(
        db,
        workspace_id=workspace_id,
        user=user,
        action="member.removed",
        resource_type="user",
        resource_id=str(member_id),
        context={"self": removing_self},
    )
    db.commit()
    if removing_self:
        return {"members": [], "invites": []}
    return list_members(db, user, workspace_id)


def revoke_invite(db: Session, user: User, workspace_id: uuid.UUID, invite_id: uuid.UUID) -> dict:
    membership = require_workspace(db, user, workspace_id)
    _managers_only(membership)
    invite = db.get(WorkspaceInvite, invite_id)
    if invite is None or invite.workspace_id != workspace_id or invite.status != "pending":
        raise AppError("not_found", "That invitation is not pending.", 404)
    invite.status = "revoked"
    db.commit()
    return list_members(db, user, workspace_id)


def accept_pending_invites(db: Session, user: User) -> None:
    invites = db.scalars(
        select(WorkspaceInvite).where(
            WorkspaceInvite.email == user.email,
            WorkspaceInvite.status == "pending",
        )
    ).all()
    for invite in invites:
        already = db.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == invite.workspace_id,
                WorkspaceMembership.user_id == user.id,
            )
        )
        if already is None and invite.role in ASSIGNABLE:
            db.add(WorkspaceMembership(workspace_id=invite.workspace_id, user_id=user.id, role=invite.role))
        invite.status = "accepted"
        invite.accepted_at = utcnow()
