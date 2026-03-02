from __future__ import annotations

import re
from typing import Any


class AccuracyPolicy:
    """Lightweight policy module for search gating + learning signals."""

    @staticmethod
    def should_search_web(
        query: str,
        topic: str,
        intent: str,
        has_internal_candidate: bool,
        understanding_conf: float,
        topic_stats: dict[str, Any] | None = None,
    ) -> bool:
        q = re.sub(r"\s+", " ", str(query or "").lower()).strip()
        stats = topic_stats or {}

        if intent in {"math", "casual", "feedback", "safety"}:
            return False

        if any(k in q for k in ["source", "sources", "reference", "references", "latest", "today", "news"]):
            return True

        if has_internal_candidate and understanding_conf >= 0.75:
            return False

        # Very short, vague prompts should ask for clarification first.
        tokens = re.findall(r"[a-z0-9]+", q)
        if len(tokens) <= 2 and not any(k in q for k in ["who", "what", "where", "when", "why", "how"]):
            return False

        corrections = int(stats.get("corrections", 0))
        mistakes = int(stats.get("mistakes", 0))
        if corrections + mistakes >= 4:
            return True

        return True

    @staticmethod
    def search_variants_limit(query: str, must_search: bool) -> int:
        q = re.sub(r"\s+", " ", str(query or "").lower()).strip()
        if not must_search:
            return 0
        if len(q.split()) <= 3:
            return 1
        if any(k in q for k in ["latest", "today", "news", "sources", "reference"]):
            return 3
        return 2

    @staticmethod
    def classify_answer_outcome(confidence: float, answer: str) -> str:
        low = str(answer or "").lower()
        if confidence >= 0.88 and "could not find a high-confidence summary" not in low:
            return "likely_correct"
        if confidence <= 0.55 or "could not find a high-confidence summary" in low:
            return "likely_incorrect"
        return "uncertain"

    @staticmethod
    def should_accept_candidate(
        *,
        query: str,
        answer: str,
        intent: str,
        relevance: float,
        focus_overlap: float,
        trust: float,
        support_count: int,
    ) -> tuple[bool, str]:
        q = re.sub(r"\s+", " ", str(query or "").lower()).strip()
        a = re.sub(r"\s+", " ", str(answer or "").lower()).strip()
        if not a:
            return False, "empty-answer"
        if "may refer to" in a or "disambiguation" in a:
            return False, "ambiguous-answer"
        if "could not find a high-confidence summary" in a:
            return False, "low-confidence-fallback"

        tokens = re.findall(r"[a-z0-9]+", q)
        short_query = len(tokens) <= 6
        if intent in {"knowledge", "problem_solving"} and short_query:
            if relevance < 0.15:
                return False, "low-relevance-short-query"
            if focus_overlap < 0.34:
                return False, "low-focus-overlap-short-query"

        if trust < 0.52 and support_count <= 1:
            return False, "low-trust-no-support"

        if any(k in q for k in ["purpose of", "role of", "function of", "job of"]) and not any(
            k in a for k in ["purpose", "used for", "used to", "main function", "transport", "carry", "serves"]
        ):
            return False, "purpose-query-mismatch"

        return True, "accepted"
