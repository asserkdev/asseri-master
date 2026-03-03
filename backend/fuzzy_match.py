from __future__ import annotations

import re
from collections import OrderedDict
from difflib import get_close_matches
from typing import Iterable

from .nlp.arabic import contains_arabic, normalize_arabic_text

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
            "google",
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
            "data",
            "information",
            "point",
            "points",
            "difference",
            "between",
            "clear",
            "train",
            "travels",
            "travel",
            "average",
            "speed",
            "hour",
            "hours",
            "meter",
            "meters",
            "second",
            "seconds",
            "write",
            "function",
            "check",
            "number",
            "prime",
            "time",
            "complexity",
            "correlation",
            "causation",
            "example",
            "summarize",
            "photosynthesis",
            "student",
            "university",
            "compare",
            "sql",
            "nosql",
            "used",
            "use",
            "reliable",
            "respond",
            "before",
            "design",
            "day",
            "days",
            "beginner",
            "plan",
            "security",
            "risks",
            "using",
            "eval",
            "safe",
            "alternative",
            "rectangle",
            "perimeter",
            "width",
            "length",
            "area",
            "recursion",
            "factorial",
            "iterative",
            "typed",
            "trusted",
            "newton",
            "gravitation",
            "trustworthy",
            "japan",
            "mistake",
            "people",
            "argument",
            "valid",
            "safely",
            "unsafe",
            "requests",
        }
        base |= {
            "then",
            "therefore",
            "thus",
            "because",
            "proof",
            "counterexample",
            "rains",
            "rain",
            "roads",
            "road",
            "wet",
            "traffic",
            "slows",
            "slow",
            "cats",
            "cat",
            "mammals",
            "mammal",
            "animals",
            "animal",
            "exists",
            "exist",
            "tokyo",
            "law",
            "risk",
        }
        extra = set(vocabulary or [])
        self.vocabulary = sorted(base | extra)
        self.typo_map = {
            "wht": "what",
            "teh": "the",
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
            "captial": "capital",
            "japn": "japan",
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
            "ariplane": "airplane",
        }
        self.uncertain_typo_map = {
            "gogg": "google",
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
    def _is_suspicious_unknown(token: str) -> bool:
        tok = str(token or "").lower().strip()
        if not tok:
            return False
        if any(ch.isdigit() for ch in tok) and any(ch.isalpha() for ch in tok):
            return True
        letters = re.sub(r"[^a-z]", "", tok)
        if len(letters) >= 4 and not re.search(r"[aeiouy]", letters):
            return True
        if len(letters) >= 8 and re.search(r"(.)\1\1", letters):
            return True
        return False

    @staticmethod
    def normalize_math_text(text: str) -> str:
        original = str(text or "")
        key = FuzzyMatcher._memory_key(original)
        if key in MATH_CORRECTION_MEMORY:
            corrected = MATH_CORRECTION_MEMORY[key]
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
            "ariplane": "airplane",
        }
        for wrong, right in corrections.items():
            out = re.sub(rf"\b{re.escape(wrong)}\b", right, out)

        out = re.sub(r"(\d)([a-z])", r"\1 \2", out)
        out = re.sub(r"([a-z])(\d)", r"\1 \2", out)
        out = re.sub(r"\s+", " ", out).strip()
        if out != key:
            FuzzyMatcher._remember_math_correction(original, out)
        return out

    def _is_valid_candidate(self, token: str, candidate: str) -> bool:
        if not candidate or candidate == token:
            return False
        max_len_delta = 1 if len(token) >= 6 else 2
        if len(candidate) < 4 or abs(len(candidate) - len(token)) > max_len_delta:
            return False
        if token and candidate and token[0] != candidate[0]:
            return False
        if len(token) >= 7 and not candidate.startswith(token[:2]):
            return False
        if len(token) >= 5 and len(candidate) < int(round(len(token) * 0.8)):
            return False
        return True

    def _candidate_for_token(self, token: str, cutoff: int = 93) -> str:
        candidate = ""
        if RAPIDFUZZ_READY and process is not None:
            best = process.extractOne(token, self.vocabulary, score_cutoff=cutoff)
            if best:
                candidate = str(best[0])
        else:
            close = get_close_matches(token, self.vocabulary, n=1, cutoff=max(0.0, min(1.0, cutoff / 100.0)))
            if close:
                candidate = close[0]
        if self._is_valid_candidate(token, candidate):
            return candidate
        return ""

    def analyze_text(self, text: str) -> dict[str, object]:
        if contains_arabic(text):
            normalized = normalize_arabic_text(text)
            return {
                "normalized": normalized,
                "corrections": [],
                "understanding_confidence": 0.9,
                "ambiguous_tokens": [],
                "clarification_suggestions": [],
                "suggested_sentence": normalized,
                "needs_confirmation": False,
                "soft_corrections": [],
            }

        parts = re.findall(r"[a-zA-Z0-9']+|[^a-zA-Z0-9']+", text)
        corrected_parts: list[str] = []
        suggested_parts: list[str] = []
        changes: list[dict[str, str]] = []
        soft_changes: list[dict[str, str]] = []
        unknown_tokens: list[str] = []
        suspicious_unknown_tokens: list[str] = []
        total_words = 0

        for part in parts:
            if not re.fullmatch(r"[a-zA-Z0-9']+", part):
                corrected_parts.append(part)
                suggested_parts.append(part)
                continue

            token = part.lower()
            if len(token) >= 3 and not token.isdigit():
                total_words += 1

            if token in self.typo_map:
                fixed = self.typo_map[token]
                corrected_parts.append(fixed)
                suggested_parts.append(fixed)
                changes.append({"from": token, "to": fixed})
                continue

            if token in self.uncertain_typo_map:
                fixed = self.uncertain_typo_map[token]
                corrected_parts.append(token)
                suggested_parts.append(fixed)
                soft_changes.append({"from": token, "to": fixed})
                unknown_tokens.append(token)
                continue

            if token.endswith("s") and len(token) >= 5 and token[:-1] in self.vocabulary:
                corrected_parts.append(token)
                suggested_parts.append(token)
                continue

            if token.isdigit() or len(token) < 4 or token in self.vocabulary:
                corrected_parts.append(token)
                suggested_parts.append(token)
                continue

            strong_candidate = self._candidate_for_token(token, cutoff=93)
            if strong_candidate:
                corrected_parts.append(strong_candidate)
                suggested_parts.append(strong_candidate)
                changes.append({"from": token, "to": strong_candidate})
                continue

            corrected_parts.append(token)
            if len(token) >= 4 and not token.isdigit():
                unknown_tokens.append(token)
                if self._is_suspicious_unknown(token):
                    suspicious_unknown_tokens.append(token)

            soft_candidate = self._candidate_for_token(token, cutoff=86)
            if soft_candidate:
                suggested_parts.append(soft_candidate)
                soft_changes.append({"from": token, "to": soft_candidate})
            else:
                suggested_parts.append(token)

        unknown_count = len(unknown_tokens)
        suspicious_count = len(suspicious_unknown_tokens)
        strong_change_count = len(changes)
        soft_change_count = len(soft_changes)
        penalty = min(
            0.65,
            (strong_change_count * 0.08)
            + (soft_change_count * 0.05)
            + (suspicious_count * 0.14)
            + (min(unknown_count, 6) * 0.015),
        )
        if total_words <= 2 and penalty == 0:
            confidence = 0.95
        elif total_words == 0:
            confidence = 1.0
        else:
            confidence = max(0.2, 1.0 - penalty)

        suggestions: list[str] = []
        seen_map: set[str] = set()
        for row in soft_changes[:4]:
            key = f"{row['from']}->{row['to']}"
            if key in seen_map:
                continue
            seen_map.add(key)
            suggestions.append(f"{row['from']} -> {row['to']}")

        if not suggestions:
            suggestion_pool = suspicious_unknown_tokens[:3] if suspicious_unknown_tokens else unknown_tokens[:2]
            for token in suggestion_pool:
                candidate = self._candidate_for_token(token, cutoff=85)
                if candidate:
                    key = f"{token}->{candidate}"
                    if key in seen_map:
                        continue
                    seen_map.add(key)
                    suggestions.append(f"{token} -> {candidate}")

        normalized = "".join(corrected_parts)
        suggested_sentence = "".join(suggested_parts)
        original_compact = re.sub(r"\s+", " ", str(text or "")).strip()
        normalized_compact = re.sub(r"\s+", " ", normalized).strip()
        suggested_compact = re.sub(r"\s+", " ", suggested_sentence).strip()

        needs_confirmation = (
            bool(soft_changes)
            or strong_change_count >= 2
            or (strong_change_count >= 1 and (suspicious_count >= 1 or confidence < 0.94))
        )
        if not suggested_compact or suggested_compact.lower() == original_compact.lower():
            needs_confirmation = False

        return {
            "normalized": normalized,
            "corrections": changes,
            "understanding_confidence": round(confidence, 3),
            "ambiguous_tokens": unknown_tokens[:5],
            "clarification_suggestions": suggestions,
            "suggested_sentence": suggested_compact,
            "needs_confirmation": bool(needs_confirmation),
            "soft_corrections": soft_changes[:8],
        }

    def normalize_text(self, text: str) -> tuple[str, list[dict[str, str]]]:
        analysis = self.analyze_text(text)
        return str(analysis["normalized"]), list(analysis["corrections"])
