"""Report generation and download."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import AppError
from app.models import User
from app.services.report_service import REPORT_TYPES, create_report, get_report_file, list_reports

router = APIRouter()

MEDIA = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}


class ReportRequest(BaseModel):
    dataset_id: uuid.UUID
    report_type: str


@router.get("/workspaces/{workspace_id}/reports")
def reports(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_reports(db, user, workspace_id)


@router.post("/reports", status_code=201)
def generate_report(
    body: ReportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if body.report_type not in REPORT_TYPES:
        raise AppError("unknown_report", "Choose a supported report type.", 422)
    return create_report(db, user, body.dataset_id, body.report_type)


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: uuid.UUID,
    file_format: str = "pdf",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        path, filename = get_report_file(db, user, report_id, file_format)
    except ValueError as exc:
        raise AppError("not_found", "Report file not found.", 404) from exc
    return FileResponse(path, media_type=MEDIA.get(file_format, "application/octet-stream"), filename=filename)
