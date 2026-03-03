---
title: Asseri AI
emoji: "🤖"
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---
# Asseri Modular AI System

Clean modular AI architecture with separate frontend/backend and optional acceleration layers.

## Project Structure

```text
asseri/
  .github/workflows/deploy-pages.yml
  backend/
    main.py
    routes.py
    ai_core.py
    accuracy_policy.py
    query_planner.py          # Route planner (clarify/internal/web/hybrid)
    search_module.py
    math_engine.py
    compute_engine.py          # Python/NumPy/Torch-CUDA compute router
    fuzzy_match.py
    human_layer.py
    memory.py
    auth_store.py
    runtime_config.py          # YAML/JSON config loader + env overrides
    train.py                   # Offline training/analytics script
    native/
      cpp/matmul_kernel.cpp    # C++ kernel scaffold
      cuda/matmul_kernel.cu    # CUDA kernel scaffold
      README.md
    data/
  config/
    system.yaml                # Runtime config (app/compute/learning)
  frontend/
    index.html
    style.css
    app.js
  docs/
    index.html
    style.css
    app.js
  scripts/
    run_backend.sh
    train_model.sh
    build_native.sh
  main.py
  requirements.txt
  render.yaml
  README.md
```

## Core Features

- Per-user accounts and isolated chat/session memory
- Intent routing (`math`, `knowledge`, `problem_solving`, `casual`)
- Internal math/logic engine with step-by-step answers
- Online search integration with relevance/trust filtering
- Query planning to choose clarify vs internal vs web/hybrid route
- Fuzzy text understanding and typo correction
- Safe correction-based learning with confidence tracking
- Similar-experience memory retrieval for closer repeated answers
- Contradiction-aware memory retrieval (respects later corrections)
- Ambiguous entity disambiguation prompts (e.g., python/java/apple)
- Internal propositional logic handling (modus ponens-style queries)
- Multi-hop reasoning for comparison-style prompts
- Consensus voting across internal/memory/web candidates
- Self-critique second-pass repair for low-confidence/fact-check turns
- Strict fact-check mode via query phrasing (`verify`, `fact check`, `double check`)
- Confidence score and references on each answer
- Decision logging and learning overview endpoints
- Optional compute acceleration path (Torch CUDA -> NumPy -> Python)

## Tech Stack Added

- Python: backend APIs, orchestration, AI logic
- C++: native compute scaffold (extensible)
- CUDA/CUDA C: GPU kernel scaffold (extensible)
- Bash: orchestration scripts (`scripts/`)
- YAML/JSON: centralized runtime config

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start backend:

```bash
python main.py
```

3. Open app:

```bash
http://127.0.0.1:8000
```

## Config

Default runtime config lives in:

- `config/system.yaml`

Environment variable overrides still work, for example:

- `ASSERI_MAX_MESSAGE_CHARS`
- `ASSERI_PREFER_GPU`
- `ASSERI_AUTH_SESSION_HOURS`

## Scripts

- `bash scripts/run_backend.sh`
- `bash scripts/train_model.sh`
- `bash scripts/build_native.sh`
- `bash scripts/run_quality_eval.sh`

Quality benchmark output is written to:

- `backend/data/quality_report.json`

## API Endpoints

- `GET /api/health`
- `GET /api/system/capabilities`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/chat`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`
- `DELETE /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/restore`
- `GET /api/learning/overview`
- `GET /api/learning/rules/{topic}`
- `GET /api/graph/{topic}`
- `GET /api/learning/decisions?limit=20`

## Deploy

GitHub Pages and Firebase Hosting serve only static frontend. Python backend must run on an API host (Cloud Run/Render/Fly/VM).

- GitHub Pages URL: `https://asserkdev.github.io/asseri-master/`
- Firebase Hosting URL: `https://asseri-1.web.app`
- Current backend URL: `https://asserk-asseri.hf.space`
- Optional override: pass `?api=<custom-backend-url>` in the query string.

### Firebase Hosting (Configured)

Project:
- Project ID: `asseri-1`
- Site: `asseri-1`

Files added:
- `.firebaserc`
- `firebase.json`
- `frontend/firebase-init.js`
- `docs/firebase-init.js`

Deploy commands:

```bash
npm install -g firebase-tools
firebase login
firebase use asseri-1
firebase deploy --only hosting
```

If you move backend from Hugging Face Spaces to another host, set your API URL in:
- `frontend/firebase-init.js` -> `firebaseApiBase`
- `docs/firebase-init.js` -> `firebaseApiBase`

### Hugging Face Spaces (No Card Path)

This repo now includes:
- `Dockerfile`
- `.dockerignore`

Steps:
1. In Hugging Face, create a new **Space** with SDK = **Docker**.
2. In terminal, authenticate:

```bash
pip install -U huggingface_hub
huggingface-cli login
```

3. Add Space git remote and push:

```bash
git remote add hf https://huggingface.co/spaces/<YOUR_USERNAME>/<YOUR_SPACE_NAME>
git push hf main
```

Notes:
- Space runs on port `7860` automatically via `Dockerfile`.
- This app serves frontend + backend from the same host in Spaces, so no `?api=` override is required there.

