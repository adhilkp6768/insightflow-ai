from fastapi import APIRouter

from app.api.routes import assistant, auth, datasets, health, reports, workspaces

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(datasets.router, tags=["datasets"])
api_router.include_router(reports.router, tags=["reports"])
api_router.include_router(assistant.router, tags=["assistant"])
