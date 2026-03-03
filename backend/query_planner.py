from __future__ import annotations

import re
from typing import Any


class QueryPlanner:
    """Route planner for knowledge/problem-solving requests."""

    @staticmethod
    def _tokens(text: str) -> list[str]:
        pattern = r"[a-z0-9\u0600-\u06FF]+"
        return [t for t in re.findall(pattern, str(text or "").lower()) if t]

    @staticmethod
    def _is_vague(query: str) -> bool:
        q = re.sub(r"\s+", " ", str(query or "").strip().lower())
        tokens = QueryPlanner._tokens(q)
        if len(tokens) <= 1:
            return True
        vague_set = {
            "it",
            "this",
            "that",
            "thing",
            "stuff",
            "something",
            "anything",
            "there",
            "here",
            "هذا",
            "هذه",
            "ذلك",
            "شيء",
            "حاجة",
            "هناك",
            "هنا",
        }
        if len(tokens) <= 3 and all(t in vague_set or len(t) <= 2 for t in tokens):
            return True
        return False

    @staticmethod
    def _needs_fresh_web(query: str) -> bool:
        q = str(query or "").lower()
        markers = {
            "latest",
            "today",
            "news",
            "now",
            "current",
            "new update",
            "this week",
            "this month",
            "sources",
            "references",
            "احدث",
            "اليوم",
            "اخبار",
            "حاليا",
            "مصادر",
            "مراجع",
        }
        return any(m in q for m in markers)

    @staticmethod
    def _query_complexity(query: str) -> str:
        tokens = QueryPlanner._tokens(query)
        q = str(query or "").lower()
        if len(tokens) >= 18 or any(k in q for k in ["compare", "analyze", "prove", "derive", "step by step", "قارن", "حلل", "اثبت", "اشرح خطوة"]):
            return "high"
        if len(tokens) >= 9:
            return "medium"
        return "low"

    def analyze(
        self,
        *,
        query: str,
        intent: str,
        understanding_conf: float,
        has_internal_candidate: bool,
        topic: str,
        topic_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stats = topic_stats or {}
        corrections = int(stats.get("corrections", 0))
        mistakes = int(stats.get("mistakes", 0))
        complexity = self._query_complexity(query)
        needs_fresh_web = self._needs_fresh_web(query)
        vague = self._is_vague(query)

        route = "default"
        allow_web = True
        request_clarification = False

        if intent in {"math", "casual", "feedback", "safety"}:
            route = intent
            allow_web = False
        elif (understanding_conf < 0.42 and not has_internal_candidate) or vague:
            route = "clarify"
            allow_web = False
            request_clarification = True
        elif needs_fresh_web:
            route = "web_first"
            allow_web = True
        elif has_internal_candidate:
            route = "internal_first"
            allow_web = False
        elif corrections + mistakes >= 4:
            route = "hybrid_verify"
            allow_web = True
        else:
            route = "hybrid"
            allow_web = True

        variants = 1
        if allow_web:
            if complexity == "high":
                variants = 3
            elif complexity == "medium":
                variants = 2
            else:
                variants = 1
            if needs_fresh_web:
                variants = max(variants, 3)

        return {
            "route": route,
            "allow_web": allow_web,
            "request_clarification": request_clarification,
            "search_variants": variants,
            "complexity": complexity,
            "needs_fresh_web": needs_fresh_web,
            "topic": topic,
        }
