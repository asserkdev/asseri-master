from __future__ import annotations

import re
from typing import Any


class HumanLayer:
    """Tone shaping + safety policy department."""

    TONES = {"formal", "friendly", "casual", "chill", "direct"}
    @staticmethod
    def _is_short_or_greeting(text: str) -> bool:
        low = re.sub(r"\s+", " ", str(text or "").strip().lower())
        if not low:
            return True
        greeting_starts = (
            "hi",
            "hello",
            "hey",
            "i am asseri ai",
            "i'm asseri ai",
            "tone set to",
            "your tone mode is",
            "your response mode is",
            "you are signed in as",
        )
        if any(low.startswith(start) for start in greeting_starts):
            return True
        word_count = len(re.findall(r"[a-z0-9']+", low))
        return word_count <= 10

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
        compact = re.sub(r"[^\w\s]", " ", t)
        compact = re.sub(r"\s+", " ", compact).strip()
        if compact.startswith("set tone to "):
            raw = compact[len("set tone to ") :].strip().split(" ")[0]
            tone = alias.get(raw, raw)
            if tone in HumanLayer.TONES:
                return tone
        if compact.startswith("set style to "):
            raw = compact[len("set style to ") :].strip().split(" ")[0]
            tone = alias.get(raw, raw)
            if tone in HumanLayer.TONES:
                return tone
        if compact.startswith("tone "):
            raw = compact[len("tone ") :].strip().split(" ")[0]
            tone = alias.get(raw, raw)
            if tone in HumanLayer.TONES:
                return tone
        if compact.startswith("style "):
            raw = compact[len("style ") :].strip().split(" ")[0]
            tone = alias.get(raw, raw)
            if tone in HumanLayer.TONES:
                return tone
        for pattern in [
            r"^(?:set|change|switch)\s+(?:tone|style)\s+(?:to\s+)?([a-z]+)\b",
            r"^(?:be|talk)\s+(?:more\s+)?([a-z]+)\b",
            r"^(?:tone|style)\s*[:=]?\s*([a-z]+)\b",
        ]:
            m = re.search(pattern, compact)
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
            if not HumanLayer._is_short_or_greeting(text) and not re.match(r"^(sure|okay|alright)[\.\,]?", text.lower()):
                text = f"Sure. {text}"
            return text

        if tone == "casual":
            text = base
            text = re.sub(r"\bI am\b", "I'm", text)
            text = re.sub(r"\bI cannot\b", "I can't", text)
            return text

        # friendly
        return base

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
            "\u0627\u0642\u062a\u0644 \u0646\u0641\u0633\u064a",
            "\u0627\u0646\u062a\u062d\u0627\u0631",
            "\u0627\u0624\u0630\u064a \u0646\u0641\u0633\u064a",
            "\u0627\u0630\u064a \u0646\u0641\u0633\u064a",
            "\u0627\u0645\u0648\u062a",
            "\u0623\u0645\u0648\u062a",
            "\u0627\u0646\u0647\u064a \u062d\u064a\u0627\u062a\u064a",
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
            "\u0627\u0635\u0646\u0639 \u0642\u0646\u0628\u0644\u0629",
            "\u0627\u0635\u0646\u0639 \u0645\u062a\u0641\u062c\u0631\u0627\u062a",
            "\u0627\u062e\u062a\u0631\u0642 \u062d\u0633\u0627\u0628",
            "\u0633\u0631\u0642\u0629 \u0643\u0644\u0645\u0629 \u0627\u0644\u0645\u0631\u0648\u0631",
            "\u0628\u0631\u0645\u062c\u064a\u0629 \u062e\u0628\u064a\u062b\u0629",
            "\u0641\u064a\u0631\u0648\u0633 \u0641\u062f\u064a\u0629",
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
            "\u0643\u064a\u0641 \u0627\u0633\u0645\u0645",
            "\u0643\u064a\u0641 \u0627\u0642\u062a\u0644 \u0634\u062e\u0635",
            "\u0643\u064a\u0641 \u0627\u0624\u0630\u064a \u0627\u0644\u0646\u0627\u0633",
            "\u0633\u0644\u0627\u062d \u0644\u0644\u0647\u062c\u0648\u0645",
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
