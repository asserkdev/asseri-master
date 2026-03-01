from __future__ import annotations

import os

import uvicorn


def run() -> None:
    cloud_port = os.getenv("PORT")
    host = os.getenv("ASSERI_HOST", "0.0.0.0" if cloud_port else "127.0.0.1")
    port = int(cloud_port or os.getenv("ASSERI_PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    run()
