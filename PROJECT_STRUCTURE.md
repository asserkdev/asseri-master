# Clean Project Structure

This document defines the clean structure of the repository and what each folder owns.

## Top Level

- `backend/`: Python API, AI orchestration, learning, reasoning, memory.
- `frontend/`: development source for the web UI.
- `docs/`: deploy-ready static frontend for GitHub Pages/Firebase hosting.
- `config/`: runtime/system configuration.
- `scripts/`: run/eval/deploy helper scripts.

## Backend Ownership

- `backend/main.py`, `backend/routes.py`: API entry and route layer.
- `backend/ai_core.py`: central orchestration brain.
- `backend/math_engine.py`, `backend/compute_engine.py`: math and compute execution.
- `backend/fuzzy_match.py`: fuzzy understanding for English + correction pipeline.
- `backend/memory.py`: persistent per-user/session memory.
- `backend/search_module.py`: web retrieval and summarization.
- `backend/human_layer.py`: tone/safety/style behavior.
- `backend/query_planner.py`, `backend/accuracy_policy.py`: routing and confidence policy.
- `backend/auth_store.py`: account/session auth state.

## Arabic Expansion Zone (Scaffold Only)

- `backend/nlp/arabic/`: reserved for Arabic understanding module.
- Files are intentionally scaffold-only for now (no Arabic logic yet).

## Frontend Ownership

- `frontend/`: editable source.
- `docs/`: deploy mirror.

Rule:
-- UI behavior changes should be made in `frontend/` first, then synced to `docs/` for hosting.

## Current Priority Order

1. Keep core English system stable.
2. Complete Arabic design scaffold.
3. Implement Arabic normalization/fuzzy/grammar in dedicated module files.
4. Integrate Arabic routing into `ai_core` after module tests pass.

## Maintenance Workflow

1. Edit web UI in `frontend/`.
2. Run `python scripts/sync_frontend_to_docs.py`.
3. Commit both `frontend/` and `docs/` changes together.
4. Keep Arabic files scaffold-only until you trigger the Arabic phase.
