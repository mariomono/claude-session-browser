from fastapi import APIRouter

from app.api.v1.endpoints import health, sessions

# Versioned API surface, mounted under /api/v1 in app.main.
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sessions.router)
