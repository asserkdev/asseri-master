from __future__ import annotations

import re
from collections import OrderedDict
from difflib import get_close_matches
from typing import Iterable

try:
    from rapidfuzz import process

    RAPIDFUZZ_READY = True
except Exception:
    process = None
    RAPIDFUZZ_READY = False

MATH_CORRECTION_MEMORY: OrderedDict[str, str] = OrderedDict()
MAX_MATH_CORRECTION_MEMORY = 200


class FuzzyMatcher:
    """Lightweight typo correction for user queries."""

    def __init__(self, vocabulary: Iterable[str] | None = None) -> None:
        base = {
            "and",
            "or",
            "of",
            "to",
            "in",
            "on",
            "for",
            "with",
            "is",
            "are",
            "was",
            "were",
            "be",
            "a",
            "an",
            "the",
            "what",
            "who",
            "where",
            "when",
            "why",
            "how",
            "calculate",
            "compute",
            "evaluate",
            "solve",
            "equation",
            "integrate",
            "differentiate",
            "derivative",
            "limit",
            "factor",
            "simplify",
            "expand",
            "matrix",
            "determinant",
            "inverse",
            "eigenvalues",
            "weather",
            "forecast",
            "temperature",
            "capital",
            "internet",
            "python",
            "machine",
            "learning",
            "transformer",
            "reference",
            "references",
            "source",
            "sources",
            "gravity",
            "discovery",
            "discover",
            "logical",
            "logically",
            "follow",
            "follows",
            "roses",
            "rose",
            "flowers",
            "flower",
            "fade",
            "quickly",
            "thanks",
            "correct",
            "wrong",
            "ai",
            "assistant",
            "intelligence",
            "confidence",
            "mode",
            "simple",
            "standard",
            "advanced",
            "technical",
            "detail",
            "brief",
            "short",
            "name",
            "account",
            "login",
            "logout",
            "sign",
            "signed",
            "session",
            "chat",
            "question",
            "answer",
            "learn",
            "memory",
            "knowledge",
            "plane",
            "airplane",
            "aircraft",
            "purpose",
            "role",
            "function",
            "search",
            "wikipedia",
            "github",
            "repository",
            "frontend",
            "backend",
            "human",
            "woman",
            "women",
            "person",
            "movie",
            "song",
            "sing",
            "dance",
            "continue",
            "clarify",
            "explain",
            "reasoning",
            "step",
            "steps",
            "tone",
            "style",
            "formal",
            "friendly",
            "casual",
            "chill",
            "direct",
            "safety",
            "secure",
            "learning",
            "guardrails",
        }
        extra = set(vocabulary or [])
        self.vocabulary = sorted(base | extra)
        self.typo_map = {
            "wht": "what",
            "waht": "what",
            "wher": "where",
            "tommorow": "tomorrow",
            "teqneqs": "techniques",
            "mathimatical": "mathematical",
            "litterly": "literally",
            "intlegence": "intelligence",
            "proplem": "problem",
            "resparorty": "repository",
            "gihub": "github",
            "maost": "most",
            "pyhton": "python",
            "pythn": "python",
            "javascrit": "javascript",
            "algorthm": "algorithm",
            "calclate": "calculate",
            "simpel": "simple",
            "advnaced": "advanced",
            "detialed": "detailed",
            "refrence": "reference",
            "refrences": "references",
            "soucre": "source",
            "infomation": "information",
            "knwo": "know",
            "tecnical": "technical",
            "soruce": "source",
            "souces": "sources",
            "discovry": "discovery",
            "logial": "logical",
            "departmaent": "department",
            "complcty": "complexity",
            "safty": "safety",
            "mearses": "measures",
            "inteligent": "intelligent",
            "pluss": "plus",
            "minuss": "minus",
            "devide": "divide",
            "divde": "divide",
            "multply": "multiply",
            "squre": "square",
            "sqare": "square",
            "derivitive": "derivative",
            "intergrate": "integrate",
            "limt": "limit",
            "slove": "solve",
            "solv": "solve",
        }

    @staticmethod
    def _memory_key(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    @staticmethod
    def _remember_math_correction(original_text: str, corrected_text: str) -> None:
        key = FuzzyMatcher._memory_key(original_text)
        val = FuzzyMatcher._memory_key(corrected_text)
        if not key or not val or key == val:
            return
        if key in MATH_CORRECTION_MEMORY:
            del MATH_CORRECTION_MEMORY[key]
        MATH_CORRECTION_MEMORY[key] = val
        while len(MATH_CORRECTION_MEMORY) > MAX_MATH_CORRECTION_MEMORY:
            MATH_CORRECTION_MEMORY.popitem(last=False)

    @staticmethod
    def normalize_math_text(text: str) -> str:
        original = str(text or "")
        key = FuzzyMatcher._memory_key(original)
        if key in MATH_CORRECTION_MEMORY:
            corrected = MATH_CORRECTION_MEMORY[key]
            # Refresh recency ordering.
            del MATH_CORRECTION_MEMORY[key]
            MATH_CORRECTION_MEMORY[key] = corrected
            return corrected

        out = original.lower()
        corrections = {
            "pluss": "plus",
            "minuss": "minus",
            "devide": "divide",
            "divde": "divide",
            "multply": "multiply",
            "squre": "square",
            "sqare": "square",
            "derivitive": "derivative",
            "intergrate": "integrate",
            "limt": "limit",
            "slove": "solve",
            "solv": "solve",
        }
        for wrong, right in corrections.items():
            out = re.sub(rf"\b{re.escape(wrong)}\b", right, out)

        out = re.sub(r"(\d)([a-z])", r"\1 \2", out)
        out = re.sub(r"([a-z])(\d)", r"\1 \2", out)
        out = re.sub(r"\s+", " ", out).strip()
        if out != key:
            FuzzyMatcher._remember_math_correction(original, out)
        return out

    def analyze_text(self, text: str) -> dict[str, object]:
        parts = re.findall(r"[a-zA-Z0-9']+|[^a-zA-Z0-9']+", text)
        corrected: list[str] = []
        changes: list[dict[str, str]] = []
        unknown_tokens: list[str] = []
        total_words = 0
        for part in parts:
            if not re.fullmatch(r"[a-zA-Z0-9']+", part):
                corrected.append(part)
                continue
            token = part.lower()
            if len(token) >= 3 and not token.isdigit():
                total_words += 1
            if token in self.typo_map:
                fixed = self.typo_map[token]
                corrected.append(fixed)
                changes.append({"from": token, "to": fixed})
                continue
            if token.endswith("s") and len(token) >= 5 and token[:-1] in self.vocabulary:
                # Keep valid plurals without forcing a singular replacement.
                corrected.append(token)
                continue
            if token.isdigit() or len(token) < 4 or token in self.vocabulary:
                corrected.append(token)
                continue
            candidate = ""
            if RAPIDFUZZ_READY and process is not None:
                best = process.extractOne(token, self.vocabulary, score_cutoff=88)
                if best:
                    candidate = str(best[0])
            else:
                close = get_close_matches(token, self.vocabulary, n=1, cutoff=0.88)
                if close:
                    candidate = close[0]

            if candidate:
                if len(candidate) < 4 or abs(len(candidate) - len(token)) > 2:
                    candidate = ""

            if candidate and candidate != token:
                corrected.append(candidate)
                changes.append({"from": token, "to": candidate})
            else:
                corrected.append(token)
                if len(token) >= 4 and not token.isdigit():
                    unknown_tokens.append(token)

        unknown_count = len(unknown_tokens)
        change_count = len(changes)
        penalty = min(0.65, (change_count * 0.12) + (unknown_count * 0.2))
        if total_words <= 2 and penalty == 0:
            confidence = 0.95
        elif total_words == 0:
            confidence = 1.0
        else:
            confidence = max(0.2, 1.0 - penalty)

        suggestions: list[str] = []
        for token in unknown_tokens[:3]:
            candidate = ""
            if RAPIDFUZZ_READY and process is not None:
                best = process.extractOne(token, self.vocabulary, score_cutoff=70)
                if best:
                    candidate = str(best[0])
            else:
                close = get_close_matches(token, self.vocabulary, n=1, cutoff=0.7)
                if close:
                    candidate = close[0]
            if candidate and (len(candidate) < 4 or abs(len(candidate) - len(token)) > 2):
                candidate = ""
            if candidate:
                suggestions.append(f"{token} -> {candidate}")

        return {
            "normalized": "".join(corrected),
            "corrections": changes,
            "understanding_confidence": round(confidence, 3),
            "ambiguous_tokens": unknown_tokens[:5],
            "clarification_suggestions": suggestions,
        }

    def normalize_text(self, text: str) -> tuple[str, list[dict[str, str]]]:
        analysis = self.analyze_text(text)
        return str(analysis["normalized"]), list(analysis["corrections"])
