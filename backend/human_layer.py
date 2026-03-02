from __future__ import annotations

import re
from typing import Any


class HumanLayer:
    """Tone shaping + safety policy department."""

    TONES = {"formal", "friendly", "casual", "chill", "direct"}

    @staticmethod
    def extract_tone_command(text: str) -> str | None:
        t = re.sub(r"\s+", " ", str(text or "").strip().lower())
        alias = {
            "professional": "formal",
            "official": "formal",
            "friendly": "friendly",
            "casual": "casual",
            "chill": "chill",
            "relaxed": "chill",
            "direct": "direct",
            "brief": "direct",
        }
        for pattern in [
            r"^(?:set|change|switch)\s+(?:tone|style)\s+(?:to\s+)?([a-z]+)$",
            r"^(?:be|talk)\s+(?:more\s+)?([a-z]+)$",
            r"^(?:tone|style)\s*[:=]?\s*([a-z]+)$",
        ]:
            m = re.search(pattern, t)
            if not m:
                continue
            raw = m.group(1).strip()
            tone = alias.get(raw, raw)
            if tone in HumanLayer.TONES:
                return tone
        return None

    @staticmethod
    def infer_tone(query: str, stored_tone: str | None = None) -> tuple[str, str]:
        if stored_tone and stored_tone in HumanLayer.TONES:
            return stored_tone, "user_profile"

        q = str(query or "").lower()
        if any(x in q for x in ["formal", "professional", "official tone"]):
            return "formal", "query_override"
        if any(x in q for x in ["casual", "friendly", "like a friend"]):
            return "friendly", "query_override"
        if any(x in q for x in ["chill", "relaxed"]):
            return "chill", "query_override"
        if any(x in q for x in ["direct", "straight answer", "no extra"]):
            return "direct", "query_override"

        # Lightweight style mirroring for user comfort.
        if any(x in q for x in ["pls", "bro", "lol", "hey", "yo"]):
            return "casual", "auto_detected"
        return "friendly", "default"

    @staticmethod
    def rewrite_tone(answer: str, tone: str, intent: str) -> str:
        base = str(answer or "").strip()
        if not base:
            return base
        if tone not in HumanLayer.TONES:
            return base
        if intent == "math":
            return base

        if tone == "formal":
            text = base
            text = re.sub(r"\bI can't\b", "I cannot", text)
            text = re.sub(r"\bI don't\b", "I do not", text)
            text = re.sub(r"\bI'm\b", "I am", text)
            if not text.lower().startswith("certainly"):
                return f"Certainly. {text}"
            return text

        if tone == "direct":
            # Keep concise: preserve first useful lines only.
            lines = [ln.strip() for ln in base.splitlines() if ln.strip()]
            if intent == "math":
                return base
            if len(lines) <= 3:
                return "\n".join(lines)
            return "\n".join(lines[:3])

        if tone == "chill":
            text = base
            if not re.match(r"^(sure|okay|alright)[\.\,]?", text.lower()):
                text = f"Sure. {text}"
            return text

        if tone == "casual":
            text = base
            text = re.sub(r"\bI am\b", "I'm", text)
            text = re.sub(r"\bI cannot\b", "I can't", text)
            return text

        # friendly
        text = base
        if not re.match(r"^(sure|of course|happy to help)[\.\,]?", text.lower()):
            text = f"Of course. {text}"
        return text

    @staticmethod
    def safety_response(text: str) -> dict[str, Any] | None:
        q = re.sub(r"\s+", " ", str(text or "").lower()).strip()
        if not q:
            return None

        self_harm = [
            "kill myself",
            "suicide",
            "self harm",
            "hurt myself",
            "end my life",
            "want to die",
        ]
        if any(p in q for p in self_harm):
            return {
                "category": "self_harm",
                "answer": (
                    "I am really sorry you are going through this. You matter, and you deserve support right now.\n"
                    "If you are in immediate danger, call emergency services now.\n"
                    "If you are in the U.S., call or text 988 for the Suicide & Crisis Lifeline. "
                    "If you are elsewhere, contact your local crisis line immediately."
                ),
                "confidence": 0.97,
                "references": [
                    {"title": "988 Lifeline", "url": "https://988lifeline.org/"},
                    {"title": "Emergency Support", "url": "internal://safety-emergency"},
                ],
            }

        illegal = [
            "make a bomb",
            "build a bomb",
            "explosive at home",
            "hack account",
            "steal password",
            "ddos",
            "malware",
            "ransomware",
            "carding",
        ]
        if any(p in q for p in illegal):
            return {
                "category": "unsafe_illegal",
                "answer": (
                    "I cannot help with harmful or illegal actions. "
                    "I can help with legal safety, cybersecurity defense, and prevention guidance."
                ),
                "confidence": 0.96,
                "references": [
                    {"title": "Safety Policy", "url": "internal://safety-policy"},
                    {"title": "Cybersecurity Defense", "url": "internal://safe-cybersecurity"},
                ],
            }

        abuse = [
            "how to poison",
            "how to kill someone",
            "how to hurt people",
            "weapon to attack",
        ]
        if any(p in q for p in abuse):
            return {
                "category": "harmful_violence",
                "answer": (
                    "I cannot assist with violence or harm. "
                    "If your goal is safety or protection, I can provide lawful prevention guidance."
                ),
                "confidence": 0.96,
                "references": [{"title": "Safety Policy", "url": "internal://safety-policy"}],
            }
        return None

    @staticmethod
    def learning_guard(topic: str, candidate_answer: str) -> tuple[bool, str]:
        topic_clean = str(topic or "").strip().lower()
        ans = re.sub(r"\s+", " ", str(candidate_answer or "").strip())
        if not ans:
            return False, "Candidate answer is empty."
        if len(ans) > 600:
            return False, "Candidate answer is too long for safe automatic learning."
        if re.search(r"https?://|www\.", ans, flags=re.IGNORECASE):
            return False, "Links are not accepted as direct learned answers."
        if any(x in ans.lower() for x in ["i think", "maybe", "not sure", "probably", "guess"]):
            return False, "Uncertain statements are not accepted as rules."
        if ans.count("?") > 0:
            return False, "Questions cannot be stored as final rule answers."
        if topic_clean in {"who am i", "my name", "general"} and len(ans.split()) > 20:
            return False, "Personal/meta topics require concise validated answers."
        return True, "Learning guard passed."
