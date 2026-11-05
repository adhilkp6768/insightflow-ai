from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.models import User


def client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        raise AppError("unauthorized", "Sign in is required.", 401)
    token = header.split(" ", 1)[1].strip()
    if not token:
        raise AppError("unauthorized", "Sign in is required.", 401)
    user_id = decode_access_token(token)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError("unauthorized", "Sign in is required.", 401)
    return user
