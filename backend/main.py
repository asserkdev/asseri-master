from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import api_router, configure_app_state

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_FILE = BASE_DIR / "backend" / "data" / "memory.json"


def create_app(data_file: Path | None = None) -> FastAPI:
    app = FastAPI(title="Asseri Modular AI", version="2.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    configure_app_state(app, data_file or DATA_FILE)
    app.include_router(api_router, prefix="/api")

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    cloud_port = os.getenv("PORT")
    host = os.getenv("ASSERI_HOST", "0.0.0.0" if cloud_port else "127.0.0.1")
    port = int(cloud_port or os.getenv("ASSERI_PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=False, log_level="info")
