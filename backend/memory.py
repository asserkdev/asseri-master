from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class MemoryStore:
    """Persistent per-user memory: sessions, learning stats, and knowledge graph."""

    DEFAULT_USER_ID = "local_user"

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.data = self._load()

    @staticmethod
    def _default_user_state() -> dict[str, Any]:
        return {
            "sessions": {},
            "deleted_sessions": {},
            "experiences": [],
            "decision_logs": [],
            "rules": {},
            "user_facts": {},
            "topic_stats": {},
            "topic_weights": {},
            "question_patterns": {},
            "mistake_patterns": {},
            "corrections": [],
            "confirmations": [],
            "message_feedback": [],
            "knowledge_graph": {"nodes": {}, "edges": {}},
        }

    @classmethod
    def _default(cls) -> dict[str, Any]:
        return {"users": {cls.DEFAULT_USER_ID: cls._default_user_state()}}

    @staticmethod
    def _merge_user_state(raw: Any) -> dict[str, Any]:
        base = MemoryStore._default_user_state()
        source = raw if isinstance(raw, dict) else {}
        merged: dict[str, Any] = {}
        for key, default in base.items():
            value = source.get(key, default) if isinstance(source, dict) else default
            if isinstance(default, dict):
                merged[key] = dict(value) if isinstance(value, dict) else dict(default)
            elif isinstance(default, list):
                merged[key] = list(value) if isinstance(value, list) else list(default)
            else:
                merged[key] = value
        return merged

    @classmethod
    def _normalize_user_id(cls, user_id: str | None) -> str:
        if not user_id:
            return cls.DEFAULT_USER_ID
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", user_id.strip())
        if not cleaned:
            return cls.DEFAULT_USER_ID
        return cleaned[:64]

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    if isinstance(raw.get("users"), dict):
                        users: dict[str, Any] = {}
                        for uid, payload in raw["users"].items():
                            uid_key = self._normalize_user_id(str(uid))
                            users[uid_key] = self._merge_user_state(payload)
                        if not users:
                            users[self.DEFAULT_USER_ID] = self._default_user_state()
                        return {"users": users}

                    # Backward compatibility for older single-tenant memory schema.
                    legacy_state = self._merge_user_state(raw)
                    return {"users": {self.DEFAULT_USER_ID: legacy_state}}
            except Exception:
                pass
        return self._default()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def _state_no_lock(self, user_id: str | None) -> dict[str, Any]:
        uid = self._normalize_user_id(user_id)
        users = self.data.setdefault("users", {})
        if uid not in users or not isinstance(users.get(uid), dict):
            users[uid] = self._default_user_state()
        return users[uid]

    @staticmethod
    def _topic_tags(text: str, limit: int = 6) -> list[str]:
        stop = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "to",
            "of",
            "in",
            "for",
            "with",
            "and",
            "or",
            "what",
            "who",
            "where",
            "when",
            "why",
            "how",
            "can",
            "could",
            "would",
            "should",
            "it",
            "this",
            "that",
            "you",
            "your",
        }
        tokens: list[str] = []
        for tok in re.findall(r"[a-z][a-z0-9_-]{2,}", text.lower()):
            if tok in stop:
                continue
            if tok not in tokens:
                tokens.append(tok)
            if len(tokens) >= limit:
                break
        return tokens

    @staticmethod
    def _auto_title_from_text(text: str) -> str:
        raw = re.sub(r"\s+", " ", str(text or "").strip())
        if not raw:
            return "New Chat"
        low = raw.lower()
        for prefix in [
            "what is ",
            "what are ",
            "who is ",
            "where is ",
            "when is ",
            "why is ",
            "how to ",
            "how do i ",
            "how can i ",
            "tell me about ",
            "explain ",
            "solve ",
            "find ",
        ]:
            if low.startswith(prefix):
                raw = raw[len(prefix) :].strip()
                break
        raw = re.sub(r"[^\w\s\-\+\*\/\^\(\)=]", "", raw).strip()
        words = [w for w in raw.split(" ") if w]
        if not words:
            return "New Chat"
        title_words = words[:7]
        title = " ".join(title_words)
        if len(words) > 7:
            title = f"{title}..."
        title = title.title()
        if len(title) > 64:
            title = f"{title[:61].rstrip()}..."
        return title or "New Chat"

    @staticmethod
    def topic_key(text: str) -> str:
        clean = re.sub(r"\s+", " ", text.strip().lower())
        clean = re.sub(r"[^a-z0-9\s\-\+\*\/\^\%\(\)=]", "", clean).strip()
        if not clean:
            return "general"
        prefixes = [
            "what is ",
            "what are ",
            "who is ",
            "where is ",
            "when is ",
            "why is ",
            "why do ",
            "how to ",
            "how do ",
            "tell me about ",
        ]
        for p in prefixes:
            if clean.startswith(p):
                clean = clean[len(p) :]
                break
        clean = clean.strip()
        while clean.startswith(("a ", "an ", "the ")):
            if clean.startswith("a "):
                clean = clean[2:]
            elif clean.startswith("an "):
                clean = clean[3:]
            elif clean.startswith("the "):
                clean = clean[4:]
            clean = clean.strip()

        aliases = {
            "ai": "artificial intelligence",
            "a i": "artificial intelligence",
            "artificial intelligence ai": "artificial intelligence",
        }
        clean = aliases.get(clean, clean)
        return clean[:120] or "general"

    def _ensure_session_no_lock(self, session_id: str | None = None, user_id: str | None = None) -> str:
        state = self._state_no_lock(user_id)
        sid = session_id or f"s_{uuid4().hex[:12]}"
        sessions = state["sessions"]
        if sid not in sessions:
            sessions[sid] = {
                "user_id": self._normalize_user_id(user_id),
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "title": "New Chat",
                "tags": [],
                "pinned_messages": [],
                "messages": [],
            }
        else:
            payload = sessions.get(sid)
            if isinstance(payload, dict):
                payload.setdefault("tags", [])
                payload.setdefault("pinned_messages", [])
        return sid

    def ensure_session(self, session_id: str | None = None, user_id: str | None = None) -> str:
        with self.lock:
            sid = self._ensure_session_no_lock(session_id=session_id, user_id=user_id)
            self._save()
            return sid

    def list_sessions(self, user_id: str | None = None) -> list[dict[str, Any]]:
        with self.lock:
            state = self._state_no_lock(user_id)
            out: list[dict[str, Any]] = []
            for sid, payload in state["sessions"].items():
                if not isinstance(payload, dict):
                    continue
                messages = payload.get("messages", [])
                out.append(
                    {
                        "session_id": sid,
                        "title": payload.get("title", "New Chat"),
                        "updated_at": payload.get("updated_at", ""),
                        "message_count": len(messages) if isinstance(messages, list) else 0,
                        "tags": list(payload.get("tags", [])) if isinstance(payload.get("tags", []), list) else [],
                        "pin_count": len(payload.get("pinned_messages", [])) if isinstance(payload.get("pinned_messages", []), list) else 0,
                    }
                )
            out.sort(key=lambda x: x["updated_at"], reverse=True)
            return out

    def session_exists(self, session_id: str, user_id: str | None = None) -> bool:
        with self.lock:
            state = self._state_no_lock(user_id)
            return session_id in state["sessions"]

    def get_history(self, session_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["sessions"].get(session_id, {})
            messages = payload.get("messages", []) if isinstance(payload, dict) else []
            return list(messages) if isinstance(messages, list) else []

    def search_session_messages(
        self,
        session_id: str,
        query: str,
        limit: int = 20,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        q = re.sub(r"\s+", " ", (query or "").strip().lower())
        if not q:
            return []
        terms = [t for t in re.findall(r"[a-z0-9]+", q) if len(t) >= 2]
        out: list[dict[str, Any]] = []
        for idx, msg in enumerate(self.get_history(session_id, user_id=user_id)):
            if not isinstance(msg, dict):
                continue
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            low = content.lower()
            score = 0.0
            if q in low:
                score += 2.0
            for term in terms:
                if term in low:
                    score += 0.35
            if score <= 0.0:
                continue
            excerpt = content if len(content) <= 220 else f"{content[:220].rstrip()}..."
            out.append(
                {
                    "message_index": idx,
                    "role": str(msg.get("role", "")),
                    "timestamp": str(msg.get("timestamp", "")),
                    "excerpt": excerpt,
                    "score": round(score, 3),
                }
            )
        out.sort(key=lambda item: (float(item.get("score", 0.0)), int(item.get("message_index", 0))), reverse=True)
        return out[: max(1, min(limit, 100))]

    def delete_session(self, session_id: str, user_id: str | None = None) -> bool:
        with self.lock:
            state = self._state_no_lock(user_id)
            sessions = state["sessions"]
            if session_id not in sessions:
                return False
            deleted_store = state.setdefault("deleted_sessions", {})
            payload = sessions.pop(session_id)
            if isinstance(payload, dict):
                payload["deleted_at"] = now_iso()
            deleted_store[session_id] = payload
            self._save()
            return True

    def restore_session(self, session_id: str, user_id: str | None = None) -> bool:
        with self.lock:
            state = self._state_no_lock(user_id)
            deleted_store = state.setdefault("deleted_sessions", {})
            if session_id not in deleted_store:
                return False
            payload = deleted_store.pop(session_id)
            if isinstance(payload, dict):
                payload.pop("deleted_at", None)
                payload["updated_at"] = now_iso()
            state["sessions"][session_id] = payload
            self._save()
            return True

    def append_message(self, session_id: str, role: str, content: str, user_id: str | None = None) -> None:
        with self.lock:
            state = self._state_no_lock(user_id)
            sid = self._ensure_session_no_lock(session_id=session_id, user_id=user_id)
            session = state["sessions"][sid]
            message = {
                "role": role,
                "content": content,
                "timestamp": now_iso(),
                "tags": self._topic_tags(content),
            }
            session["messages"].append(message)
            session["updated_at"] = now_iso()
            if len(session["messages"]) == 1 and role == "user":
                session["title"] = self._auto_title_from_text(content)
            self._save()

    def set_session_title(self, session_id: str, title: str, user_id: str | None = None) -> str:
        clean = re.sub(r"\s+", " ", str(title or "").strip())
        if not clean:
            return "New Chat"
        if len(clean) > 64:
            clean = f"{clean[:61].rstrip()}..."
        with self.lock:
            state = self._state_no_lock(user_id)
            sid = self._ensure_session_no_lock(session_id=session_id, user_id=user_id)
            payload = state["sessions"].get(sid, {})
            if not isinstance(payload, dict):
                return "New Chat"
            payload["title"] = clean
            payload["updated_at"] = now_iso()
            self._save()
            return clean

    def set_session_tags(self, session_id: str, tags: list[str], user_id: str | None = None) -> list[str]:
        cleaned: list[str] = []
        for tag in tags:
            item = re.sub(r"[^a-zA-Z0-9_\-\s]", "", str(tag or "").strip().lower())
            item = re.sub(r"\s+", "-", item).strip("-")
            if not item:
                continue
            if item not in cleaned:
                cleaned.append(item[:32])
            if len(cleaned) >= 12:
                break
        with self.lock:
            state = self._state_no_lock(user_id)
            sid = self._ensure_session_no_lock(session_id=session_id, user_id=user_id)
            payload = state["sessions"].get(sid, {})
            if not isinstance(payload, dict):
                return []
            payload["tags"] = cleaned
            payload["updated_at"] = now_iso()
            self._save()
            return list(cleaned)

    def get_session_tags(self, session_id: str, user_id: str | None = None) -> list[str]:
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["sessions"].get(session_id, {})
            if not isinstance(payload, dict):
                return []
            tags = payload.get("tags", [])
            return list(tags) if isinstance(tags, list) else []

    def get_session_title(self, session_id: str, user_id: str | None = None) -> str:
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["sessions"].get(session_id, {})
            if not isinstance(payload, dict):
                return "New Chat"
            title = str(payload.get("title", "New Chat")).strip()
            return title or "New Chat"

    def pin_message(
        self,
        session_id: str,
        message_index: int,
        note: str = "",
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self.lock:
            state = self._state_no_lock(user_id)
            sid = self._ensure_session_no_lock(session_id=session_id, user_id=user_id)
            payload = state["sessions"].get(sid, {})
            if not isinstance(payload, dict):
                return None
            messages = payload.get("messages", [])
            if not isinstance(messages, list):
                return None
            if message_index < 0 or message_index >= len(messages):
                return None

            pin_bucket = payload.setdefault("pinned_messages", [])
            if not isinstance(pin_bucket, list):
                pin_bucket = []
                payload["pinned_messages"] = pin_bucket

            existing = None
            for row in pin_bucket:
                if isinstance(row, dict) and int(row.get("message_index", -1)) == int(message_index):
                    existing = row
                    break

            message = messages[message_index] if isinstance(messages[message_index], dict) else {}
            pin_payload = {
                "message_index": int(message_index),
                "role": str(message.get("role", "")),
                "timestamp": str(message.get("timestamp", "")),
                "excerpt": str(message.get("content", "")).strip()[:240],
                "note": str(note or "").strip()[:240],
                "pinned_at": now_iso(),
            }
            if existing is not None:
                existing.update(pin_payload)
                out = dict(existing)
            else:
                pin_bucket.append(pin_payload)
                out = dict(pin_payload)

            payload["updated_at"] = now_iso()
            if len(pin_bucket) > 200:
                payload["pinned_messages"] = pin_bucket[-200:]
            self._save()
            return out

    def unpin_message(self, session_id: str, message_index: int, user_id: str | None = None) -> bool:
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["sessions"].get(session_id, {})
            if not isinstance(payload, dict):
                return False
            pins = payload.get("pinned_messages", [])
            if not isinstance(pins, list):
                return False
            before = len(pins)
            payload["pinned_messages"] = [
                row for row in pins if not (isinstance(row, dict) and int(row.get("message_index", -1)) == int(message_index))
            ]
            changed = len(payload["pinned_messages"]) != before
            if changed:
                payload["updated_at"] = now_iso()
                self._save()
            return changed

    def list_pins(self, session_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["sessions"].get(session_id, {})
            if not isinstance(payload, dict):
                return []
            pins = payload.get("pinned_messages", [])
            if not isinstance(pins, list):
                return []
            out = [dict(item) for item in pins if isinstance(item, dict)]
            out.sort(key=lambda item: str(item.get("pinned_at", "")), reverse=True)
            return out

    def last_by_role(
        self,
        session_id: str,
        role: str,
        skip_texts: set[str] | None = None,
        user_id: str | None = None,
    ) -> str:
        skip = {s.lower() for s in (skip_texts or set())}
        for msg in reversed(self.get_history(session_id, user_id=user_id)):
            if msg.get("role") != role:
                continue
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            if content.lower() in skip:
                continue
            return content
        return ""

    def update_topic_stats(self, topic: str, event: str, user_id: str | None = None) -> None:
        with self.lock:
            state = self._state_no_lock(user_id)
            stats = state["topic_stats"].setdefault(
                topic,
                {
                    "questions": 0,
                    "answers": 0,
                    "confirmations": 0,
                    "corrections": 0,
                    "mistakes": 0,
                    "last_seen": "",
                },
            )
            if event in stats:
                stats[event] = int(stats.get(event, 0)) + 1
            stats["last_seen"] = now_iso()
            questions = int(stats.get("questions", 0))
            confirms = int(stats.get("confirmations", 0))
            corrections = int(stats.get("corrections", 0))
            mistakes = int(stats.get("mistakes", 0))
            weight = (questions * 1.0) + (confirms * 2.5) - (corrections * 1.8) - (mistakes * 1.2)
            state["topic_weights"][topic] = round(weight, 3)
            self._save()

    def bump_pattern(self, pattern_key: str, mistake: bool = False, user_id: str | None = None) -> None:
        with self.lock:
            state = self._state_no_lock(user_id)
            table = state["mistake_patterns"] if mistake else state["question_patterns"]
            table[pattern_key] = int(table.get(pattern_key, 0)) + 1
            self._save()

    def get_topic_stats(self, topic: str, user_id: str | None = None) -> dict[str, Any]:
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["topic_stats"].get(topic, {})
            return dict(payload) if isinstance(payload, dict) else {}

    def get_pattern_count(self, pattern_key: str, mistake: bool = False, user_id: str | None = None) -> int:
        with self.lock:
            state = self._state_no_lock(user_id)
            table = state["mistake_patterns"] if mistake else state["question_patterns"]
            return int(table.get(pattern_key, 0))

    def record_experience(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        intent: str,
        confidence: float,
        references: list[dict[str, str]],
        user_id: str | None = None,
    ) -> None:
        with self.lock:
            state = self._state_no_lock(user_id)
            state["experiences"].append(
                {
                    "session_id": session_id,
                    "user_id": self._normalize_user_id(user_id),
                    "timestamp": now_iso(),
                    "user": user_message,
                    "assistant": assistant_message,
                    "intent": intent,
                    "confidence": float(confidence),
                    "tags": self._topic_tags(f"{user_message} {assistant_message}"),
                    "references": references,
                }
            )
            if len(state["experiences"]) > 4000:
                state["experiences"] = state["experiences"][-4000:]
            self._save()

    def record_decision(
        self,
        session_id: str,
        intent: str,
        topic: str,
        confidence_percent: int,
        understanding_percent: int,
        references: list[dict[str, str]],
        reasoning_steps: list[str],
        confidence_components: dict[str, float],
        user_id: str | None = None,
    ) -> None:
        with self.lock:
            state = self._state_no_lock(user_id)
            state["decision_logs"].append(
                {
                    "timestamp": now_iso(),
                    "session_id": session_id,
                    "user_id": self._normalize_user_id(user_id),
                    "intent": intent,
                    "topic": topic,
                    "confidence_percent": int(confidence_percent),
                    "understanding_percent": int(understanding_percent),
                    "reference_count": len(references),
                    "reasoning_steps": list(reasoning_steps),
                    "confidence_components": dict(confidence_components),
                }
            )
            if len(state["decision_logs"]) > 6000:
                state["decision_logs"] = state["decision_logs"][-6000:]
            self._save()

    def recent_decisions(self, limit: int = 20, user_id: str | None = None) -> list[dict[str, Any]]:
        with self.lock:
            state = self._state_no_lock(user_id)
            logs = state.get("decision_logs", [])
            if not isinstance(logs, list):
                return []
            return list(logs[-max(1, limit) :])[::-1]

    def get_rule(self, topic: str, user_id: str | None = None) -> dict[str, Any] | None:
        with self.lock:
            state = self._state_no_lock(user_id)
            item = state["rules"].get(topic)
            if not isinstance(item, dict):
                return None
            payload = dict(item)
            if "candidate" not in payload:
                payload["candidate"] = None
            if "history" not in payload or not isinstance(payload.get("history"), list):
                payload["history"] = []
            return payload

    @staticmethod
    def _rule_confidence(base: float, corrections: int, confirmations: int, supporting_sources: int, contradictions: int) -> float:
        value = (
            float(base)
            + (0.06 * max(0, corrections))
            + (0.05 * max(0, confirmations))
            + (0.07 * max(0, supporting_sources))
            - (0.09 * max(0, contradictions))
        )
        return max(0.05, min(0.99, value))

    @staticmethod
    def _ensure_rule_shape(payload: dict[str, Any] | None) -> dict[str, Any]:
        src = payload if isinstance(payload, dict) else {}
        current = src.get("current", {})
        history = src.get("history", [])
        candidate = src.get("candidate")
        version = int(src.get("version", 1))
        return {
            "current": dict(current) if isinstance(current, dict) else {},
            "candidate": dict(candidate) if isinstance(candidate, dict) else None,
            "history": list(history) if isinstance(history, list) else [],
            "version": max(1, version),
        }

    @staticmethod
    def _init_candidate(answer: str, source: str, base_confidence: float, evidence: str = "") -> dict[str, Any]:
        return {
            "answer": str(answer).strip(),
            "source": str(source).strip() or "unknown",
            "status": "pending",
            "base_confidence": max(0.05, min(0.99, float(base_confidence))),
            "confidence": max(0.05, min(0.99, float(base_confidence))),
            "signals": {
                "corrections": 1 if source.startswith("user_") else 0,
                "confirmations": 0,
                "supporting_sources": 0,
                "contradictions": 0,
            },
            "evidence": [str(evidence).strip()] if str(evidence or "").strip() else [],
            "timestamp": now_iso(),
            "last_updated": now_iso(),
        }

    def upsert_rule(
        self,
        topic: str,
        answer: str,
        confidence: float,
        source: str,
        *,
        verified: bool = True,
        source_count: int = 1,
        user_id: str | None = None,
    ) -> None:
        with self.lock:
            state = self._state_no_lock(user_id)
            rules = state["rules"]
            prev = self._ensure_rule_shape(rules.get(topic) if isinstance(rules.get(topic), dict) else None)
            history: list[dict[str, Any]] = []
            if prev:
                current = prev.get("current", {})
                if isinstance(current, dict) and current:
                    moved = dict(current)
                    moved["status"] = "outdated"
                    moved["timestamp"] = now_iso()
                    history = list(prev.get("history", [])) + [moved]
                candidate = prev.get("candidate")
                if isinstance(candidate, dict) and candidate:
                    stale = dict(candidate)
                    stale["status"] = "discarded_candidate"
                    stale["timestamp"] = now_iso()
                    history.append(stale)
            rules[topic] = {
                "current": {
                    "answer": answer,
                    "confidence": max(0.05, min(0.99, float(confidence))),
                    "source": source,
                    "status": "active",
                    "verified": bool(verified),
                    "source_count": max(1, int(source_count)),
                    "timestamp": now_iso(),
                },
                "candidate": None,
                "history": history[-100:],
                "version": int(prev.get("version", 1)) + 1 if isinstance(prev, dict) else 1,
            }
            self._save()

    def submit_candidate_rule(
        self,
        topic: str,
        answer: str,
        source: str,
        base_confidence: float = 0.68,
        evidence: str = "",
        user_id: str | None = None,
    ) -> None:
        clean_answer = re.sub(r"\s+", " ", (answer or "").strip())
        if not clean_answer:
            return
        with self.lock:
            state = self._state_no_lock(user_id)
            rules = state["rules"]
            payload = self._ensure_rule_shape(rules.get(topic) if isinstance(rules.get(topic), dict) else None)
            candidate = payload.get("candidate")
            now = now_iso()
            if isinstance(candidate, dict) and str(candidate.get("answer", "")).strip().lower() == clean_answer.lower():
                signals = candidate.setdefault("signals", {})
                signals["corrections"] = int(signals.get("corrections", 0)) + 1
                if evidence.strip():
                    ev = candidate.setdefault("evidence", [])
                    if isinstance(ev, list):
                        ev.append(evidence.strip())
                candidate["confidence"] = self._rule_confidence(
                    float(candidate.get("base_confidence", base_confidence)),
                    int(signals.get("corrections", 0)),
                    int(signals.get("confirmations", 0)),
                    int(signals.get("supporting_sources", 0)),
                    int(signals.get("contradictions", 0)),
                )
                candidate["last_updated"] = now
                payload["candidate"] = candidate
            else:
                if isinstance(candidate, dict) and candidate:
                    stale = dict(candidate)
                    stale["status"] = "replaced_candidate"
                    stale["timestamp"] = now
                    payload["history"].append(stale)
                payload["candidate"] = self._init_candidate(
                    answer=clean_answer,
                    source=source,
                    base_confidence=base_confidence,
                    evidence=evidence,
                )
            rules[topic] = {
                "current": payload.get("current", {}),
                "candidate": payload.get("candidate"),
                "history": list(payload.get("history", []))[-100:],
                "version": int(payload.get("version", 1)),
            }
            self._save()

    def get_candidate_rule(self, topic: str, user_id: str | None = None) -> dict[str, Any] | None:
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["rules"].get(topic)
            if not isinstance(payload, dict):
                return None
            candidate = payload.get("candidate")
            return dict(candidate) if isinstance(candidate, dict) else None

    def mark_candidate_signal(
        self,
        topic: str,
        signal: str,
        evidence: str = "",
        user_id: str | None = None,
    ) -> None:
        key = signal.strip().lower()
        if key not in {"confirmations", "supporting_sources", "contradictions", "corrections"}:
            return
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["rules"].get(topic)
            if not isinstance(payload, dict):
                return
            shaped = self._ensure_rule_shape(payload)
            candidate = shaped.get("candidate")
            if not isinstance(candidate, dict):
                return
            signals = candidate.setdefault("signals", {})
            signals[key] = int(signals.get(key, 0)) + 1
            candidate["confidence"] = self._rule_confidence(
                float(candidate.get("base_confidence", 0.68)),
                int(signals.get("corrections", 0)),
                int(signals.get("confirmations", 0)),
                int(signals.get("supporting_sources", 0)),
                int(signals.get("contradictions", 0)),
            )
            if evidence.strip():
                ev = candidate.setdefault("evidence", [])
                if isinstance(ev, list):
                    ev.append(evidence.strip())
            candidate["last_updated"] = now_iso()
            shaped["candidate"] = candidate
            state["rules"][topic] = {
                "current": shaped.get("current", {}),
                "candidate": shaped.get("candidate"),
                "history": list(shaped.get("history", []))[-100:],
                "version": int(shaped.get("version", 1)),
            }
            self._save()

    def promote_candidate_rule(
        self,
        topic: str,
        min_confidence: float = 0.82,
        min_support_signals: int = 2,
        user_id: str | None = None,
    ) -> bool:
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["rules"].get(topic)
            if not isinstance(payload, dict):
                return False
            shaped = self._ensure_rule_shape(payload)
            candidate = shaped.get("candidate")
            if not isinstance(candidate, dict):
                return False
            signals = candidate.get("signals", {}) if isinstance(candidate.get("signals"), dict) else {}
            support_total = (
                int(signals.get("corrections", 0))
                + int(signals.get("confirmations", 0))
                + int(signals.get("supporting_sources", 0))
            )
            contradictions = int(signals.get("contradictions", 0))
            conf = float(candidate.get("confidence", 0.0))
            if contradictions > 0:
                return False
            if conf < float(min_confidence):
                return False
            if support_total < int(min_support_signals):
                return False

            current = shaped.get("current", {})
            history = list(shaped.get("history", []))
            if isinstance(current, dict) and current:
                archived = dict(current)
                archived["status"] = "outdated"
                archived["timestamp"] = now_iso()
                history.append(archived)

            promoted = {
                "answer": str(candidate.get("answer", "")).strip(),
                "confidence": max(0.05, min(0.99, float(candidate.get("confidence", 0.5)))),
                "source": f"{candidate.get('source', 'candidate')}+validated",
                "status": "active",
                "verified": True,
                "source_count": max(1, support_total),
                "timestamp": now_iso(),
            }
            state["rules"][topic] = {
                "current": promoted,
                "candidate": None,
                "history": history[-100:],
                "version": int(shaped.get("version", 1)) + 1,
            }
            self._save()
            return True

    def reject_candidate_rule(self, topic: str, reason: str = "rejected", user_id: str | None = None) -> bool:
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["rules"].get(topic)
            if not isinstance(payload, dict):
                return False
            shaped = self._ensure_rule_shape(payload)
            candidate = shaped.get("candidate")
            if not isinstance(candidate, dict):
                return False
            archived = dict(candidate)
            archived["status"] = str(reason or "rejected")
            archived["timestamp"] = now_iso()
            history = list(shaped.get("history", []))
            history.append(archived)
            state["rules"][topic] = {
                "current": shaped.get("current", {}),
                "candidate": None,
                "history": history[-100:],
                "version": int(shaped.get("version", 1)),
            }
            self._save()
            return True

    def adjust_rule_confidence(self, topic: str, delta: float, user_id: str | None = None) -> None:
        with self.lock:
            state = self._state_no_lock(user_id)
            payload = state["rules"].get(topic)
            if not isinstance(payload, dict):
                return
            current = payload.get("current", {})
            if not isinstance(current, dict):
                return
            current["confidence"] = max(0.05, min(0.99, float(current.get("confidence", 0.5)) + float(delta)))
            current["timestamp"] = now_iso()
            self._save()

    def record_correction(
        self,
        session_id: str,
        topic: str,
        failed: str,
        corrected: str,
        user_id: str | None = None,
    ) -> None:
        with self.lock:
            state = self._state_no_lock(user_id)
            state["corrections"].append(
                {
                    "session_id": session_id,
                    "user_id": self._normalize_user_id(user_id),
                    "timestamp": now_iso(),
                    "topic": topic,
                    "failed_answer": failed,
                    "corrected_answer": corrected,
                    "tags": self._topic_tags(f"{topic} {corrected}"),
                }
            )
            if len(state["corrections"]) > 2000:
                state["corrections"] = state["corrections"][-2000:]
            self._save()

    def record_confirmation(self, session_id: str, topic: str, answer: str, user_id: str | None = None) -> None:
        with self.lock:
            state = self._state_no_lock(user_id)
            state["confirmations"].append(
                {
                    "session_id": session_id,
                    "user_id": self._normalize_user_id(user_id),
                    "timestamp": now_iso(),
                    "topic": topic,
                    "answer": answer,
                    "tags": self._topic_tags(f"{topic} {answer}"),
                }
            )
            if len(state["confirmations"]) > 2000:
                state["confirmations"] = state["confirmations"][-2000:]
            self._save()

    def record_feedback(
        self,
        session_id: str,
        topic: str,
        signal: str,
        note: str = "",
        user_id: str | None = None,
    ) -> None:
        clean_signal = signal.strip().lower()
        if clean_signal not in {"up", "down"}:
            return
        with self.lock:
            state = self._state_no_lock(user_id)
            bucket = state.setdefault("message_feedback", [])
            bucket.append(
                {
                    "session_id": session_id,
                    "user_id": self._normalize_user_id(user_id),
                    "timestamp": now_iso(),
                    "topic": topic,
                    "signal": clean_signal,
                    "note": (note or "").strip()[:280],
                }
            )
            if len(bucket) > 4000:
                state["message_feedback"] = bucket[-4000:]
            self._save()

    def remember_user_fact(
        self,
        key: str,
        value: str,
        confidence: float = 0.85,
        source: str = "user_statement",
        user_id: str | None = None,
    ) -> None:
        clean_key = re.sub(r"[^a-z0-9_-]", "", (key or "").strip().lower())
        clean_value = re.sub(r"\s+", " ", (value or "").strip())
        if not clean_key or not clean_value:
            return
        with self.lock:
            state = self._state_no_lock(user_id)
            facts = state.setdefault("user_facts", {})
            payload = facts.get(clean_key, {}) if isinstance(facts.get(clean_key), dict) else {}
            history = list(payload.get("history", [])) if isinstance(payload.get("history", []), list) else []
            current = payload.get("current", {}) if isinstance(payload.get("current"), dict) else {}
            if current:
                archived = dict(current)
                archived["status"] = "outdated"
                archived["timestamp"] = now_iso()
                history.append(archived)
            facts[clean_key] = {
                "current": {
                    "value": clean_value,
                    "confidence": max(0.05, min(0.99, float(confidence))),
                    "source": source,
                    "status": "active",
                    "timestamp": now_iso(),
                },
                "history": history[-100:],
            }
            self._save()

    def get_user_fact(self, key: str, user_id: str | None = None) -> dict[str, Any] | None:
        clean_key = re.sub(r"[^a-z0-9_-]", "", (key or "").strip().lower())
        if not clean_key:
            return None
        with self.lock:
            state = self._state_no_lock(user_id)
            facts = state.get("user_facts", {})
            payload = facts.get(clean_key) if isinstance(facts, dict) else None
            return dict(payload) if isinstance(payload, dict) else None

    def user_profile(self, user_id: str | None = None) -> dict[str, Any]:
        with self.lock:
            state = self._state_no_lock(user_id)
            facts = state.get("user_facts", {})
            if not isinstance(facts, dict):
                return {}
            out: dict[str, Any] = {}
            for key, payload in facts.items():
                if not isinstance(payload, dict):
                    continue
                current = payload.get("current", {})
                if not isinstance(current, dict):
                    continue
                value = str(current.get("value", "")).strip()
                if not value:
                    continue
                out[str(key)] = {
                    "value": value,
                    "confidence": float(current.get("confidence", 0.5)),
                    "timestamp": str(current.get("timestamp", "")),
                    "source": str(current.get("source", "")),
                }
            return out

    def add_graph_edge(
        self,
        source: str,
        relation: str,
        target: str,
        weight_delta: float = 1.0,
        user_id: str | None = None,
    ) -> None:
        if not source or not target or source == target:
            return
        with self.lock:
            state = self._state_no_lock(user_id)
            graph = state["knowledge_graph"]
            nodes = graph.setdefault("nodes", {})
            edges = graph.setdefault("edges", {})
            nodes[source] = int(nodes.get(source, 0)) + 1
            nodes[target] = int(nodes.get(target, 0)) + 1
            key = f"{source}|{relation}|{target}"
            edge = edges.get(
                key,
                {
                    "source": source,
                    "relation": relation,
                    "target": target,
                    "weight": 0.0,
                    "first_seen": now_iso(),
                    "last_seen": now_iso(),
                },
            )
            edge["weight"] = float(edge.get("weight", 0.0)) + float(weight_delta)
            edge["last_seen"] = now_iso()
            edges[key] = edge
            self._save()

    def graph_neighbors(self, topic: str, limit: int = 5, user_id: str | None = None) -> list[dict[str, Any]]:
        with self.lock:
            state = self._state_no_lock(user_id)
            edges = state["knowledge_graph"].get("edges", {})
            items: list[dict[str, Any]] = []
            for edge in edges.values():
                if not isinstance(edge, dict):
                    continue
                if edge.get("source") == topic or edge.get("target") == topic:
                    items.append(dict(edge))
            items.sort(key=lambda x: float(x.get("weight", 0.0)), reverse=True)
            return items[:limit]

    def learning_overview(self, limit: int = 10, user_id: str | None = None) -> dict[str, Any]:
        with self.lock:
            state = self._state_no_lock(user_id)
            topic_weights = state.get("topic_weights", {})
            sorted_topics = sorted(topic_weights.items(), key=lambda kv: float(kv[1]), reverse=True)
            top_topics = [{"topic": k, "weight": float(v)} for k, v in sorted_topics[:limit]]

            question_patterns = state.get("question_patterns", {})
            top_patterns = sorted(question_patterns.items(), key=lambda kv: int(kv[1]), reverse=True)[:limit]

            mistake_patterns = state.get("mistake_patterns", {})
            top_mistakes = sorted(mistake_patterns.items(), key=lambda kv: int(kv[1]), reverse=True)[:limit]

            graph = state.get("knowledge_graph", {})
            nodes = graph.get("nodes", {}) if isinstance(graph, dict) else {}
            edges = graph.get("edges", {}) if isinstance(graph, dict) else {}
            pending_candidates = 0
            for _topic, payload in state.get("rules", {}).items():
                if isinstance(payload, dict) and isinstance(payload.get("candidate"), dict):
                    pending_candidates += 1
            return {
                "counts": {
                    "sessions": len(state.get("sessions", {})),
                    "deleted_sessions": len(state.get("deleted_sessions", {})),
                    "experiences": len(state.get("experiences", [])),
                    "decision_logs": len(state.get("decision_logs", [])),
                    "rules": len(state.get("rules", {})),
                    "pending_rule_candidates": pending_candidates,
                    "user_facts": len(state.get("user_facts", {})),
                    "corrections": len(state.get("corrections", [])),
                    "confirmations": len(state.get("confirmations", [])),
                    "message_feedback": len(state.get("message_feedback", [])),
                    "graph_nodes": len(nodes),
                    "graph_edges": len(edges),
                },
                "top_topics": top_topics,
                "top_question_patterns": [{"pattern": k, "count": int(v)} for k, v in top_patterns],
                "top_mistake_patterns": [{"pattern": k, "count": int(v)} for k, v in top_mistakes],
            }
