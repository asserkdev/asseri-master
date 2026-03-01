from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import requests


class SearchModule:
    """Online lookup with structured references and trusted-source prioritization."""

    USER_AGENT = "AsseriModularAI/2.1"
    TIMEOUT = 7

    TRUST_WEIGHTS = {
        "wikipedia.org": 0.82,
        "docs.python.org": 0.95,
        "developer.mozilla.org": 0.92,
        "pytorch.org": 0.91,
        "tensorflow.org": 0.91,
        "fastapi.tiangolo.com": 0.93,
        "duckduckgo.com": 0.62,
        "arxiv.org": 0.88,
        "google.com": 0.7,
        "customsearch.googleapis.com": 0.87,
    }

    def __init__(self) -> None:
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self.google_cse_id = os.getenv("GOOGLE_CSE_ID", "").strip()

    @classmethod
    def _ref_trust(cls, url: str) -> float:
        low = url.lower()
        for domain, weight in cls.TRUST_WEIGHTS.items():
            if domain in low:
                return weight
        return 0.55

    @classmethod
    def source_reliability(cls, references: list[dict[str, str]]) -> float:
        if not references:
            return 0.4
        scores = [cls._ref_trust(str(ref.get("url", ""))) for ref in references]
        return max(0.0, min(1.0, sum(scores) / len(scores)))

    def _trusted_references_for_query(self, query: str) -> list[dict[str, str]]:
        q = query.lower()
        refs: list[dict[str, str]] = []
        if any(k in q for k in ["python", "pip", "pydantic", "asyncio"]):
            refs.append(
                {
                    "title": "Python Official Docs",
                    "url": f"https://docs.python.org/3/search.html?q={quote(query)}",
                }
            )
        if any(k in q for k in ["javascript", "css", "html", "browser", "dom"]):
            refs.append(
                {
                    "title": "MDN Web Docs",
                    "url": f"https://developer.mozilla.org/en-US/search?q={quote(query)}",
                }
            )
        if any(k in q for k in ["research", "paper", "proof", "theorem"]):
            refs.append(
                {
                    "title": "arXiv Search",
                    "url": f"https://arxiv.org/search/?query={quote(query)}&searchtype=all",
                }
            )
        return refs

    def _merge_references(self, *groups: list[dict[str, str]]) -> list[dict[str, str]]:
        unique: dict[str, dict[str, str]] = {}
        for group in groups:
            for ref in group:
                url = str(ref.get("url", "")).strip()
                if not url:
                    continue
                unique[url] = {"title": str(ref.get("title", url)), "url": url}
        refs = list(unique.values())
        refs.sort(key=lambda r: self._ref_trust(r["url"]), reverse=True)
        return refs[:5]

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    def _http_json(self, url: str, params: dict[str, Any] | None = None) -> Any | None:
        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.TIMEOUT,
                headers={"User-Agent": self.USER_AGENT},
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    @staticmethod
    def _normalize_query(query: str) -> str:
        q = " ".join(query.strip().split())
        low = q.lower()
        low = re.sub(r"\bwhat\s+it\s+is\b", "what is", low)
        q = low
        for prefix in [
            "what is ",
            "what are ",
            "who is ",
            "where is ",
            "when is ",
            "why is ",
            "how is ",
            "tell me about ",
            "explain ",
        ]:
            if q.lower().startswith(prefix):
                q = q[len(prefix) :].strip()
                break
        while q.lower().startswith(("a ", "an ", "the ")):
            if q.lower().startswith("a "):
                q = q[2:].strip()
            elif q.lower().startswith("an "):
                q = q[3:].strip()
            elif q.lower().startswith("the "):
                q = q[4:].strip()
        q = re.sub(r"\bjob of\b", "purpose of", q)
        q = re.sub(r"\brole of\b", "purpose of", q)
        q = re.sub(r"\bfunction of\b", "purpose of", q)
        q = re.sub(r"^give me (\d+) sources? for ", "sources for ", q)
        q = re.sub(r"^give me sources? for ", "sources for ", q)
        q = re.sub(r"\bof the\b", "of ", q)
        q = re.sub(r"\s+", " ", q).strip()
        lower = q.lower()
        if lower in {"ai", "a i"}:
            q = "artificial intelligence"
        return q or query.strip()

    @staticmethod
    def _canon_token(token: str) -> str:
        t = token.lower().strip()
        if t.endswith("ies") and len(t) > 4:
            t = f"{t[:-3]}y"
        elif t.endswith("s") and len(t) > 3:
            t = t[:-1]
        aliases = {
            "airplane": "plane",
            "aeroplane": "plane",
            "aircraft": "plane",
            "planes": "plane",
            "women": "woman",
        }
        return aliases.get(t, t)

    @classmethod
    def _token_set(cls, text: str) -> set[str]:
        stop = {
            "the",
            "and",
            "for",
            "with",
            "this",
            "that",
            "what",
            "who",
            "where",
            "when",
            "why",
            "how",
            "about",
            "tell",
            "explain",
        }
        return {
            cls._canon_token(tok)
            for tok in re.findall(r"[a-z0-9]+", text.lower())
            if len(tok) >= 2 and cls._canon_token(tok) not in stop
        }

    @classmethod
    def _focus_tokens(cls, query: str) -> set[str]:
        q = cls._normalize_query(query)
        m = re.search(r"\b(?:of|for|about)\s+(.+)$", q)
        if m:
            scoped = cls._token_set(m.group(1))
            if scoped:
                return scoped
        return cls._token_set(q)

    @classmethod
    def _overlap_ratio(cls, query: str, text: str) -> float:
        focus = cls._focus_tokens(query)
        if not focus:
            return 0.0
        tset = cls._token_set(text)
        if not tset:
            return 0.0
        return len(focus & tset) / max(len(focus), 1)

    @classmethod
    def _text_consistency(cls, a: str, b: str) -> float:
        ta = cls._token_set(a)
        tb = cls._token_set(b)
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / max(len(ta | tb), 1)

    @classmethod
    def _is_relevant_hit(cls, query: str, text: str) -> bool:
        focus = cls._focus_tokens(query)
        if not focus:
            return True
        ratio = cls._overlap_ratio(query, text)
        if len(focus) <= 1:
            base_ok = ratio >= 1.0
        elif len(focus) == 2:
            base_ok = ratio >= 0.5
        else:
            base_ok = ratio >= 0.34
        if not base_ok:
            return False
        low_q = query.lower()
        if any(k in low_q for k in ["purpose of", "job of", "role of", "function of"]):
            low_t = text.lower()
            function_markers = [
                "purpose",
                "used for",
                "used to",
                "designed to",
                "main function",
                "serves to",
                "transport",
                "carry",
                "allows",
                "helps",
            ]
            return any(marker in low_t for marker in function_markers)
        return True

    @staticmethod
    def _is_ambiguous_text(text: str) -> bool:
        low = text.lower()
        return any(
            marker in low
            for marker in [
                "may refer to",
                "can refer to",
                "could refer to",
                "disambiguation",
                "multiple meanings",
            ]
        )

    def _wiki_best_title(self, query: str) -> str:
        payload = self._http_json(
            "https://en.wikipedia.org/w/api.php",
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 6,
                "format": "json",
            },
        )
        if not isinstance(payload, dict):
            return ""
        q = payload.get("query", {})
        if not isinstance(q, dict):
            return ""
        results = q.get("search", [])
        if not isinstance(results, list) or not results:
            return ""
        best_title = ""
        best_score = 0.0
        for item in results:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            snippet = str(item.get("snippet", "")).strip()
            if not title:
                continue
            score = self._overlap_ratio(query, f"{title} {snippet}")
            if "disambiguation" in title.lower():
                score -= 0.2
            if score > best_score:
                best_score = score
                best_title = title
        if best_title and best_score >= 0.18:
            return best_title
        return ""

    def _wiki_summary(self, query: str) -> tuple[str | None, list[dict[str, str]]]:
        title = self._wiki_best_title(query)
        if not title:
            return None, []

        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}"
        payload = self._http_json(summary_url)
        if not isinstance(payload, dict):
            return None, []
        page_type = str(payload.get("type", "")).strip().lower()
        extract = str(payload.get("extract", "")).strip()
        if not extract or page_type == "disambiguation" or self._is_ambiguous_text(extract):
            return None, []
        if not self._is_relevant_hit(query, f"{title} {extract}"):
            return None, []
        return extract[:540], [{"title": f"Wikipedia: {title}", "url": summary_url}]

    def _duckduckgo(self, query: str) -> tuple[str | None, list[dict[str, str]]]:
        payload = self._http_json(
            "https://api.duckduckgo.com/",
            {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            },
        )
        if not isinstance(payload, dict):
            return None, []
        for key in ("Answer", "AbstractText", "Definition"):
            text = str(payload.get(key, "")).strip()
            if text:
                if not self._is_relevant_hit(query, text):
                    continue
                url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json"
                return text[:540], [{"title": "DuckDuckGo Instant Answer", "url": url}]
        return None, []

    def _google_cse(self, query: str) -> tuple[str | None, list[dict[str, str]]]:
        if not self.google_api_key or not self.google_cse_id:
            return None, []
        payload = self._http_json(
            "https://customsearch.googleapis.com/customsearch/v1",
            {
                "key": self.google_api_key,
                "cx": self.google_cse_id,
                "q": query,
                "num": 1,
            },
        )
        if not isinstance(payload, dict):
            return None, []
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return None, []
        top = items[0] if isinstance(items[0], dict) else {}
        snippet = str(top.get("snippet", "")).strip()
        link = str(top.get("link", "")).strip()
        title = str(top.get("title", "Google Result")).strip() or "Google Result"
        if not snippet:
            return None, []
        if not self._is_relevant_hit(query, f"{title} {snippet}"):
            return None, []
        refs = [{"title": f"Google: {title}", "url": link}] if link else []
        return snippet[:540], refs

    @staticmethod
    def _google_link(query: str) -> dict[str, str]:
        return {"title": f"Google Search: {query}", "url": f"https://www.google.com/search?q={quote(query)}"}

    def _rank_candidates(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not candidates:
            return []
        for idx, item in enumerate(candidates):
            answer = str(item.get("answer", "")).strip()
            refs = list(item.get("references", []))
            base = float(item.get("base_confidence", 0.55))
            relevance = self._overlap_ratio(query, answer)
            trust = self.source_reliability(refs)
            peers = [c for i, c in enumerate(candidates) if i != idx]
            consensus = 0.0
            if peers:
                scores = [self._text_consistency(answer, str(peer.get("answer", ""))) for peer in peers]
                consensus = sum(scores) / len(scores)
            score = (self._clamp(base) * 0.45) + (trust * 0.25) + (relevance * 0.2) + (consensus * 0.1)
            if self._is_ambiguous_text(answer):
                score -= 0.1
            item["relevance"] = round(relevance, 3)
            item["trust"] = round(trust, 3)
            item["consensus"] = round(consensus, 3)
            item["score"] = round(self._clamp(score), 3)
        return sorted(candidates, key=lambda x: float(x.get("score", 0.0)), reverse=True)

    def _consensus_result(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        trusted_refs: list[dict[str, str]],
    ) -> dict[str, Any] | None:
        ranked = self._rank_candidates(query, candidates)
        if not ranked:
            return None
        best = ranked[0]
        best_answer = str(best.get("answer", "")).strip()
        if not best_answer:
            return None
        supporters: list[dict[str, Any]] = []
        for peer in ranked[1:]:
            consistency = self._text_consistency(best_answer, str(peer.get("answer", "")))
            if consistency >= 0.42:
                supporters.append(peer)
        ref_groups: list[list[dict[str, str]]] = [list(best.get("references", []))]
        for s in supporters[:2]:
            ref_groups.append(list(s.get("references", [])))
        ref_groups.append(trusted_refs)
        refs = self._merge_references(*ref_groups)
        support_count = 1 + len(supporters)
        base_score = float(best.get("score", 0.6))
        confidence = self._clamp(base_score + min(0.09, 0.03 * len(supporters)), 0.45, 0.92)
        notes = [
            "Collected evidence from multiple sources.",
            f"Selected source path: {best.get('name', 'unknown')}.",
            f"Consensus support count: {support_count}.",
        ]
        if support_count >= 2:
            notes.append("Multiple sources agreed on core facts.")
        return {
            "answer": best_answer,
            "references": refs,
            "confidence": confidence,
            "source_reliability": self.source_reliability(refs),
            "consensus_score": float(best.get("consensus", 0.0)),
            "support_count": support_count,
            "notes": notes,
        }

    def search(self, query: str) -> dict[str, Any]:
        query = query.strip()
        if not query:
            return {
                "answer": "I need a query to search.",
                "references": [],
                "confidence": 0.35,
                "source_reliability": 0.35,
            }
        normalized_query = self._normalize_query(query)

        trusted_refs = self._trusted_references_for_query(normalized_query)
        candidates: list[dict[str, Any]] = []

        wiki_answer, wiki_refs = self._wiki_summary(normalized_query)
        if wiki_answer:
            candidates.append(
                {
                    "name": "wikipedia",
                    "answer": wiki_answer,
                    "references": self._merge_references(wiki_refs, trusted_refs),
                    "base_confidence": 0.82,
                }
            )

        ddg_answer, ddg_refs = self._duckduckgo(normalized_query)
        if ddg_answer and not self._is_ambiguous_text(ddg_answer):
            candidates.append(
                {
                    "name": "duckduckgo",
                    "answer": ddg_answer,
                    "references": self._merge_references(ddg_refs, trusted_refs, [self._google_link(query)]),
                    "base_confidence": 0.74,
                }
            )

        google_answer, google_refs = self._google_cse(normalized_query)
        if google_answer:
            candidates.append(
                {
                    "name": "google_cse",
                    "answer": google_answer,
                    "references": self._merge_references(google_refs, trusted_refs, [self._google_link(query)]),
                    "base_confidence": 0.68,
                }
            )

        consensus = self._consensus_result(normalized_query, candidates, trusted_refs)
        if consensus:
            return consensus

        refs = self._merge_references(
            [self._google_link(query)],
            [{"title": f"DuckDuckGo Search: {query}", "url": f"https://duckduckgo.com/?q={quote(query)}"}],
            trusted_refs,
        )
        return {
            "answer": (
                f"I could not find a high-confidence summary for '{query}'. "
                "I added direct Google and search links for manual verification."
            ),
            "references": refs,
            "confidence": 0.45,
            "source_reliability": self.source_reliability(refs),
        }
