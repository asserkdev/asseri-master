from __future__ import annotations

import os

import uvicorn

from backend.main import app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False, log_level="info")
