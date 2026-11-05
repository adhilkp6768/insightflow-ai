import re
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    dummy_verify,
    generate_refresh_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.models import ActivityLog, RefreshToken, User, Workspace, WorkspaceMembership
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.utils.time import as_utc, utcnow


def _workspace_name(full_name: str) -> str:
    first = full_name.split()[0]
    return f"{first}'s workspace"[:120]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:40] or "workspace"


def _unique_slug(db: Session, full_name: str, email: str) -> str:
    base = _slugify(full_name)
    if base == "workspace":
        base = _slugify(email.split("@")[0])
    candidate = base
    suffix = 2
    while db.scalar(select(Workspace.id).where(Workspace.slug == candidate)) is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _log(
    db: Session,
    *,
    user_id,
    workspace_id,
    action: str,
    resource_type: str,
    resource_id,
    ip: str | None,
) -> None:
    db.add(
        ActivityLog(
            user_id=user_id,
            workspace_id=workspace_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            context={"ip": ip} if ip else {},
        )
    )


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    settings = get_settings()
    raw_refresh = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=utcnow() + timedelta(seconds=settings.jwt_refresh_ttl_seconds),
        )
    )
    db.flush()
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=raw_refresh,
        expires_in=settings.jwt_access_ttl_seconds,
        user=UserPublic.model_validate(user),
    )


def _primary_workspace_id(db: Session, user_id) -> object:
    membership = db.scalar(
        select(WorkspaceMembership)
        .where(WorkspaceMembership.user_id == user_id)
        .order_by(WorkspaceMembership.created_at)
    )
    return membership.workspace_id if membership else None


def register(db: Session, payload: RegisterRequest, ip: str | None) -> TokenResponse:
    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise AppError("email_taken", "An account with this email already exists.", 409)

    user = User(
        email=email, password_hash=hash_password(payload.password), full_name=payload.full_name
    )
    db.add(user)
    db.flush()

    workspace = Workspace(
        name=_workspace_name(payload.full_name),
        slug=_unique_slug(db, payload.full_name, email),
        owner_id=user.id,
    )
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role="owner"))
    from app.services.membership_service import accept_pending_invites

    accept_pending_invites(db, user)
    _log(
        db,
        user_id=user.id,
        workspace_id=workspace.id,
        action="auth.register",
        resource_type="user",
        resource_id=user.id,
        ip=ip,
    )
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def login(db: Session, payload: LoginRequest, ip: str | None) -> TokenResponse:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        dummy_verify(payload.password)
        raise AppError("invalid_credentials", "Invalid email or password.", 401)
    if not user.is_active or not verify_password(payload.password, user.password_hash):
        raise AppError("invalid_credentials", "Invalid email or password.", 401)
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    _log(
        db,
        user_id=user.id,
        workspace_id=_primary_workspace_id(db, user.id),
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        ip=ip,
    )
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def rotate_refresh_token(db: Session, raw_token: str) -> TokenResponse:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if row is None:
        raise AppError("invalid_refresh", "Refresh token is invalid.", 401)
    if row.revoked_at is not None:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == row.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        db.commit()
        raise AppError("invalid_refresh", "Refresh token is invalid.", 401)
    if as_utc(row.expires_at) <= utcnow():
        raise AppError("invalid_refresh", "Refresh token is invalid.", 401)

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise AppError("invalid_refresh", "Refresh token is invalid.", 401)

    row.revoked_at = utcnow()
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def logout(db: Session, user: User, raw_token: str, ip: str | None) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if row is None or row.user_id != user.id:
        raise AppError("invalid_refresh", "Refresh token is invalid.", 401)
    if row.revoked_at is None:
        row.revoked_at = utcnow()
    _log(
        db,
        user_id=user.id,
        workspace_id=_primary_workspace_id(db, user.id),
        action="auth.logout",
        resource_type="user",
        resource_id=user.id,
        ip=ip,
    )
    db.commit()
