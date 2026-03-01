from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class AuthStore:
    """Simple local auth system with hashed passwords and bearer sessions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.session_hours = max(1, int(os.getenv("ASSERI_AUTH_SESSION_HOURS", "720")))
        self.data = self._load()

    @staticmethod
    def _default() -> dict[str, Any]:
        return {"users": {}, "sessions": {}}

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    users = raw.get("users", {})
                    sessions = raw.get("sessions", {})
                    return {
                        "users": users if isinstance(users, dict) else {},
                        "sessions": sessions if isinstance(sessions, dict) else {},
                    }
            except Exception:
                pass
        return self._default()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    @staticmethod
    def normalize_username(username: str | None) -> str:
        raw = (username or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9_-]{3,32}", raw):
            return ""
        return raw

    @staticmethod
    def _hash_password(password: str, salt_hex: str) -> str:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            240000,
        )
        return digest.hex()

    def _cleanup_expired_sessions_no_lock(self) -> bool:
        changed = False
        sessions = self.data.get("sessions", {})
        if not isinstance(sessions, dict):
            self.data["sessions"] = {}
            return True
        now = datetime.now()
        expired_tokens: list[str] = []
        for token, payload in sessions.items():
            if not isinstance(payload, dict):
                expired_tokens.append(token)
                continue
            exp_raw = str(payload.get("expires_at", "")).strip()
            try:
                exp_dt = datetime.fromisoformat(exp_raw)
            except Exception:
                expired_tokens.append(token)
                continue
            if now >= exp_dt:
                expired_tokens.append(token)
        for token in expired_tokens:
            sessions.pop(token, None)
            changed = True
        return changed

    def register_user(self, username: str, password: str) -> tuple[bool, str]:
        uname = self.normalize_username(username)
        if not uname:
            return False, "Username must be 3-32 chars, letters/numbers/_/- only."
        if len(password) < 6:
            return False, "Password must be at least 6 characters."
        if len(password) > 256:
            return False, "Password is too long."

        with self.lock:
            users = self.data.setdefault("users", {})
            if not isinstance(users, dict):
                users = {}
                self.data["users"] = users
            if uname in users:
                return False, "Username already exists."

            salt = secrets.token_hex(16)
            users[uname] = {
                "salt": salt,
                "password_hash": self._hash_password(password, salt),
                "created_at": now_iso(),
                "last_login_at": "",
            }
            self._save()
        return True, uname

    def _issue_session_no_lock(self, username: str) -> tuple[str, str]:
        sessions = self.data.setdefault("sessions", {})
        if not isinstance(sessions, dict):
            sessions = {}
            self.data["sessions"] = sessions

        token = secrets.token_urlsafe(48)
        created = datetime.now()
        expires = created + timedelta(hours=self.session_hours)
        sessions[token] = {
            "username": username,
            "created_at": created.isoformat(timespec="seconds"),
            "last_seen": created.isoformat(timespec="seconds"),
            "expires_at": expires.isoformat(timespec="seconds"),
        }
        return token, expires.isoformat(timespec="seconds")

    def login(self, username: str, password: str) -> tuple[bool, str, str, str]:
        uname = self.normalize_username(username)
        if not uname:
            return False, "", "", "Invalid username or password."
        with self.lock:
            users = self.data.get("users", {})
            payload = users.get(uname) if isinstance(users, dict) else None
            if not isinstance(payload, dict):
                return False, "", "", "Invalid username or password."

            salt = str(payload.get("salt", ""))
            expected = str(payload.get("password_hash", ""))
            if not salt or not expected:
                return False, "", "", "Invalid username or password."
            actual = self._hash_password(password, salt)
            if not hmac.compare_digest(actual, expected):
                return False, "", "", "Invalid username or password."

            self._cleanup_expired_sessions_no_lock()
            token, expires_at = self._issue_session_no_lock(uname)
            payload["last_login_at"] = now_iso()
            self._save()
            return True, token, expires_at, uname

    def validate_session(self, token: str | None) -> str | None:
        clean = (token or "").strip()
        if not clean:
            return None
        with self.lock:
            sessions = self.data.get("sessions", {})
            if not isinstance(sessions, dict):
                return None
            payload = sessions.get(clean)
            if not isinstance(payload, dict):
                return None
            exp_raw = str(payload.get("expires_at", "")).strip()
            try:
                exp_dt = datetime.fromisoformat(exp_raw)
            except Exception:
                sessions.pop(clean, None)
                self._save()
                return None
            now = datetime.now()
            if now >= exp_dt:
                sessions.pop(clean, None)
                self._save()
                return None
            username = self.normalize_username(str(payload.get("username", "")))
            if not username:
                sessions.pop(clean, None)
                self._save()
                return None
            payload["last_seen"] = now.isoformat(timespec="seconds")
            self._save()
            return username

    def logout(self, token: str | None) -> bool:
        clean = (token or "").strip()
        if not clean:
            return False
        with self.lock:
            sessions = self.data.get("sessions", {})
            if not isinstance(sessions, dict):
                return False
            if clean not in sessions:
                return False
            sessions.pop(clean, None)
            self._save()
            return True
