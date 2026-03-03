# Repository Map

This is the source-of-truth map for where to edit each part of Asseri.

## Edit Zones

- `backend/`: API, AI logic, memory, safety, math, fuzzy understanding.
- `frontend/`: primary UI source files to edit.
- `docs/`: deployment mirror for GitHub Pages/Firebase.
- `backend/nlp/arabic/`: Arabic module zone (currently scaffold only).
- `config/`: runtime settings.
- `scripts/`: maintenance and operations helpers.

## Top-Level Files

- `main.py`: local app entrypoint (`python main.py`).
- `app.py`: Hugging Face Spaces entrypoint.
- `index.html`: root redirect to `docs/` for static hosting.
- `requirements.txt`: Python dependencies.

## Rules To Keep Structure Clean

1. Edit UI in `frontend/` first, then run sync to update `docs/`.
2. Keep deploy-specific files at root (`Dockerfile`, `firebase.json`, workflow yaml).
3. Keep generated data under `backend/data/` only.
4. Keep language expansion modules under `backend/nlp/`.
5. Do not implement Arabic runtime logic until Arabic phase is explicitly started.

## Sync Command

```bash
python scripts/sync_frontend_to_docs.py
```

## Arabic Start Command

When you are ready to begin coding Arabic logic, use:

`Start Arabic implementation phase 1`
