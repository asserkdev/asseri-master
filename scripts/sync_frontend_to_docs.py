from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DOCS = ROOT / "docs"

# Keep this list explicit so deployment assets are controlled and predictable.
SYNC_FILES = [
    "index.html",
    "style.css",
    "app.js",
    "firebase-init.js",
    "logo.svg",
]


def sync_frontend_to_docs() -> None:
    missing = [name for name in SYNC_FILES if not (FRONTEND / name).exists()]
    if missing:
        names = ", ".join(missing)
        raise FileNotFoundError(f"Missing frontend files: {names}")

    DOCS.mkdir(parents=True, exist_ok=True)
    for name in SYNC_FILES:
        source = FRONTEND / name
        destination = DOCS / name
        shutil.copy2(source, destination)
        print(f"Synced: {source} -> {destination}")

    nojekyll = DOCS / ".nojekyll"
    if not nojekyll.exists():
        nojekyll.write_text("", encoding="utf-8")
        print(f"Created: {nojekyll}")


if __name__ == "__main__":
    sync_frontend_to_docs()
