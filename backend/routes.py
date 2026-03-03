from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .ai_core import AICore
from .auth_store import AuthStore
from .compute_engine import ComputeEngine
from .fuzzy_match import FuzzyMatcher
from .math_engine import MathEngine
from .memory import MemoryStore
from .runtime_config import load_runtime_config
from .search_module import SearchModule


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class SessionActionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)


class FeedbackRequest(BaseModel):
    session_id: str | None = None
    topic: str | None = None
    signal: str = Field(min_length=2, max_length=8)
    note: str | None = Field(default=None, max_length=280)


class TagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)


class PinRequest(BaseModel):
    message_index: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=240)


class ChatResponse(BaseModel):
    user_id: str | None = None
    session_id: str
    answer: str
    intent: str
    confidence: int
    references: list[dict[str, str]]
    fuzzy_corrections: list[dict[str, str]]
    reflection_steps: list[str] | None = None
    topic: str | None = None
    related_concepts: list[dict[str, Any]] | None = None


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=256)


class AuthResponse(BaseModel):
    ok: bool
    user_id: str | None = None
    token: str | None = None
    expires_at: str | None = None
    message: str | None = None


api_router = APIRouter()
logger = logging.getLogger(__name__)


def _max_message_chars() -> int:
    raw = os.getenv("ASSERI_MAX_MESSAGE_CHARS", "0").strip()
    try:
        val = int(raw)
    except Exception:
        return 0
    return max(0, val)


def _resolved_max_message_chars(request: Request) -> int:
    env_value = _max_message_chars()
    if env_value > 0:
        return env_value
    cfg = getattr(request.app.state, "runtime_config", {})
    app_cfg = cfg.get("app", {}) if isinstance(cfg, dict) else {}
    try:
        return max(0, int(app_cfg.get("max_message_chars", 0)))
    except Exception:
        return 0


def _extract_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    x_token = request.headers.get("x-auth-token", "").strip()
    if x_token:
        return x_token
    query_token = request.query_params.get("token", "").strip()
    if query_token:
        return query_token
    return ""


def _is_feedback_like_text(text: str) -> bool:
    low = str(text or "").strip().lower()
    if not low:
        return True
    if low in {"correct", "right", "exactly", "yes correct", "wrong", "also wrong", "still wrong"}:
        return True
    if "answer is " in low:
        return True
    if any(k in low for k in ["that is wrong", "this is wrong", "incorrect", "correct answer is"]):
        return True
    return False


def _last_substantive_user_message(memory: MemoryStore, session_id: str, user_id: str) -> str:
    history = memory.get_history(session_id, user_id=user_id)
    for msg in reversed(history):
        if str(msg.get("role", "")).lower() != "user":
            continue
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if _is_feedback_like_text(content):
            continue
        return content
    return ""


def _safe_chat(ai: AICore, memory: MemoryStore, message: str, session_id: str | None, user_id: str) -> ChatResponse:
    try:
        result = ai.handle_message(message, session_id, user_id=user_id)
        safe_session = str(result.get("session_id") or memory.ensure_session(session_id, user_id=user_id))
        refs_raw = result.get("references")
        refs = refs_raw if isinstance(refs_raw, list) else []
        conf_raw = result.get("confidence")
        conf = int(conf_raw) if isinstance(conf_raw, (int, float)) else None
        intent = str(result.get("intent", "")).strip() or None
        topic = str(result.get("topic", "")).strip() or None
        memory.annotate_last_assistant_message(
            safe_session,
            user_id=user_id,
            references=refs,
            confidence=conf,
            intent=intent,
            topic=topic,
        )
        result["session_id"] = safe_session
        result["user_id"] = user_id
        return ChatResponse(**result)
    except Exception as exc:
        logger.exception("Chat handling failed: %s", exc)
        safe_session = memory.ensure_session(session_id, user_id=user_id)
        fallback = {
            "user_id": user_id,
            "session_id": safe_session,
            "answer": (
                "I encountered an internal error while processing that input. "
                "Please rephrase or try again with more detail.\n"
                "I'm 25% sure this is correct.\n"
                "Confidence: 25%"
            ),
            "intent": "error",
            "confidence": 25,
            "references": [{"title": "Internal Error Handler", "url": "internal://error-handler"}],
            "fuzzy_corrections": [],
            "reflection_steps": ["Global safety handler intercepted an exception."],
            "topic": "error",
            "related_concepts": [],
        }
        memory.append_message(
            safe_session,
            "assistant",
            fallback["answer"],
            user_id=user_id,
            references=fallback["references"],
            confidence=int(fallback["confidence"]),
            intent=str(fallback["intent"]),
            topic=str(fallback["topic"]),
        )
        return ChatResponse(**fallback)


