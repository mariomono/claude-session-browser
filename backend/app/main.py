"""FastAPI app: session index, transcript, resume and bookmark API."""

from fastapi import FastAPI

from app.api.v1.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(title="Claude Session Browser")
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
