"""Grounded analytics assistant."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.services.assistant_service import answer_question

router = APIRouter()


class AssistantRequest(BaseModel):
    dataset_id: uuid.UUID
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None
    date_from: str | None = None
    date_to: str | None = None


@router.post("/assistant/messages")
def ask(
    body: AssistantRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return answer_question(
        db,
        user,
        dataset_id=body.dataset_id,
        question=body.question,
        conversation_id=body.conversation_id,
        date_from=body.date_from,
        date_to=body.date_to,
    )