def _require_user_id(request: Request) -> str:
    auth: AuthStore = request.app.state.auth_store
    token = _extract_token(request)
    user_id = auth.validate_session(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")
    return user_id


def configure_app_state(app: FastAPI, data_file: Path) -> None:
    base_dir = data_file.parent.parent.parent
    runtime_config = load_runtime_config(base_dir)
    memory = MemoryStore(data_file)
    fuzzy = FuzzyMatcher()
    compute_engine = ComputeEngine(config=runtime_config.get("compute", {}))
    math_engine = MathEngine(compute_engine=compute_engine)
    search = SearchModule()
    auth_store = AuthStore(data_file.parent / "auth.json")
    app.state.ai_core = AICore(memory=memory, search=search, math_engine=math_engine, fuzzy=fuzzy)
    app.state.memory = memory
    app.state.auth_store = auth_store
    app.state.runtime_config = runtime_config
    app.state.compute_engine = compute_engine


@api_router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@api_router.get("/system/capabilities")
def system_capabilities(request: Request) -> dict[str, Any]:
    compute: ComputeEngine = request.app.state.compute_engine
    runtime_config: dict[str, Any] = request.app.state.runtime_config
    return {
        "app": runtime_config.get("app", {}),
        "compute": compute.capabilities(),
        "learning": runtime_config.get("learning", {}),
    }


@api_router.post("/auth/register", response_model=AuthResponse)
def auth_register(payload: AuthRequest, request: Request) -> AuthResponse:
    auth: AuthStore = request.app.state.auth_store
    ok, message = auth.register_user(payload.username, payload.password)
    if not ok:
        raise HTTPException(status_code=400, detail=message)

    logged_in, token, expires_at, user_id = auth.login(payload.username, payload.password)
    if not logged_in:
        raise HTTPException(status_code=500, detail="Account was created but login failed.")
    return AuthResponse(ok=True, user_id=user_id, token=token, expires_at=expires_at, message="Registered successfully.")


@api_router.post("/auth/login", response_model=AuthResponse)
def auth_login(payload: AuthRequest, request: Request) -> AuthResponse:
    auth: AuthStore = request.app.state.auth_store
    ok, token, expires_at, user_id = auth.login(payload.username, payload.password)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return AuthResponse(ok=True, user_id=user_id, token=token, expires_at=expires_at, message="Signed in.")


@api_router.post("/auth/logout", response_model=AuthResponse)
def auth_logout(request: Request) -> AuthResponse:
    auth: AuthStore = request.app.state.auth_store
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")
    auth.logout(token)
    return AuthResponse(ok=True, message="Signed out.")


@api_router.get("/auth/me", response_model=AuthResponse)
def auth_me(request: Request) -> AuthResponse:
    user_id = _require_user_id(request)
    return AuthResponse(ok=True, user_id=user_id, message="Authenticated.")


@api_router.get("/sessions")
def list_sessions(request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    return {"user_id": resolved, "sessions": memory.list_sessions(user_id=resolved)}


@api_router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    if not memory.session_exists(session_id, user_id=resolved):
        raise HTTPException(status_code=404, detail="Session not found.")
    history = memory.get_history(session_id, user_id=resolved)
    return {
        "user_id": resolved,
        "session_id": session_id,
        "history": history,
        "tags": memory.get_session_tags(session_id, user_id=resolved),
        "pins": memory.list_pins(session_id, user_id=resolved),
    }


@api_router.delete("/sessions/{session_id}")
def delete_session(session_id: str, request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    deleted = memory.delete_session(session_id, user_id=resolved)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"ok": True, "user_id": resolved, "deleted_session_id": session_id}


@api_router.post("/sessions/{session_id}/restore")
def restore_session(session_id: str, request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    restored = memory.restore_session(session_id, user_id=resolved)
    if not restored:
        raise HTTPException(status_code=404, detail="Deleted session not found.")
    return {"ok": True, "user_id": resolved, "restored_session_id": session_id}


@api_router.get("/learning/overview")
def learning_overview(request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    return {"user_id": resolved, **memory.learning_overview(limit=12, user_id=resolved)}


@api_router.get("/learning/rules/{topic}")
def learning_rule(topic: str, request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    normalized = memory.topic_key(topic)
    payload = memory.get_rule(normalized, user_id=resolved)
    if not payload:
        raise HTTPException(status_code=404, detail="Rule not found.")
    return {"user_id": resolved, "topic": normalized, "rule": payload}


@api_router.get("/graph/{topic}")
def graph_neighbors(topic: str, request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    normalized = memory.topic_key(topic)
    return {"user_id": resolved, "topic": normalized, "neighbors": memory.graph_neighbors(normalized, limit=12, user_id=resolved)}


@api_router.get("/learning/decisions")
def learning_decisions(request: Request, limit: int = 20) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    safe_limit = max(1, min(limit, 100))
    return {"user_id": resolved, "decisions": memory.recent_decisions(limit=safe_limit, user_id=resolved)}


@api_router.get("/profile")
def user_profile(request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    return {"user_id": resolved, "profile": memory.user_profile(user_id=resolved)}


@api_router.get("/chat/suggestions")
def chat_suggestions(request: Request) -> dict[str, Any]:
    resolved = _require_user_id(request)
    suggestions = [
        "Explain artificial intelligence in simple terms.",
        "Solve 2x + 7 = 19 step by step.",
        "What do you remember about me?",
        "Give me 3 project ideas with Python and FastAPI.",
        "Compare machine learning vs deep learning.",
        "How can I improve this code for performance?",
        "What is the capital of Japan and a short fact?",
    ]
    return {"user_id": resolved, "suggestions": suggestions}


@api_router.get("/sessions/{session_id}/export")
def export_session(session_id: str, request: Request, fmt: str = "markdown") -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    if not memory.session_exists(session_id, user_id=resolved):
        raise HTTPException(status_code=404, detail="Session not found.")
    history = memory.get_history(session_id, user_id=resolved)
    mode = fmt.strip().lower()

    if mode == "json":
        return {"user_id": resolved, "session_id": session_id, "format": "json", "content": history}

    lines = [f"# Session {session_id}", ""]
    for msg in history:
        role = str(msg.get("role", "assistant")).upper()
        stamp = str(msg.get("timestamp", "")).strip()
        content = str(msg.get("content", "")).strip()
        lines.append(f"## {role} [{stamp}]")
        lines.append(content)
        lines.append("")
    return {"user_id": resolved, "session_id": session_id, "format": "markdown", "content": "\n".join(lines).strip()}


@api_router.get("/sessions/{session_id}/search")
def search_session(session_id: str, request: Request, q: str, limit: int = 20) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    if not memory.session_exists(session_id, user_id=resolved):
        raise HTTPException(status_code=404, detail="Session not found.")
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
    safe_limit = max(1, min(limit, 100))
    results = memory.search_session_messages(session_id, query, limit=safe_limit, user_id=resolved)
    return {
        "user_id": resolved,
        "session_id": session_id,
        "query": query,
        "count": len(results),
        "results": results,
    }


@api_router.post("/sessions/{session_id}/tags")
def set_session_tags(session_id: str, payload: TagsRequest, request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    if not memory.session_exists(session_id, user_id=resolved):
        raise HTTPException(status_code=404, detail="Session not found.")
    tags = memory.set_session_tags(session_id, payload.tags, user_id=resolved)
    return {"ok": True, "user_id": resolved, "session_id": session_id, "tags": tags}


@api_router.get("/sessions/{session_id}/pins")
def list_pins(session_id: str, request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    if not memory.session_exists(session_id, user_id=resolved):
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"user_id": resolved, "session_id": session_id, "pins": memory.list_pins(session_id, user_id=resolved)}


@api_router.post("/sessions/{session_id}/pins")
def pin_message(session_id: str, payload: PinRequest, request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    if not memory.session_exists(session_id, user_id=resolved):
        raise HTTPException(status_code=404, detail="Session not found.")
    pinned = memory.pin_message(
        session_id=session_id,
        message_index=payload.message_index,
        note=payload.note or "",
        user_id=resolved,
    )
    if not pinned:
        raise HTTPException(status_code=400, detail="Unable to pin message index.")
    return {"ok": True, "user_id": resolved, "session_id": session_id, "pin": pinned}


@api_router.delete("/sessions/{session_id}/pins/{message_index}")
def unpin_message(session_id: str, message_index: int, request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    if not memory.session_exists(session_id, user_id=resolved):
        raise HTTPException(status_code=404, detail="Session not found.")
    if message_index < 0:
        raise HTTPException(status_code=400, detail="message_index must be >= 0.")
    removed = memory.unpin_message(session_id=session_id, message_index=message_index, user_id=resolved)
    if not removed:
        raise HTTPException(status_code=404, detail="Pin not found for this message index.")
    return {"ok": True, "user_id": resolved, "session_id": session_id, "message_index": message_index}


@api_router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    ai: AICore = request.app.state.ai_core
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    max_chars = _resolved_max_message_chars(request)
    if max_chars > 0 and len(payload.message) > max_chars:
        raise HTTPException(status_code=413, detail=f"Message too long. Maximum allowed is {max_chars} characters.")
    return _safe_chat(ai=ai, memory=memory, message=payload.message, session_id=payload.session_id, user_id=resolved)


@api_router.post("/chat/regenerate", response_model=ChatResponse)
def chat_regenerate(payload: SessionActionRequest, request: Request) -> ChatResponse:
    ai: AICore = request.app.state.ai_core
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    if not memory.session_exists(payload.session_id, user_id=resolved):
        raise HTTPException(status_code=404, detail="Session not found.")
    seed = _last_substantive_user_message(memory, payload.session_id, resolved)
    if not seed:
        raise HTTPException(status_code=400, detail="No previous user question available to regenerate.")
    return _safe_chat(ai=ai, memory=memory, message=seed, session_id=payload.session_id, user_id=resolved)


@api_router.post("/chat/continue", response_model=ChatResponse)
def chat_continue(payload: SessionActionRequest, request: Request) -> ChatResponse:
    ai: AICore = request.app.state.ai_core
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    if not memory.session_exists(payload.session_id, user_id=resolved):
        raise HTTPException(status_code=404, detail="Session not found.")
    seed = _last_substantive_user_message(memory, payload.session_id, resolved)
    if not seed:
        raise HTTPException(status_code=400, detail="No previous user question available to continue.")
    low = seed.lower()
    if any(k in low for k in ["solve", "equation", "integrate", "differentiate"]) or any(op in low for op in ["+", "-", "*", "/", "^", "="]):
        prompt = f"show another step-by-step method for: {seed}"
    else:
        prompt = f"continue with more detail, examples, and clearer explanation about: {seed}"
    return _safe_chat(ai=ai, memory=memory, message=prompt, session_id=payload.session_id, user_id=resolved)


@api_router.post("/chat/feedback")
def chat_feedback(payload: FeedbackRequest, request: Request) -> dict[str, Any]:
    memory: MemoryStore = request.app.state.memory
    resolved = _require_user_id(request)
    signal = payload.signal.strip().lower()
    if signal not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="Feedback signal must be 'up' or 'down'.")
    if not payload.session_id:
        raise HTTPException(status_code=400, detail="session_id is required for feedback.")
    if not memory.session_exists(payload.session_id, user_id=resolved):
        raise HTTPException(status_code=404, detail="Session not found.")

    seed = payload.topic or _last_substantive_user_message(memory, payload.session_id, resolved) or "general"
    topic = memory.topic_key(seed)
    memory.record_feedback(payload.session_id, topic, signal, note=payload.note or "", user_id=resolved)

    if signal == "up":
        memory.update_topic_stats(topic, "confirmations", user_id=resolved)
        memory.adjust_rule_confidence(topic, +0.04, user_id=resolved)
    else:
        memory.update_topic_stats(topic, "corrections", user_id=resolved)
        memory.update_topic_stats(topic, "mistakes", user_id=resolved)
        memory.bump_pattern(topic, mistake=True, user_id=resolved)
        memory.adjust_rule_confidence(topic, -0.08, user_id=resolved)

    return {"ok": True, "user_id": resolved, "session_id": payload.session_id, "topic": topic, "signal": signal}
