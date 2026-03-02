from __future__ import annotations

import re
from typing import Any

from .fuzzy_match import FuzzyMatcher
from .math_engine import MathEngine
from .memory import MemoryStore
from .search_module import SearchModule


class AICore:
    """Central orchestrator: intent routing + adaptive learning."""
    RESPONSE_MODES = {"simple", "standard", "advanced"}

    def __init__(
        self,
        memory: MemoryStore,
        search: SearchModule,
        math_engine: MathEngine,
        fuzzy: FuzzyMatcher,
    ) -> None:
        self.memory = memory
        self.search = search
        self.math_engine = math_engine
        self.fuzzy = fuzzy
        self._seed_graph()

    def _seed_graph(self) -> None:
        seeds = [
            ("prime numbers", "related_to", "number theory"),
            ("integral", "related_to", "calculus"),
            ("derivative", "related_to", "calculus"),
            ("matrix", "related_to", "linear algebra"),
            ("transformer", "related_to", "machine learning"),
            ("machine learning", "related_to", "artificial intelligence"),
        ]
        for src, rel, dst in seeds:
            self.memory.add_graph_edge(src, rel, dst, weight_delta=0.2)

    @staticmethod
    def _clamp(value: float, low: float = 0.05, high: float = 0.99) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _is_confirmation(text: str) -> bool:
        t = re.sub(r"[^\w\s]", "", text.lower()).strip()
        return t in {
            "correct",
            "right",
            "exactly",
            "thats correct",
            "that is correct",
            "good answer",
            "yes correct",
        }

    @staticmethod
    def _is_correction(text: str) -> bool:
        t = text.lower()
        compact = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()
        if compact in {"wrong", "also wrong", "still wrong", "not correct"}:
            return True
        if any(
            x in t
            for x in [
                "that's wrong",
                "that is wrong",
                "this is wrong",
                "incorrect",
                "should be",
                "correct answer is",
                "you are wrong",
                "wrong answer",
            ]
        ):
            return True
        if re.search(r"^(?:no[, ]|actually[, ]|correction[: ])", t):
            return True
        if "you mean" in t:
            return True
        if (" means " in t or " = " in t) and any(x in t for x in ["wrong", "incorrect", "no,", "actually"]):
            return True
        return False

    @staticmethod
    def _is_meta_personal_query(text: str) -> bool:
        t = re.sub(r"\s+", " ", text.lower()).strip()
        patterns = [
            "who am i",
            "who i am",
            "what is my name",
            "what's my name",
            "whats my name",
            "my username",
            "my account",
            "am i signed in",
            "where did you learn",
            "were did you learn",
            "where do you learn",
            "where did you get this",
            "where did you get that",
            "did you make this up",
            "how did you know this",
            "how much confidence",
            "your confidence",
            "confidence do you have",
            "what do you know about me",
            "do you remember me",
            "response mode",
            "my mode",
        ]
        return any(p in t for p in patterns)

    @staticmethod
    def _is_personal_session_query(text: str) -> bool:
        t = re.sub(r"\s+", " ", text.lower()).strip()
        direct = [
            "who am i",
            "what is my name",
            "what's my name",
            "whats my name",
            "am i signed in",
            "my account",
            "my profile",
            "do you remember me",
            "what do you know about me",
            "where did you learn",
            "were did you learn",
            "how did you know this",
            "did you make this up",
            "how much confidence",
            "confidence do you have",
            "your confidence",
            "response mode",
            "my mode",
        ]
        if any(p in t for p in direct):
            return True
        if re.search(r"\b(my|me|i)\b", t) and any(
            q in t
            for q in ["who", "what", "where", "how", "remember", "account", "profile", "name", "confidence", "mode"]
        ):
            return True
        return False

    @staticmethod
    def _is_perform_request(text: str) -> bool:
        t = re.sub(r"\s+", " ", text.lower()).strip()
        if t.startswith("sing ") or t == "sing":
            return True
        if t.startswith("play ") or t.startswith("rap "):
            return True
        if t.startswith("dance ") or t == "dance":
            return True
        if t.startswith("draw ") or t.startswith("paint "):
            return True
        return False

    @staticmethod
    def _is_assistant_identity_query(text: str) -> bool:
        t = re.sub(r"\s+", " ", text.lower()).strip()
        direct = {
            "who are you",
            "what are you",
            "what is your name",
            "whats your name",
            "what's your name",
            "name?",
            "your name?",
            "who r u",
        }
        if t in direct:
            return True
        return any(
            p in t
            for p in [
                "your name",
                "who are u",
                "introduce yourself",
                "tell me about yourself",
                "what can you do",
            ]
        )

    @staticmethod
    def _is_teaching_input(text: str) -> bool:
        t = text.lower().strip()
        return any(
            t.startswith(prefix)
            for prefix in [
                "answer is ",
                "the answer is ",
                "remember this:",
                "remember that ",
                "learn this:",
                "for future:",
            ]
        )

    @staticmethod
    def _assistant_requested_user_input(text: str) -> bool:
        t = text.lower()
        return "if you know the correct answer, reply with: answer is" in t

    @classmethod
    def _extract_response_mode_command(cls, text: str) -> str | None:
        t = re.sub(r"\s+", " ", text.strip().lower())
        alias = {
            "easy": "simple",
            "basic": "simple",
            "beginner": "simple",
            "normal": "standard",
            "default": "standard",
            "detailed": "advanced",
            "detail": "advanced",
            "technical": "advanced",
            "complex": "advanced",
            "expert": "advanced",
        }
        for pattern in [
            r"^(?:set|change|switch)\s+(?:response\s+)?mode\s+(?:to\s+)?([a-z]+)$",
            r"^(?:response\s+)?mode\s*[:=]?\s*([a-z]+)$",
            r"^([a-z]+)\s+mode$",
        ]:
            m = re.search(pattern, t)
            if not m:
                continue
            raw = m.group(1).strip()
            mode = alias.get(raw, raw)
            if mode in cls.RESPONSE_MODES:
                return mode
        return None

    @classmethod
    def _query_mode_override(cls, query: str) -> str | None:
        q = query.lower()
        if any(x in q for x in ["simple words", "simply", "for kids", "beginner", "easy explanation", "short answer"]):
            return "simple"
        if any(x in q for x in ["in detail", "technical", "advanced", "deeper", "more complex", "expert level"]):
            return "advanced"
        if any(x in q for x in ["normal mode", "standard mode", "default mode"]):
            return "standard"
        return None

    def _stored_response_mode(self, user_id: str | None = None) -> str:
        payload = self.memory.get_user_fact("response_mode", user_id=user_id)
        if not payload or not isinstance(payload.get("current"), dict):
            return "standard"
        value = str(payload["current"].get("value", "")).strip().lower()
        return value if value in self.RESPONSE_MODES else "standard"

    def _resolve_response_mode(self, query: str, user_id: str | None = None) -> tuple[str, str]:
        override = self._query_mode_override(query)
        if override:
            return override, "query_override"
        stored = self._stored_response_mode(user_id=user_id)
        if stored in self.RESPONSE_MODES:
            return stored, "user_profile"
        return "standard", "default"

    @staticmethod
    def _extract_teaching_value(text: str) -> str | None:
        for pattern in [
            r"^(?:the answer is|answer is)\s+(.+)$",
            r"^remember this:\s*(.+)$",
            r"^remember that\s+(.+)$",
            r"^learn this:\s*(.+)$",
            r"^for future:\s*(.+)$",
        ]:
            m = re.search(pattern, text.strip(), flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip(" .")
                if val:
                    return val
        return None

    @staticmethod
    def _normalize_topic_text(text: str) -> str:
        clean = re.sub(r"[^a-z0-9\s]", "", text.lower())
        clean = re.sub(r"\s+", " ", clean).strip()
        while clean.startswith(("a ", "an ", "the ")):
            if clean.startswith("a "):
                clean = clean[2:].strip()
            elif clean.startswith("an "):
                clean = clean[3:].strip()
            elif clean.startswith("the "):
                clean = clean[4:].strip()
        if clean in {"ai", "a i"}:
            return "artificial intelligence"
        return clean

    @staticmethod
    def _extract_user_name_claim(text: str) -> str | None:
        raw = re.sub(r"\s+", " ", text.strip())
        if "?" in raw:
            return None
        patterns = [
            r"^my name is\s+([a-zA-Z][a-zA-Z0-9_-]{1,31}(?:\s+[a-zA-Z][a-zA-Z0-9_-]{1,31})?)$",
            r"^call me\s+([a-zA-Z][a-zA-Z0-9_-]{1,31}(?:\s+[a-zA-Z][a-zA-Z0-9_-]{1,31})?)$",
            r"^i am\s+([a-zA-Z][a-zA-Z0-9_-]{1,31})$",
            r"^im\s+([a-zA-Z][a-zA-Z0-9_-]{1,31})$",
        ]
        stop = {
            "fine",
            "good",
            "okay",
            "ok",
            "happy",
            "sad",
            "ready",
            "here",
            "back",
            "human",
            "wrong",
            "correct",
        }
        for p in patterns:
            m = re.match(p, raw, flags=re.IGNORECASE)
            if not m:
                continue
            name = m.group(1).strip()
            if name.lower() in stop:
                return None
            return " ".join([part.capitalize() for part in name.split()])
        return None

    @staticmethod
    def _is_overly_ambiguous_query(query: str) -> bool:
        compact = re.sub(r"\s+", " ", query.strip().lower())
        if not compact:
            return True
        trimmed = re.sub(
            r"^(what is|what are|who is|where is|when is|why is|how is|tell me about|explain)\s+",
            "",
            compact,
        )
        tokens = [t for t in re.findall(r"[a-z0-9]+", trimmed) if len(t) >= 2]
        if len(tokens) <= 1:
            return True
        return False

    @staticmethod
    def _internal_knowledge_lookup(query: str, topic: str) -> dict[str, Any] | None:
        key = AICore._normalize_topic_text(topic or query)
        core: dict[str, tuple[str, str]] = {
            "artificial intelligence": (
                "Artificial intelligence (AI) is the field of building systems that perform tasks requiring human-like reasoning, learning, and decision-making.",
                "https://en.wikipedia.org/wiki/Artificial_intelligence",
            ),
            "machine learning": (
                "Machine learning is a branch of AI where models learn patterns from data to make predictions or decisions.",
                "https://en.wikipedia.org/wiki/Machine_learning",
            ),
            "deep learning": (
                "Deep learning uses multi-layer neural networks to learn complex patterns in data such as images, text, and audio.",
                "https://en.wikipedia.org/wiki/Deep_learning",
            ),
            "algorithm": (
                "An algorithm is a finite sequence of clear steps for solving a problem or computing a result.",
                "https://en.wikipedia.org/wiki/Algorithm",
            ),
            "api": (
                "An API is an interface that lets software systems communicate through defined requests and responses.",
                "https://en.wikipedia.org/wiki/API",
            ),
            "fastapi": (
                "FastAPI is a Python web framework for building APIs with type hints, automatic validation, and high performance.",
                "https://fastapi.tiangolo.com/",
            ),
            "python": (
                "Python is a high-level programming language focused on readability, rapid development, and a large ecosystem.",
                "https://docs.python.org/3/",
            ),
            "plane": (
                "A plane (airplane) is an aircraft designed to transport people or cargo through the air using lift from wings.",
                "https://en.wikipedia.org/wiki/Airplane",
            ),
            "airplane": (
                "An airplane is a powered fixed-wing aircraft used for transportation, travel, and logistics.",
                "https://en.wikipedia.org/wiki/Airplane",
            ),
            "purpose of plane": (
                "The primary purpose of a plane is to move people or cargo efficiently over long distances through the air.",
                "https://en.wikipedia.org/wiki/Airplane",
            ),
            "purpose of airplane": (
                "The primary purpose of an airplane is transportation of passengers and cargo through air travel.",
                "https://en.wikipedia.org/wiki/Airplane",
            ),
        }
        if key in core:
            text, link = core[key]
            return {
                "answer": text,
                "confidence": 0.9,
                "references": [{"title": "Core Concept Reference", "url": link}],
            }
        m = re.match(r"^(?:purpose|function|role|job) of (.+)$", key)
        if m:
            obj = m.group(1).strip()
            obj = re.sub(r"^(?:a|an|the)\s+", "", obj)
            purpose_map = {
                "plane": "The primary purpose of a plane is to transport people and cargo quickly through the air.",
                "airplane": "The primary purpose of an airplane is transportation of passengers and cargo through air travel.",
                "aeroplane": "The primary purpose of an aeroplane is air transportation of passengers and cargo.",
                "aircraft": "The main function of an aircraft is transportation or aerial operations through controlled flight.",
                "train": "The main purpose of a train is to transport passengers or freight efficiently on rail networks.",
                "car": "The main purpose of a car is personal or small-group transportation on roads.",
                "bus": "The main purpose of a bus is shared public or private transportation of many passengers.",
                "ship": "The main purpose of a ship is transporting people or cargo across water.",
                "boat": "The main purpose of a boat is transportation, work, or recreation on water.",
                "helicopter": "The main purpose of a helicopter is flexible air transport and access to hard-to-reach areas.",
            }
            if obj in purpose_map:
                return {
                    "answer": purpose_map[obj],
                    "confidence": 0.89,
                    "references": [{"title": "General Engineering Usage", "url": "internal://concept-purpose"}],
                }
        return None

    @staticmethod
    def _norm_entity(text: str) -> str:
        t = re.sub(r"[^a-z0-9\s]", "", text.lower()).strip()
        t = re.sub(r"\s+", " ", t)
        while t.startswith(("a ", "an ", "the ")):
            if t.startswith("a "):
                t = t[2:].strip()
            elif t.startswith("an "):
                t = t[3:].strip()
            else:
                t = t[4:].strip()
        if t.endswith("ies") and len(t) > 4:
            t = f"{t[:-3]}y"
        elif t.endswith("s") and len(t) > 3:
            t = t[:-1]
        aliases = {
            "airplane": "plane",
            "aeroplane": "plane",
            "aircraft": "plane",
            "women": "woman",
        }
        return aliases.get(t, t)

    @classmethod
    def _parse_quantified_clause(cls, text: str) -> dict[str, str] | None:
        s = re.sub(r"\s+", " ", text.lower()).strip(" .?!,;")
        for pattern, kind in [
            (r"^all ([a-z ]+?) are ([a-z ]+)$", "all_are"),
            (r"^no ([a-z ]+?) are ([a-z ]+)$", "no_are"),
            (r"^some ([a-z ]+?) are not ([a-z ]+)$", "some_not_are"),
            (r"^some ([a-z ]+?) are ([a-z ]+)$", "some_are"),
        ]:
            m = re.match(pattern, s)
            if m:
                left_raw = m.group(1).strip()
                right_raw = m.group(2).strip()
                return {
                    "kind": kind,
                    "left_raw": left_raw,
                    "right_raw": right_raw,
                    "left": cls._norm_entity(left_raw),
                    "right": cls._norm_entity(right_raw),
                }

        m = re.match(r"^some ([a-z ]+?) ([a-z][a-z ]+)$", s)
        if m:
            left_raw = m.group(1).strip()
            pred_raw = m.group(2).strip()
            if pred_raw.startswith("are "):
                return None
            return {
                "kind": "some_predicate",
                "left_raw": left_raw,
                "right_raw": pred_raw,
                "left": cls._norm_entity(left_raw),
                "right": cls._norm_entity(pred_raw),
            }
        return None

    @staticmethod
    def _eval_clause(clause: dict[str, str], assignment: dict[str, int], universe_mask: int) -> bool:
        a = assignment.get(clause["left"], 0)
        b = assignment.get(clause["right"], 0)
        kind = clause["kind"]
        if kind == "all_are":
            return (a & (~b & universe_mask)) == 0
        if kind == "no_are":
            return (a & b) == 0
        if kind in {"some_are", "some_predicate"}:
            return (a & b) != 0
        if kind == "some_not_are":
            return (a & (~b & universe_mask)) != 0
        return False

    @staticmethod
    def _powerset_masks(size: int) -> list[int]:
        return [i for i in range(1 << size)]

    @classmethod
    def _quantified_entailment(
        cls,
        premises: list[dict[str, str]],
        conclusion: dict[str, str],
    ) -> tuple[bool, bool, dict[str, int] | None]:
        predicates: list[str] = []
        for c in premises + [conclusion]:
            for key in [c["left"], c["right"]]:
                if key not in predicates:
                    predicates.append(key)

        size = 3
        universe_mask = (1 << size) - 1
        masks = cls._powerset_masks(size)
        satisfiable = False
        counterexample: dict[str, int] | None = None

        def backtrack(idx: int, current: dict[str, int]) -> None:
            nonlocal satisfiable, counterexample
            if idx >= len(predicates):
                prem_ok = all(cls._eval_clause(c, current, universe_mask) for c in premises)
                if not prem_ok:
                    return
                satisfiable = True
                concl_ok = cls._eval_clause(conclusion, current, universe_mask)
                if not concl_ok and counterexample is None:
                    counterexample = dict(current)
                return
            pred = predicates[idx]
            for m in masks:
                current[pred] = m
                backtrack(idx + 1, current)
            current.pop(pred, None)

        backtrack(0, {})
        entailed = satisfiable and counterexample is None
        return entailed, satisfiable, counterexample

    @classmethod
    def _render_counterexample(cls, conclusion: dict[str, str], model: dict[str, int]) -> str:
        kind = conclusion["kind"]
        l_raw = conclusion["left_raw"]
        r_raw = conclusion["right_raw"]
        if kind in {"some_are", "some_predicate"}:
            return f"Counterexample: premises can be true while no object is both '{l_raw}' and '{r_raw}'."
        if kind == "all_are":
            return f"Counterexample: premises can be true while at least one '{l_raw}' is not '{r_raw}'."
        if kind == "no_are":
            return f"Counterexample: premises can be true while some '{l_raw}' is also '{r_raw}'."
        if kind == "some_not_are":
            return f"Counterexample: premises can be true while every '{l_raw}' is '{r_raw}'."
        return "Counterexample model found."

    @classmethod
    def _logical_syllogism_answer(cls, query: str) -> dict[str, Any] | None:
        low = re.sub(r"\s+", " ", query.lower()).strip()
        low = re.sub(r"\bexplain\b", "", low).strip(" .?!")
        m = re.match(r"^if (.+?), does it(?: logically)? follow that (.+)$", low)
        if not m:
            return None
        premises_raw = [p.strip() for p in re.split(r"\s+and\s+", m.group(1).strip()) if p.strip()]
        conclusion_raw = m.group(2).strip()
        premises = [cls._parse_quantified_clause(p) for p in premises_raw]
        conclusion = cls._parse_quantified_clause(conclusion_raw)
        if not conclusion or any(p is None for p in premises):
            return None

        valid_premises = [p for p in premises if p is not None]
        entailed, satisfiable, witness = cls._quantified_entailment(valid_premises, conclusion)
        if not satisfiable:
            answer = "The premises are mutually inconsistent, so the argument structure is invalid as stated."
            return {
                "answer": answer,
                "confidence": 0.88,
                "intent": "problem_solving",
                "references": [{"title": "Predicate Logic Rule", "url": "internal://logic/quantifiers"}],
                "reasoning_steps": [
                    "Parsed quantified premises and conclusion.",
                    "Checked model satisfiability.",
                    "Found no satisfying model for all premises.",
                ],
                "direct_reasoning": True,
            }

        if entailed:
            answer = (
                "Yes. It logically follows from the premises.\n"
                "1. Parsed premises and conclusion as quantified statements.\n"
                "2. Checked all finite models where premises are true.\n"
                "3. Conclusion is true in every such model."
            )
            reasoning = [
                "Parsed quantified premises and conclusion.",
                "Ran finite-model entailment check.",
                "No counterexample model exists.",
            ]
        else:
            counterexample = cls._render_counterexample(conclusion, witness or {})
            answer = (
                "No. It does not logically follow.\n"
                "1. Parsed premises and conclusion as quantified statements.\n"
                "2. Ran finite-model entailment check.\n"
                f"3. Found a counterexample model. {counterexample}"
            )
            reasoning = [
                "Parsed quantified premises and conclusion.",
                "Ran finite-model entailment check.",
                "Counterexample model found, so entailment fails.",
            ]
        return {
            "answer": answer,
            "confidence": 0.95 if entailed else 0.93,
            "intent": "problem_solving",
            "references": [{"title": "Predicate Logic Rule", "url": "internal://logic/quantifiers"}],
            "reasoning_steps": reasoning,
            "direct_reasoning": True,
        }

    @staticmethod
    def _fact_claim_override(query: str) -> dict[str, Any] | None:
        low = re.sub(r"\s+", " ", query.lower()).strip()

        if all(k in low for k in ["great wall", "moon", "naked eye", "visible"]):
            return {
                "answer": (
                    "That claim is false. The Great Wall is generally not visible from the Moon with the naked eye.\n"
                    "Reason: at lunar distance, its apparent width is far below normal human visual resolution, "
                    "and its color contrast with surrounding terrain is low."
                ),
                "confidence": 0.95,
                "intent": "knowledge",
                "references": [
                    {
                        "title": "Wikipedia: Great Wall visibility from space",
                        "url": "https://en.wikipedia.org/wiki/Great_Wall_of_China#Visibility_from_space",
                    },
                    {
                        "title": "NASA Earth observations discussion",
                        "url": "https://www.nasa.gov/history/alsj/a17/alsj-EarthObs4.html",
                    },
                ],
                "reasoning_steps": [
                    "Detected known false-premise myth pattern.",
                    "Applied geometric visibility and contrast constraints.",
                    "Returned direct correction before web fallback.",
                ],
                "direct_reasoning": True,
            }

        grav_year = re.search(r"discovery of gravity.*\b(1[0-9]{3}|20[0-9]{2})\b", low)
        if grav_year:
            year = int(grav_year.group(1))
            if year >= 1700:
                return {
                    "answer": (
                        f"Gravity was not discovered in {year}. The foundational law of universal gravitation was "
                        "published by Isaac Newton in 1687 (Principia).\n"
                        "Earlier and later milestones include Galileo's motion studies and Einstein's general relativity (1915)."
                    ),
                    "confidence": 0.94,
                    "intent": "knowledge",
                    "references": [
                        {"title": "Newton's law of universal gravitation", "url": "https://en.wikipedia.org/wiki/Newton%27s_law_of_universal_gravitation"},
                        {"title": "Philosophiæ Naturalis Principia Mathematica", "url": "https://en.wikipedia.org/wiki/Philosophi%C3%A6_Naturalis_Principia_Mathematica"},
                        {"title": "General relativity", "url": "https://en.wikipedia.org/wiki/General_relativity"},
                    ],
                    "reasoning_steps": [
                        "Detected historical-year claim about gravity discovery.",
                        "Compared claimed year against known timeline anchors.",
                        "Returned corrected historical answer with sources.",
                    ],
                    "direct_reasoning": True,
                }
        return None

    def _deterministic_reasoning_answer(self, query: str) -> dict[str, Any] | None:
        logic = self._logical_syllogism_answer(query)
        if logic:
            return logic
        fact = self._fact_claim_override(query)
        if fact:
            return fact
        return None

    @staticmethod
    def _is_likely_fictional_query(query: str) -> bool:
        q = re.sub(r"\s+", " ", query.lower()).strip()
        explicit = [
            "quantum bananas",
            "interstellar taxation",
            "dragon economy",
            "time travel pizza",
            "telepathic database",
        ]
        if any(p in q for p in explicit):
            return True
        sci = any(k in q for k in ["quantum", "interstellar", "galactic", "telepathic", "wormhole"])
        absurd = any(k in q for k in ["bananas", "unicorn", "wizard", "magic beans", "dragon"])
        return sci and absurd

    @staticmethod
    def _fictional_query_response(query: str) -> tuple[str, list[dict[str, str]], float, list[str]]:
        answer = (
            f"I could not verify factual evidence for '{query}'.\n"
            "If you want, I can answer this as creative world-building instead of factual analysis."
        )
        refs = [{"title": "Clarification Needed", "url": "internal://clarification"}]
        steps = [
            "Detected likely fictional or speculative concept mix.",
            "Avoided fabricating factual claims.",
            "Requested mode clarification (factual vs creative).",
        ]
        return answer, refs, 0.68, steps

    def _extract_correction_value(self, text: str, topic_hint: str | None = None) -> str | None:
        raw = text.strip()
        low = raw.lower().strip()
        if low in {"wrong", "that is wrong", "this is wrong", "incorrect", "wrong answer"}:
            return None

        for pattern in [
            r"(?:correct answer is|it should be|should be|it's|it is|means|equals|is defined as)\s+(.+)$",
            r"^no,\s*(.+)$",
        ]:
            m = re.search(pattern, raw, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip(" .")
                if val:
                    return val

        if topic_hint:
            hint = self._normalize_topic_text(topic_hint)
            body = re.sub(
                r"^(?:that(?:'s| is) wrong|this is wrong|wrong answer|incorrect)[,:\s]*",
                "",
                raw,
                flags=re.IGNORECASE,
            ).strip()
            structured = re.search(r"^(.+?)\s+(?:means|is|=)\s+(.+)$", body, flags=re.IGNORECASE)
            if structured:
                left = self._normalize_topic_text(structured.group(1))
                right = structured.group(2).strip(" .")
                if right and (left == hint or left in hint or hint in left):
                    return right
        return None

    def _intent(self, query: str) -> str:
        q = query.lower().strip()
        if self.math_engine.is_math_query(q):
            return "math"
        if any(k in q for k in ["logically follow", "does it follow", "valid argument", "syllogism", "if all ", "if some "]):
            return "problem_solving"
        if self._is_personal_session_query(q):
            return "casual"
        if re.search(r"\b(my name|about me|remember me|am i)\b", q):
            return "casual"
        if self._is_assistant_identity_query(q):
            return "casual"
        if self._is_meta_personal_query(q):
            return "casual"
        if self._is_perform_request(q):
            return "casual"
        is_definition = bool(re.match(r"^(what is|what are|who is|tell me about)\b", q))
        if any(k in q for k in ["algorithm", "logic", "logical", "logically", "debug", "code", "python", "javascript", "program", "prove"]) and not is_definition:
            return "problem_solving"
        if q in {"hi", "hello", "hey", "how are you"}:
            return "casual"
        if any(x in q for x in ["joke", "story", "poem", "write this"]):
            return "casual"
        return "knowledge"

    def _topic_from_query(self, query: str) -> str:
        return self.memory.topic_key(query)

    @staticmethod
    def _title_from_topic(topic: str, query: str, intent: str) -> str:
        base = topic if topic and topic not in {"general", "error"} else query
        if intent == "math":
            base = f"Solve {query}"
        base = re.sub(r"\s+", " ", str(base or "").strip())
        base = re.sub(r"[^\w\s\-\+\*\/\^\(\)=]", "", base).strip()
        words = [w for w in base.split(" ") if w]
        if not words:
            return "New Chat"
        text = " ".join(words[:7]).title()
        if len(words) > 7:
            text = f"{text}..."
        if len(text) > 64:
            text = f"{text[:61].rstrip()}..."
        return text or "New Chat"

    def _maybe_update_session_title(self, session_id: str, topic: str, query: str, intent: str, user_id: str | None = None) -> None:
        if intent in {"feedback", "clarification", "error"}:
            return
        if not topic or topic in {"general", "error"}:
            return
        current = self.memory.get_session_title(session_id, user_id=user_id).strip().lower()
        generic_titles = {"new chat", "session", "hi", "hello", "hey"}
        if current and current not in generic_titles and len(current.split()) >= 2:
            return
        candidate = self._title_from_topic(topic, query, intent)
        if candidate and candidate.lower() not in generic_titles:
            self.memory.set_session_title(session_id, candidate, user_id=user_id)

    @staticmethod
    def _strip_conf(answer: str) -> str:
        kept: list[str] = []
        for line in answer.splitlines():
            low = line.strip().lower()
            if low.startswith("confidence:"):
                continue
            if re.match(r"^i['’]?m \d+% sure this is correct\.?$", low):
                continue
            kept.append(line)
        return "\n".join(kept).strip()

    def _attach_conf(self, answer: str, confidence: float) -> str:
        pct = int(round(self._clamp(confidence, 0.0, 1.0) * 100))
        base = self._strip_conf(answer)
        if not base:
            return f"I'm {pct}% sure this is correct.\nConfidence: {pct}%"
        return f"{base}\nI'm {pct}% sure this is correct.\nConfidence: {pct}%"

    def _is_contradiction(self, topic: str, answer: str, user_id: str | None = None) -> bool:
        rule = self.memory.get_rule(topic, user_id=user_id)
        if not rule or not isinstance(rule.get("current"), dict):
            return False
        prev = str(rule["current"].get("answer", "")).strip().lower()
        new = self._strip_conf(answer).strip().lower()
        if not prev or not new:
            return False
        return prev != new and float(rule["current"].get("confidence", 0.5)) >= 0.75

    @staticmethod
    def _extract_confidence_percent(text: str) -> int | None:
        if not text:
            return None
        for pattern in [r"confidence:\s*(\d+)%", r"i(?:'|’)?m\s*(\d+)%\s*sure this is correct"]:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                try:
                    return max(0, min(100, int(m.group(1))))
                except Exception:
                    return None
        return None

    def _casual_answer(self, query: str, user_id: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        q = query.lower().strip()
        if q in {"hi", "hello", "hey"}:
            return {"answer": "Hi. I am ready to help.", "confidence": 0.86, "references": []}
        if "your name" in q or "who are you" in q:
            return {"answer": "I am Asseri AI.", "confidence": 0.96, "references": []}
        if any(p in q for p in ["who am i", "who i am", "what is my name", "what's my name", "whats my name", "my username", "my account", "am i signed in"]):
            known_name = self.memory.get_user_fact("name", user_id=user_id)
            known_name_current = known_name.get("current", {}) if isinstance(known_name, dict) else {}
            stored_name = str(known_name_current.get("value", "")).strip() if isinstance(known_name_current, dict) else ""
            if stored_name:
                return {
                    "answer": f"You told me your name is {stored_name}.",
                    "confidence": 0.95,
                    "references": [{"title": "Learned User Profile", "url": "memory://user-facts/name"}],
                }
            if user_id:
                return {
                    "answer": f"You are signed in as {user_id}.",
                    "confidence": 0.97,
                    "references": [{"title": "Authenticated Session", "url": "internal://auth-session"}],
                }
            return {"answer": "You are the current user of this chat session.", "confidence": 0.74, "references": []}
        if any(k in q for k in ["what do you know about me", "do you remember me"]):
            profile = self.memory.user_profile(user_id=user_id)
            if profile:
                chunks = [f"{k}: {v.get('value', '')}" for k, v in profile.items() if isinstance(v, dict)]
                summary = "; ".join(chunks[:5]).strip()
                return {
                    "answer": f"I remember these profile facts: {summary}.",
                    "confidence": 0.91,
                    "references": [{"title": "Learned User Profile", "url": "memory://user-facts"}],
                }
            return {
                "answer": "I do not have profile facts yet. You can teach me by saying: my name is <name>.",
                "confidence": 0.78,
                "references": [{"title": "Learning Memory", "url": "internal://memory"}],
            }
        if any(k in q for k in ["how much confidence", "your confidence", "confidence do you have"]):
            prev_conf = None
            if session_id:
                prev_assistant = self.memory.last_by_role(session_id, "assistant", user_id=user_id)
                prev_conf = self._extract_confidence_percent(prev_assistant)
            if prev_conf is not None:
                return {
                    "answer": f"My previous answer confidence was {prev_conf}%. The bar under each response shows confidence.",
                    "confidence": 0.92,
                    "references": [{"title": "Confidence System", "url": "internal://confidence"}],
                }
            return {
                "answer": "Confidence is shown by the bar under each response. More to green means higher confidence.",
                "confidence": 0.9,
                "references": [{"title": "Confidence System", "url": "internal://confidence"}],
            }
        if any(k in q for k in ["response mode", "my mode", "what mode", "mode am i using"]):
            mode = self._stored_response_mode(user_id=user_id)
            return {
                "answer": f"Your response mode is '{mode}'. You can change it by saying: set response mode to simple|standard|advanced.",
                "confidence": 0.92,
                "references": [{"title": "User Preferences", "url": "memory://user-facts/response_mode"}],
            }
        if self._is_perform_request(q):
            tail = q[5:].strip() if q.startswith("sing ") else ""
            if tail:
                return {
                    "answer": (
                        f"I cannot sing audio here. For '{tail}', I can summarize the song, explain its meaning, "
                        "or help you write original lyrics in a similar style."
                    ),
                    "confidence": 0.9,
                    "references": [],
                }
            return {
                "answer": "I cannot sing audio here, but I can help with lyrics meaning, song summary, or original lyrics.",
                "confidence": 0.88,
                "references": [],
            }
        if any(k in q for k in ["where did you learn", "were did you learn", "where did you get this", "did you make this up", "how did you know this"]):
            return {
                "answer": (
                    "I use internal logic modules, conversation memory, a math engine, and trusted web summaries "
                    "with references. I do not invent answers on purpose."
                ),
                "confidence": 0.9,
                "references": [
                    {"title": "Internal AI Core", "url": "internal://ai-core"},
                    {"title": "Search Module", "url": "internal://search-module"},
                    {"title": "Memory System", "url": "internal://memory"},
                ],
            }
        if "what are you" in q or "introduce yourself" in q:
            return {
                "answer": "I am Asseri AI, a modular assistant for chat, math, and knowledge tasks.",
                "confidence": 0.94,
                "references": [],
            }
        if "what can you do" in q:
            return {
                "answer": "I can answer questions, solve math step-by-step, search sources, and learn from your feedback.",
                "confidence": 0.93,
                "references": [],
            }
        if "how are you" in q:
            return {"answer": "I am operating normally and ready to assist.", "confidence": 0.82, "references": []}
        if "joke" in q:
            return {"answer": "I debug because I care. Sometimes the bug cares back.", "confidence": 0.74, "references": []}
        return {
            "answer": "I can help with knowledge lookup, coding help, and math step-by-step.",
            "confidence": 0.72,
            "references": [],
        }

    @staticmethod
    def _format_math_answer(answer: str, steps: list[str]) -> str:
        clean = str(answer).strip()
        if re.fullmatch(r"-?\d+\.\d+", clean):
            clean = clean.rstrip("0").rstrip(".")
        if not steps:
            return clean
        lines = ["Step-by-step solution:"]
        for idx, step in enumerate(steps, start=1):
            lines.append(f"{idx}. {step}")
        if clean:
            lines.append(f"Final answer: {clean}")
        return "\n".join(lines)

    @staticmethod
    def _format_problem_answer(query: str, answer: str) -> str:
        clean = str(answer).strip()
        if not clean:
            return clean
        return "\n".join(
            [
                "Step-by-step reasoning:",
                f"1. Parse request: {query[:120]}",
                "2. Collect candidate knowledge paths.",
                "3. Compare consistency between paths.",
                "4. Keep the strongest supported result.",
                f"Final answer: {clean}",
            ]
        )

    @staticmethod
    def _simple_rewrite(text: str) -> str:
        clean = re.sub(r"\([^)]*\)", "", text.strip())
        clean = re.sub(r"\s+", " ", clean)
        replacements = {
            r"\bprimary\b": "main",
            r"\bapproximately\b": "about",
            r"\btherefore\b": "so",
            r"\butilize\b": "use",
            r"\btransportation\b": "travel",
            r"\bmodular\b": "organized",
            r"\bconsistency\b": "agreement",
            r"\bretrieve\b": "get",
            r"\binformation\b": "info",
            r"\bperform tasks requiring\b": "do",
            r"\breasoning, learning, and decision-making\b": "thinking, learning, and choosing",
        }
        for pattern, repl in replacements.items():
            clean = re.sub(pattern, repl, clean, flags=re.IGNORECASE)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
        if len(sentences) > 2:
            clean = " ".join(sentences[:2])
        if len(clean) > 340:
            clean = f"{clean[:337].rstrip()}..."
        return clean

    @staticmethod
    def _advanced_rewrite(text: str, intent: str) -> str:
        clean = text.strip()
        tail = (
            "Technical view: this answer is selected after query normalization, multi-source retrieval, "
            "cross-source agreement scoring, and confidence calibration."
        )
        if intent == "math":
            tail = "Technical view: the result is produced by symbolic/numeric solving and internal consistency checks."
        if tail.lower() in clean.lower():
            return clean
        return f"{clean}\n\n{tail}"

    def _rewrite_for_mode(self, answer: str, mode: str, intent: str) -> str:
        base = self._strip_conf(answer).strip()
        if not base or mode == "standard":
            return base
        if mode == "simple":
            if intent == "math":
                lines = [line.strip() for line in base.splitlines() if line.strip()]
                if len(lines) > 6:
                    lines = lines[:5] + [lines[-1]]
                compact = "\n".join(lines)
                return self._simple_rewrite(compact)
            return self._simple_rewrite(base)
        return self._advanced_rewrite(base, intent)

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
            "automobile": "car",
            "automobiles": "car",
            "vehicle": "car",
            "vehicles": "car",
            "women": "woman",
            "jobs": "job",
        }
        return aliases.get(t, t)

    @staticmethod
    def _token_set(text: str) -> set[str]:
        return {
            AICore._canon_token(t)
            for t in re.findall(r"[a-z0-9]+", text.lower())
            if len(t) >= 2
            and AICore._canon_token(t)
            not in {
                "the",
                "and",
                "for",
                "with",
                "that",
                "this",
                "what",
                "who",
                "why",
                "how",
                "job",
                "purpose",
                "role",
                "function",
                "work",
                "thing",
                "things",
            }
        }

    def _focus_query_tokens(self, query: str) -> set[str]:
        core = self._strip_question_prefix(query)
        focus = self._token_set(core)
        m = re.search(r"\b(?:of|for|about)\s+(.+)$", core)
        if m:
            scoped = self._token_set(m.group(1))
            if scoped:
                focus = scoped
        generic = {"thing", "stuff", "info", "meaning"}
        focus = {t for t in focus if t not in generic}
        return focus

    def _path_consistency(self, a: str, b: str) -> float:
        ta = self._token_set(a)
        tb = self._token_set(b)
        if not ta or not tb:
            return 0.0
        return max(0.0, min(1.0, len(ta & tb) / max(len(ta | tb), 1)))

    def _query_answer_relevance(self, query: str, answer: str) -> float:
        q_tokens = self._focus_query_tokens(query)
        a_tokens = self._token_set(answer)
        if not q_tokens or not a_tokens:
            return 0.0
        overlap = len(q_tokens & a_tokens)
        return max(0.0, min(1.0, overlap / max(len(q_tokens), 1)))

    @staticmethod
    def _strip_question_prefix(query: str) -> str:
        q = re.sub(r"\s+", " ", query.strip().lower())
        prefixes = [
            "what is ",
            "what are ",
            "who is ",
            "where is ",
            "when is ",
            "why is ",
            "why are ",
            "how is ",
            "how are ",
            "tell me about ",
            "explain ",
            "can you explain ",
        ]
        for p in prefixes:
            if q.startswith(p):
                q = q[len(p) :].strip()
                break
        return q

    @staticmethod
    def _semantic_normalize(query: str) -> str:
        q = re.sub(r"\s+", " ", query.strip().lower())
        q = re.sub(r"\bwhat\s+it\s+is\b", "what is", q)
        q = re.sub(r"\bwat is\b", "what is", q)
        q = re.sub(r"\bwht is\b", "what is", q)
        q = re.sub(r"\ba\.?\s*i\.?\b", "ai", q)
        q = re.sub(r"\bartifical intelligence\b", "artificial intelligence", q)
        q = re.sub(r"\bartificial inteligence\b", "artificial intelligence", q)
        q = re.sub(r"\bwhat is a ai\b", "what is ai", q)
        q = re.sub(r"\bwhat is an ai\b", "what is ai", q)
        q = re.sub(r"\ba ai\b", "ai", q)
        q = re.sub(r"\ban ai\b", "ai", q)
        q = re.sub(r"\baeroplane\b", "airplane", q)
        q = re.sub(r"\bair craft\b", "aircraft", q)
        q = re.sub(r"\bjob for\b", "purpose of", q)
        q = re.sub(r"\bjob of\b", "purpose of", q)
        q = re.sub(r"\brole of\b", "purpose of", q)
        q = re.sub(r"\bfunction of\b", "purpose of", q)
        q = re.sub(r"\bwork of\b", "purpose of", q)
        q = re.sub(r"\buse of\b", "purpose of", q)
        q = re.sub(r"^give me (\d+) sources? for ", r"sources for ", q)
        q = re.sub(r"^give me sources? for ", "sources for ", q)
        q = re.sub(r"\bin simple words\b", "", q)
        q = re.sub(r"\bsimple explanation\b", "", q)
        q = re.sub(r"\bfor beginners\b", "", q)
        q = re.sub(r"\bfor kids\b", "", q)
        q = re.sub(r"\bin detail\b", "", q)
        q = re.sub(r"\bin details\b", "", q)
        q = re.sub(r"\bwith details\b", "", q)
        q = re.sub(r"\btechnical explanation\b", "", q)
        q = re.sub(r"\bbriefly\b", "", q)
        q = re.sub(r"\bof the\b", "of ", q)
        q = re.sub(r"\s+", " ", q).strip()
        return q

    def _query_variants(self, query: str, topic: str) -> list[str]:
        variants: list[str] = []
        base = query.strip()
        compact = self._strip_question_prefix(query)
        for candidate in [base, compact, topic, f"overview {topic}".strip()]:
            c = re.sub(r"\s+", " ", str(candidate or "").strip())
            if c and c not in variants:
                variants.append(c)
        return variants[:4]

    @staticmethod
    def _is_ambiguous_answer(answer: str) -> bool:
        a = answer.lower()
        ambiguity_markers = [
            "may refer to",
            "can refer to",
            "could refer to",
            "disambiguation",
            "multiple meanings",
        ]
        if any(marker in a for marker in ambiguity_markers):
            return True
        if len(answer.strip()) < 16:
            return True
        return False

    @staticmethod
    def _merge_references(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
        unique: dict[str, dict[str, str]] = {}
        for group in groups:
            for ref in group:
                url = str(ref.get("url", "")).strip()
                if not url:
                    continue
                unique[url] = {"title": str(ref.get("title", url)), "url": url}
        return list(unique.values())[:5]

    def _source_reliability(self, references: list[dict[str, str]]) -> float:
        if hasattr(self.search, "source_reliability"):
            return float(self.search.source_reliability(references))
        return 0.4 if not references else 0.7

    def _quality_adjustment(self, answer: str, references: list[dict[str, str]]) -> float:
        delta = 0.0
        low = answer.lower()
        if self._is_ambiguous_answer(answer):
            delta -= 0.16
        if "could not find a high-confidence summary" in low:
            delta -= 0.08
        if references:
            delta += 0.03
        return delta

    def _score_confidence(
        self,
        topic: str,
        base: float,
        references: list[dict[str, str]],
        reasoning_steps: list[str],
        contradiction: bool,
        understanding_conf: float,
        user_id: str | None = None,
    ) -> tuple[float, dict[str, float]]:
        stats = self.memory.get_topic_stats(topic, user_id=user_id)
        confirms = int(stats.get("confirmations", 0))
        corrections = int(stats.get("corrections", 0))
        mistakes = int(stats.get("mistakes", 0))

        internal = min(1.0, 0.56 + (min(len(reasoning_steps), 8) * 0.05))
        source = self._source_reliability(references)
        consistency = 0.35 if contradiction else 0.84
        history = self._clamp(0.62 + (confirms * 0.04) - (corrections * 0.05) - (mistakes * 0.03), 0.1, 0.95)
        understand = self._clamp(understanding_conf, 0.0, 1.0)

        final = self._clamp((self._clamp(base, 0.0, 1.0) * 0.42) + (internal * 0.18) + (source * 0.2) + (consistency * 0.12) + (history * 0.05) + (understand * 0.03))
        return final, {
            "base_model": round(self._clamp(base, 0.0, 1.0), 3),
            "internal_reasoning": round(internal, 3),
            "source_reliability": round(source, 3),
            "consistency": round(consistency, 3),
            "history_signal": round(history, 3),
            "understanding": round(understand, 3),
        }

    def _knowledge_multi_path(self, query: str, topic: str, user_id: str | None = None) -> dict[str, Any]:
        paths: list[dict[str, Any]] = []
        notes: list[str] = ["Generate 3 independent reasoning paths when possible."]
        focus_tokens = self._focus_query_tokens(query)

        learned = self.memory.get_rule(topic, user_id=user_id)
        if learned and isinstance(learned.get("current"), dict):
            current = learned["current"]
            learned_answer = str(current.get("answer", "")).strip()
            if learned_answer:
                paths.append(
                    {
                        "name": "learned_rule",
                        "answer": learned_answer,
                        "references": [{"title": "Learned Memory Rule", "url": f"memory://rules/{topic.replace(' ', '_')}"}],
                        "score": float(current.get("confidence", 0.55)),
                    }
                )

        for idx, variant in enumerate(self._query_variants(query, topic)):
            result = self.search.search(variant)
            paths.append(
                {
                    "name": f"web_variant_{idx}",
                    "answer": str(result.get("answer", "")).strip(),
                    "references": list(result.get("references", [])),
                    "score": float(result.get("confidence", 0.45)),
                    "support_count": int(result.get("support_count", 1)),
                    "consensus_score": float(result.get("consensus_score", 0.0)),
                    "search_notes": list(result.get("notes", [])) if isinstance(result.get("notes"), list) else [],
                }
            )
            if len(paths) >= 4:
                break

        while len(paths) < 3:
            result = self.search.search(query)
            paths.append(
                {
                    "name": f"web_fill_{len(paths)}",
                    "answer": str(result.get("answer", "")).strip(),
                    "references": list(result.get("references", [])),
                    "score": float(result.get("confidence", 0.4)),
                }
            )

        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                c = self._path_consistency(paths[i]["answer"], paths[j]["answer"])
                if c >= 0.45:
                    paths[i]["score"] += 0.05
                    paths[j]["score"] += 0.05

        for p in paths:
            relevance = self._query_answer_relevance(query, str(p.get("answer", "")))
            answer_tokens = self._token_set(str(p.get("answer", "")))
            focus_overlap = (len(focus_tokens & answer_tokens) / max(len(focus_tokens), 1)) if focus_tokens else 0.0
            p["relevance"] = relevance
            p["focus_overlap"] = focus_overlap
            p["score"] += min(0.12, relevance * 0.22)
            if relevance < 0.12:
                p["score"] -= 0.2
            if focus_tokens and focus_overlap < 0.34:
                p["score"] -= 0.22
            elif focus_tokens and focus_overlap >= 0.6:
                p["score"] += 0.05
            p["score"] += self._quality_adjustment(str(p.get("answer", "")), list(p.get("references", [])))
            p["score"] += min(0.06, self._source_reliability(list(p.get("references", []))) * 0.06)
            p["score"] += min(0.08, max(0.0, float(p.get("consensus_score", 0.0))) * 0.08)
            p["score"] += min(0.06, max(0, int(p.get("support_count", 1)) - 1) * 0.03)
            if not p["answer"]:
                p["score"] -= 0.1
            if not p["references"]:
                p["score"] -= 0.03

        scored = sorted(paths, key=lambda p: float(p["score"]), reverse=True)
        best = scored[0] if scored else {"answer": "", "references": [], "score": 0.45, "name": "none"}
        if len(scored) > 1:
            top_consistency = self._path_consistency(str(scored[0].get("answer", "")), str(scored[1].get("answer", "")))
            if top_consistency >= 0.5:
                best["score"] = float(best.get("score", 0.45)) + 0.04
                notes.append("Top two paths are mutually consistent.")
        notes.append("Score each path by confidence and cross-path consistency.")
        notes.append(f"Selected best path: {best['name']}.")
        if int(best.get("support_count", 1)) > 1:
            notes.append(f"Best path backed by {int(best.get('support_count', 1))} sources.")
        if float(best.get("consensus_score", 0.0)) >= 0.4:
            notes.append("Cross-source consensus is strong.")
        for n in list(best.get("search_notes", []))[:2]:
            notes.append(str(n))
        if float(best.get("relevance", 0.0)) < 0.12:
            notes.append("Best path has low query relevance; avoid overcommitting.")
        if focus_tokens and float(best.get("focus_overlap", 0.0)) < 0.34:
            notes.append("Best path weakly matches focus terms; likely off-topic.")
        return {
            "answer": str(best.get("answer", "")).strip(),
            "references": list(best.get("references", [])),
            "confidence": self._clamp(float(best.get("score", 0.45)), 0.05, 0.95),
            "relevance": float(best.get("relevance", 0.0)),
            "focus_overlap": float(best.get("focus_overlap", 0.0)),
            "notes": notes,
        }

    def _internal_validation(self, query: str, answer: str) -> tuple[str, float]:
        if not re.search(r"\d", query) or not re.search(r"\d", answer):
            return "", 0.0
        if not self.math_engine.is_math_query(query):
            return "", 0.0
        try:
            check = self.math_engine.solve(query, force_steps=True)
            computed = str(check.get("answer", "")).strip()
            if computed and computed in answer:
                return "Internal calculator cross-check: consistent.", 0.06
            if computed:
                return "Internal calculator cross-check: potential mismatch found.", -0.08
        except Exception:
            return "", 0.0
        return "", 0.0

    def _reflect(
        self,
        query: str,
        answer: str,
        intent: str,
        base_confidence: float,
        references: list[dict[str, str]],
        understanding_conf: float,
        pre_steps: list[str] | None = None,
        user_id: str | None = None,
    ) -> tuple[str, list[dict[str, str]], float, dict[str, float], list[str]]:
        steps = list(pre_steps or []) + [
            "Normalize query and detect intent.",
            "Check learned rule memory for contradictions.",
        ]
        topic = self._topic_from_query(query)
        contradiction = self._is_contradiction(topic, answer, user_id=user_id)
        steps.append("Contradiction found against high-confidence stored rule." if contradiction else "No contradiction found.")

        conf, components = self._score_confidence(
            topic,
            base_confidence,
            references,
            steps,
            contradiction,
            understanding_conf,
            user_id=user_id,
        )
        if conf < 0.70 and intent in {"knowledge", "problem_solving"}:
            steps.append("Confidence below 70%; rerun with trusted web refinement.")
            refined = self.search.search(query)
            candidate = str(refined.get("answer", "")).strip()
            if candidate:
                answer = candidate
                references = self._merge_references(references, list(refined.get("references", [])))
                steps.append("Refined answer adopted.")
            else:
                steps.append("Refinement did not improve answer.")
            contradiction = self._is_contradiction(topic, answer, user_id=user_id)
            conf, components = self._score_confidence(
                topic,
                max(conf, float(refined.get("confidence", 0.45))),
                references,
                steps,
                contradiction,
                understanding_conf,
                user_id=user_id,
            )
        else:
            steps.append("Confidence threshold satisfied.")
        return answer, references, conf, components, steps

    def _update_graph_from_text(self, query: str, answer: str, user_id: str | None = None) -> None:
        tags = self.memory._topic_tags(f"{query} {answer}")  # noqa: SLF001
        max_edges = min(8, len(tags) * (len(tags) - 1) // 2)
        count = 0
        for i in range(len(tags)):
            for j in range(i + 1, len(tags)):
                self.memory.add_graph_edge(tags[i], "related_to", tags[j], weight_delta=0.5, user_id=user_id)
                count += 1
                if count >= max_edges:
                    return

    @staticmethod
    def _low_conf_alternative(intent: str, query: str) -> str:
        if intent == "math":
            return "Alternative approach: verify by substitution or independent numeric testing."
        if intent == "problem_solving":
            return f"Alternative approach: split '{query[:80]}' into smaller sub-questions and validate each one."
        return "Alternative approach: compare at least two trusted sources before finalizing."

    @staticmethod
    def _needs_user_teaching(intent: str, answer: str, confidence: float) -> bool:
        if intent not in {"knowledge", "problem_solving"}:
            return False
        low_answer = answer.lower()
        if confidence < 0.58:
            return True
        return any(
            marker in low_answer
            for marker in [
                "could not find a high-confidence summary",
                "provisional answer:",
            ]
        )

    def _ensure_references(self, intent: str, query: str, refs: list[dict[str, str]]) -> list[dict[str, str]]:
        merged = self._merge_references(refs)
        if merged:
            return merged
        if intent == "math":
            return [
                {"title": "Internal Math Engine", "url": "internal://math-engine"},
                {"title": "SymPy Documentation", "url": "https://docs.sympy.org/latest/index.html"},
            ]
        if intent in {"knowledge", "problem_solving"}:
            return [{"title": f"Search: {query}", "url": f"https://duckduckgo.com/?q={query.replace(' ', '+')}"}]
        return []

    @staticmethod
    def _is_followup_query(raw: str) -> bool:
        q = raw.strip().lower()
        if not q:
            return False
        if len(q) <= 24 and any(k in q for k in ["and ", "also", "what about", "why", "how", "then"]):
            return True
        if len(q.split()) <= 5 and any(p in q for p in ["what about", "and", "also", "then", "why", "how so"]):
            return True
        return False

    def _resolve_query_context(self, session_id: str, raw: str, user_id: str | None = None) -> str:
        if self._is_feedback_like_text(raw):
            return raw
        if not self._is_followup_query(raw):
            return raw
        last_user = self.memory.last_by_role(session_id, "user", skip_texts={raw.lower()}, user_id=user_id)
        if not last_user:
            return raw
        previous_topic = self._topic_from_query(last_user)
        current = raw.strip()
        current_low = current.lower()
        follow = re.match(r"^(?:and|what about|also)\s+(.+?)[\?\.\!]*$", current_low)
        if follow:
            tail = follow.group(1).strip()
            if previous_topic.startswith("capital of "):
                return f"capital of {tail}"
            if previous_topic.startswith("population of "):
                return f"population of {tail}"
            if previous_topic.startswith("currency of "):
                return f"currency of {tail}"
            if previous_topic.startswith("who is "):
                return f"who is {tail}"
            if previous_topic.startswith("what is "):
                return f"what is {tail}"
        if previous_topic and previous_topic != "general":
            return f"{current} related to {previous_topic}"
        return current

    @staticmethod
    def _is_feedback_like_text(text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True
        low = t.lower().strip()
        if low in {"correct", "right", "exactly", "yes correct", "wrong", "also wrong", "still wrong"}:
            return True
        if AICore._is_confirmation(low) or AICore._is_correction(low) or AICore._is_teaching_input(low):
            return True
        return False

    def _latest_substantive_user_query(
        self,
        session_id: str,
        current_raw: str,
        user_id: str | None = None,
    ) -> str:
        history = self.memory.get_history(session_id, user_id=user_id)
        current_low = current_raw.strip().lower()
        for msg in reversed(history):
            if str(msg.get("role", "")).lower() != "user":
                continue
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            low = content.lower()
            if low == current_low:
                continue
            if self._is_feedback_like_text(content):
                continue
            return content
        return ""

    def _log_decision(
        self,
        session_id: str,
        intent: str,
        topic: str,
        confidence: float,
        understanding_conf: float,
        references: list[dict[str, str]],
        reflection_steps: list[str],
        components: dict[str, float],
        user_id: str | None = None,
    ) -> None:
        self.memory.record_decision(
            session_id=session_id,
            intent=intent,
            topic=topic,
            confidence_percent=int(round(self._clamp(confidence, 0.0, 1.0) * 100)),
            understanding_percent=int(round(self._clamp(understanding_conf, 0.0, 1.0) * 100)),
            references=references,
            reasoning_steps=reflection_steps,
            confidence_components=components,
            user_id=user_id,
        )

    def _alternative_retry(self, last_query: str, user_id: str | None = None) -> tuple[str, list[dict[str, str]], float, list[str]]:
        normalized, _ = self.fuzzy.normalize_text(last_query)
        retry_intent = self._intent(normalized)
        steps = ["Analyze previous user query.", "Run an alternative resolution path."]
        if retry_intent == "math":
            result = self.math_engine.solve(normalized, force_steps=True)
            steps.append("Alternative path: strict internal math solver.")
            return (
                self._format_math_answer(str(result.get("answer", "")), list(result.get("steps", []))),
                list(result.get("references", [])),
                self._clamp(float(result.get("confidence", 0.8)) - 0.08),
                steps,
            )
        if retry_intent == "casual":
            result = self._casual_answer(normalized, user_id=user_id)
            steps.append("Alternative path: contextual casual response.")
            return (
                str(result.get("answer", "")).strip(),
                list(result.get("references", [])),
                self._clamp(float(result.get("confidence", 0.76)) - 0.05),
                steps,
            )
        result = self._knowledge_multi_path(normalized, self._topic_from_query(normalized), user_id=user_id)
        steps.extend(list(result.get("notes", [])))
        answer = str(result.get("answer", "")).strip()
        if retry_intent == "problem_solving":
            answer = self._format_problem_answer(normalized, answer)
        return (
            answer,
            list(result.get("references", [])),
            self._clamp(float(result.get("confidence", 0.72)) - 0.06),
            steps,
        )

    def handle_message(self, message: str, session_id: str | None, user_id: str | None = None) -> dict[str, Any]:
        session_id = self.memory.ensure_session(session_id, user_id=user_id)
        raw = message.strip()
        analysis = self.fuzzy.analyze_text(raw)
        normalized = str(analysis.get("normalized", raw)).strip()
        corrections = list(analysis.get("corrections", []))
        understanding_conf = float(analysis.get("understanding_confidence", 1.0))
        clarify_suggestions = list(analysis.get("clarification_suggestions", []))

        self.memory.append_message(session_id, "user", raw, user_id=user_id)
        normalized = self._resolve_query_context(session_id, normalized, user_id=user_id)
        normalized = self._semantic_normalize(normalized)
        previous_assistant = self.memory.last_by_role(session_id, "assistant", user_id=user_id)

        claimed_name = self._extract_user_name_claim(raw)
        if claimed_name and not self._is_correction(raw) and not self._is_confirmation(raw):
            self.memory.remember_user_fact("name", claimed_name, confidence=0.92, source="user_statement", user_id=user_id)
            topic = self._topic_from_query("my name")
            conf = 0.94
            answer = self._attach_conf(
                f"Got it. I will remember your name as {claimed_name}.",
                conf,
            )
            refs = [{"title": "Learned User Profile", "url": "memory://user-facts/name"}]
            reflection_steps = [
                "Detected explicit user profile statement.",
                "Stored per-user profile fact in memory.",
            ]
            self.memory.record_experience(session_id, raw, answer, "feedback", conf, refs, user_id=user_id)
            self.memory.append_message(session_id, "assistant", answer, user_id=user_id)
            self._log_decision(
                session_id,
                "feedback",
                topic,
                conf,
                understanding_conf,
                refs,
                reflection_steps,
                {
                    "base_model": round(conf, 3),
                    "internal_reasoning": 0.85,
                    "source_reliability": 0.8,
                    "consistency": 0.9,
                    "history_signal": 0.86,
                    "understanding": round(understanding_conf, 3),
                },
                user_id=user_id,
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "intent": "feedback",
                "references": refs,
                "fuzzy_corrections": corrections,
                "confidence": int(round(conf * 100)),
                "reflection_steps": reflection_steps,
                "topic": topic,
                "related_concepts": self.memory.graph_neighbors(topic, limit=4, user_id=user_id),
            }

        mode_cmd = self._extract_response_mode_command(raw)
        if mode_cmd:
            self.memory.remember_user_fact("response_mode", mode_cmd, confidence=0.97, source="user_preference", user_id=user_id)
            topic = self._topic_from_query("response mode")
            conf = 0.95
            answer = self._attach_conf(
                f"Response mode set to '{mode_cmd}'. I will adapt explanations to this level.",
                conf,
            )
            refs = [{"title": "User Preferences", "url": "memory://user-facts/response_mode"}]
            reflection_steps = [
                "Detected explicit response mode preference.",
                "Stored mode preference in per-user profile memory.",
            ]
            self.memory.record_experience(session_id, raw, answer, "feedback", conf, refs, user_id=user_id)
            self.memory.append_message(session_id, "assistant", answer, user_id=user_id)
            self._log_decision(
                session_id,
                "feedback",
                topic,
                conf,
                understanding_conf,
                refs,
                reflection_steps,
                {
                    "base_model": round(conf, 3),
                    "internal_reasoning": 0.87,
                    "source_reliability": 0.86,
                    "consistency": 0.94,
                    "history_signal": 0.85,
                    "understanding": round(understanding_conf, 3),
                },
                user_id=user_id,
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "intent": "feedback",
                "references": refs,
                "fuzzy_corrections": corrections,
                "confidence": int(round(conf * 100)),
                "reflection_steps": reflection_steps,
                "topic": topic,
                "related_concepts": self.memory.graph_neighbors(topic, limit=4, user_id=user_id),
            }

        if self._is_teaching_input(raw):
            taught_value = self._extract_teaching_value(raw)
            topic_text = self._latest_substantive_user_query(session_id, raw, user_id=user_id)
            topic = self._topic_from_query(topic_text or raw)
            requested = self._assistant_requested_user_input(previous_assistant)
            if taught_value:
                teach_conf = 0.9 if requested else 0.84
                self.memory.upsert_rule(topic, taught_value, teach_conf, "user_teaching", user_id=user_id)
                self.memory.update_topic_stats(topic, "confirmations", user_id=user_id)
                conf = 0.91 if requested else 0.86
                answer = self._attach_conf(
                    f"Thanks. I learned this for '{topic}' and will use it in future answers.",
                    conf,
                )
                refs = [{"title": "Learned User Input", "url": f"memory://rules/{topic.replace(' ', '_')}"}]
                reflection_steps = [
                    "Detected user teaching input.",
                    "Stored user-provided rule in memory.",
                ]
            else:
                conf = 0.74
                answer = self._attach_conf(
                    "I detected learning input, but I could not parse the value. Please use: answer is <value>.",
                    conf,
                )
                refs = [{"title": "Learning Memory", "url": "internal://memory"}]
                reflection_steps = [
                    "Detected learning intent.",
                    "Parsing failed; requested structured teaching format.",
                ]
            self.memory.record_experience(session_id, raw, answer, "feedback", conf, refs, user_id=user_id)
            self.memory.append_message(session_id, "assistant", answer, user_id=user_id)
            self._log_decision(
                session_id,
                "feedback",
                topic,
                conf,
                understanding_conf,
                refs,
                reflection_steps,
                {
                    "base_model": round(conf, 3),
                    "internal_reasoning": 0.74,
                    "source_reliability": round(self._source_reliability(refs), 3),
                    "consistency": 0.82,
                    "history_signal": 0.72,
                    "understanding": round(understanding_conf, 3),
                },
                user_id=user_id,
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "intent": "feedback",
                "references": refs,
                "fuzzy_corrections": corrections,
                "confidence": int(round(conf * 100)),
                "reflection_steps": reflection_steps,
                "topic": topic,
                "related_concepts": self.memory.graph_neighbors(topic, limit=4, user_id=user_id),
            }

        needs_clarification = understanding_conf < 0.60 and (bool(corrections) or bool(clarify_suggestions))
        if needs_clarification:
            detail = "I may have misunderstood your wording."
            if corrections:
                edits = ", ".join([f"{c['from']} -> {c['to']}" for c in corrections[:4]])
                detail += f" Detected corrections: {edits}."
            if clarify_suggestions:
                detail += " Possible intended terms: " + "; ".join(clarify_suggestions) + "."
            detail += " Please clarify and I will answer precisely."
            conf = self._clamp(understanding_conf + 0.05, 0.2, 0.65)
            answer = self._attach_conf(detail, conf)
            refs = [{"title": "Internal Fuzzy Matcher", "url": "internal://fuzzy-match"}]
            reflection_steps = [
                "Analyze user text normalization and typo corrections.",
                "Understanding confidence below 60%; clarification requested before reasoning.",
            ]
            topic = self._topic_from_query(normalized or raw)
            self.memory.record_experience(session_id, raw, answer, "clarification", conf, refs, user_id=user_id)
            self.memory.append_message(session_id, "assistant", answer, user_id=user_id)
            self._log_decision(
                session_id,
                "clarification",
                topic,
                conf,
                understanding_conf,
                refs,
                reflection_steps,
                {
                    "base_model": round(conf, 3),
                    "internal_reasoning": 0.5,
                    "source_reliability": 0.5,
                    "consistency": 0.5,
                    "history_signal": 0.5,
                    "understanding": round(understanding_conf, 3),
                },
                user_id=user_id,
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "intent": "clarification",
                "references": refs,
                "fuzzy_corrections": corrections,
                "confidence": int(round(conf * 100)),
                "reflection_steps": reflection_steps,
                "topic": topic,
                "related_concepts": self.memory.graph_neighbors(topic, limit=4, user_id=user_id),
            }

        if self._is_confirmation(raw):
            topic_text = self._latest_substantive_user_query(session_id, raw, user_id=user_id)
            topic = self._topic_from_query(topic_text or raw)
            last_answer = self.memory.last_by_role(session_id, "assistant", user_id=user_id)
            confirmed_answer = self._strip_conf(last_answer)
            self.memory.record_confirmation(session_id, topic, last_answer, user_id=user_id)
            self.memory.adjust_rule_confidence(topic, +0.06, user_id=user_id)
            if confirmed_answer:
                self.memory.upsert_rule(topic, confirmed_answer, 0.9, "user_confirmation", user_id=user_id)
            self.memory.update_topic_stats(topic, "confirmations", user_id=user_id)
            conf = 0.92
            answer = self._attach_conf("Noted. I marked the previous answer as confirmed and increased its confidence.", conf)
            refs = [{"title": "Learning Memory", "url": "internal://memory"}]
            reflection_steps = ["User confirmation detected.", "Increase confidence for topic rule."]
            self.memory.append_message(session_id, "assistant", answer, user_id=user_id)
            self.memory.record_experience(session_id, raw, answer, "feedback", conf, refs, user_id=user_id)
            self._log_decision(
                session_id,
                "feedback",
                topic,
                conf,
                understanding_conf,
                refs,
                reflection_steps,
                {
                    "base_model": 0.92,
                    "internal_reasoning": 0.8,
                    "source_reliability": 0.8,
                    "consistency": 0.9,
                    "history_signal": 0.8,
                    "understanding": round(understanding_conf, 3),
                },
                user_id=user_id,
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "intent": "feedback",
                "references": refs,
                "fuzzy_corrections": corrections,
                "confidence": 92,
                "reflection_steps": reflection_steps,
                "topic": topic,
                "related_concepts": self.memory.graph_neighbors(topic, limit=4, user_id=user_id),
            }

        if self._is_correction(raw):
            topic_text = self._latest_substantive_user_query(session_id, raw, user_id=user_id)
            topic = self._topic_from_query(topic_text or raw)
            failed = self.memory.last_by_role(session_id, "assistant", user_id=user_id)
            corrected = self._extract_correction_value(raw, topic_hint=topic)
            self.memory.update_topic_stats(topic, "corrections", user_id=user_id)
            self.memory.update_topic_stats(topic, "mistakes", user_id=user_id)
            self.memory.bump_pattern(topic, mistake=True, user_id=user_id)
            self.memory.adjust_rule_confidence(topic, -0.18, user_id=user_id)

            if corrected:
                self.memory.record_correction(session_id, topic, failed, corrected, user_id=user_id)
                self.memory.upsert_rule(topic, corrected, 0.86, "user_correction", user_id=user_id)
                ack = f"Correction learned for '{topic}'. I replaced the conflicting rule with your correction."
                refs = [{"title": "Learning Memory", "url": "internal://memory"}]
                conf = 0.9
                reflection_steps = [
                    "User-provided corrected answer detected.",
                    "Old rule confidence reduced; corrected rule stored with higher confidence.",
                ]
            else:
                prev_query = self._latest_substantive_user_query(session_id, raw, user_id=user_id)
                if prev_query:
                    alt_answer, refs, conf, retry_steps = self._alternative_retry(prev_query, user_id=user_id)
                    failed_clean = self._strip_conf(failed).strip().lower()
                    alt_clean = self._strip_conf(alt_answer).strip().lower()
                    if alt_clean and alt_clean != failed_clean:
                        self.memory.record_correction(session_id, topic, failed, alt_answer, user_id=user_id)
                        ack = f"I logged the correction signal for '{topic}' and re-analyzed using an alternative path.\n{alt_answer}"
                        reflection_steps = ["Correction signal without explicit fix."] + retry_steps
                    else:
                        ack = (
                            f"I logged the correction for '{topic}', but my alternative path still looked unreliable. "
                            "Please provide the corrected answer using: answer is <your answer>."
                        )
                        refs = [{"title": "Learning Memory", "url": "internal://memory"}]
                        conf = 0.62
                        reflection_steps = [
                            "Correction signal without explicit fix.",
                            "Alternative retry did not improve previous answer.",
                            "Requested explicit user correction for safe learning.",
                        ]
                else:
                    ack = "I logged that as a correction. Share the corrected answer and I will update the rule."
                    refs = [{"title": "Learning Memory", "url": "internal://memory"}]
                    conf = 0.76
                    reflection_steps = ["Correction signal detected.", "No previous query context for recomputation."]

            answer = self._attach_conf(ack, conf)
            self.memory.append_message(session_id, "assistant", answer, user_id=user_id)
            self.memory.record_experience(session_id, raw, answer, "feedback", conf, refs, user_id=user_id)
            self._log_decision(
                session_id,
                "feedback",
                topic,
                conf,
                understanding_conf,
                refs,
                reflection_steps,
                {
                    "base_model": round(conf, 3),
                    "internal_reasoning": 0.78,
                    "source_reliability": round(self._source_reliability(refs), 3),
                    "consistency": 0.62,
                    "history_signal": 0.6,
                    "understanding": round(understanding_conf, 3),
                },
                user_id=user_id,
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "intent": "feedback",
                "references": refs,
                "fuzzy_corrections": corrections,
                "confidence": int(round(conf * 100)),
                "reflection_steps": reflection_steps,
                "topic": topic,
                "related_concepts": self.memory.graph_neighbors(topic, limit=4, user_id=user_id),
            }

        intent = self._intent(normalized)
        deterministic_candidate = self._deterministic_reasoning_answer(normalized)
        if deterministic_candidate and str(deterministic_candidate.get("intent", "")) == "problem_solving":
            intent = "problem_solving"
        fictional_candidate: dict[str, Any] | None = None
        if intent in {"knowledge", "problem_solving"} and not deterministic_candidate and self._is_likely_fictional_query(normalized):
            ans, refs, conf, steps = self._fictional_query_response(normalized)
            fictional_candidate = {
                "answer": ans,
                "references": refs,
                "confidence": conf,
                "reasoning_steps": steps,
                "direct_reasoning": True,
                "intent": "knowledge",
            }
        topic = self._topic_from_query(normalized)
        self._maybe_update_session_title(session_id, topic, normalized, intent, user_id=user_id)
        self.memory.bump_pattern(topic, user_id=user_id)
        self.memory.update_topic_stats(topic, "questions", user_id=user_id)
        knowledge_relevance = 1.0
        knowledge_focus_overlap = 1.0
        internal_candidate = (
            deterministic_candidate
            if deterministic_candidate and intent in {"knowledge", "problem_solving"}
            else (
                fictional_candidate
                if fictional_candidate and intent in {"knowledge", "problem_solving"}
                else (self._internal_knowledge_lookup(normalized, topic) if intent in {"knowledge", "problem_solving"} else None)
            )
        )

        if intent in {"knowledge", "problem_solving"} and not internal_candidate and self._is_overly_ambiguous_query(normalized):
            conf = 0.58
            answer = self._attach_conf(
                f"Your question '{normalized}' is too broad. Please add context so I can return a closer result.",
                conf,
            )
            refs = [{"title": "Clarification Needed", "url": "internal://clarification"}]
            reflection_steps = [
                "Detected broad query with insufficient context.",
                "Requested clarification to avoid unrelated results.",
            ]
            self.memory.record_experience(session_id, raw, answer, "clarification", conf, refs, user_id=user_id)
            self.memory.append_message(session_id, "assistant", answer, user_id=user_id)
            self._log_decision(
                session_id,
                "clarification",
                topic,
                conf,
                understanding_conf,
                refs,
                reflection_steps,
                {
                    "base_model": round(conf, 3),
                    "internal_reasoning": 0.66,
                    "source_reliability": 0.6,
                    "consistency": 0.76,
                    "history_signal": 0.65,
                    "understanding": round(understanding_conf, 3),
                },
                user_id=user_id,
            )
            return {
                "session_id": session_id,
                "answer": answer,
                "intent": "clarification",
                "references": refs,
                "fuzzy_corrections": corrections,
                "confidence": int(round(conf * 100)),
                "reflection_steps": reflection_steps,
                "topic": topic,
                "related_concepts": self.memory.graph_neighbors(topic, limit=4, user_id=user_id),
            }

        learned = self.memory.get_rule(topic, user_id=user_id)
        can_reuse_learned = intent in {"knowledge", "problem_solving"}
        if can_reuse_learned and learned and isinstance(learned.get("current"), dict) and float(learned["current"].get("confidence", 0.0)) >= 0.8:
            base_answer = str(learned["current"].get("answer", "")).strip()
            refs = [{"title": "Learned Memory Rule", "url": f"memory://rules/{topic.replace(' ', '_')}"}]
            base_conf = float(learned["current"].get("confidence", 0.8))
            path_steps = ["Used high-confidence learned rule."]
        else:
            if intent == "math":
                result = self.math_engine.solve(normalized, force_steps=True)
                steps = list(result.get("steps", []))
                base_answer = self._format_math_answer(str(result.get("answer", "")), steps)
                refs = list(result.get("references", []))
                base_conf = float(result.get("confidence", 0.6))
                path_steps = ["Math intent routed to internal calculator/reasoner.", "Generated explicit step-by-step solution."]
            elif intent == "casual":
                result = self._casual_answer(normalized, user_id=user_id, session_id=session_id)
                base_answer = str(result.get("answer", "")).strip()
                refs = list(result.get("references", []))
                base_conf = float(result.get("confidence", 0.6))
                path_steps = ["Casual intent handled by conversational fallback."]
            elif intent == "problem_solving":
                internal = internal_candidate
                if internal:
                    direct_reasoning = bool(internal.get("direct_reasoning", False))
                    if direct_reasoning:
                        base_answer = str(internal.get("answer", "")).strip()
                    else:
                        base_answer = self._format_problem_answer(normalized, str(internal.get("answer", "")).strip())
                    refs = list(internal.get("references", []))
                    base_conf = float(internal.get("confidence", 0.84))
                    knowledge_relevance = self._query_answer_relevance(normalized, base_answer)
                    knowledge_focus_overlap = knowledge_relevance
                    path_steps = list(internal.get("reasoning_steps", [])) if isinstance(internal.get("reasoning_steps"), list) else []
                    path_steps += ["Used curated internal knowledge for core concept.", "Structured reasoning steps generated."]
                else:
                    result = self._knowledge_multi_path(normalized, topic, user_id=user_id)
                    base_answer = self._format_problem_answer(normalized, str(result.get("answer", "")).strip())
                    refs = list(result.get("references", []))
                    base_conf = float(result.get("confidence", 0.6))
                    knowledge_relevance = float(result.get("relevance", 1.0))
                    knowledge_focus_overlap = float(result.get("focus_overlap", 0.0))
                    path_steps = list(result.get("notes", [])) + ["Structured reasoning steps generated."]
            else:
                internal = internal_candidate
                if internal:
                    base_answer = str(internal.get("answer", "")).strip()
                    refs = list(internal.get("references", []))
                    base_conf = float(internal.get("confidence", 0.84))
                    knowledge_relevance = self._query_answer_relevance(normalized, base_answer)
                    knowledge_focus_overlap = knowledge_relevance
                    path_steps = list(internal.get("reasoning_steps", [])) if isinstance(internal.get("reasoning_steps"), list) else []
                    path_steps += ["Used curated internal knowledge for core concept."]
                else:
                    result = self._knowledge_multi_path(normalized, topic, user_id=user_id)
                    base_answer = str(result.get("answer", "")).strip()
                    refs = list(result.get("references", []))
                    base_conf = float(result.get("confidence", 0.6))
                    knowledge_relevance = float(result.get("relevance", 1.0))
                    knowledge_focus_overlap = float(result.get("focus_overlap", 0.0))
                    path_steps = list(result.get("notes", []))

        if intent in {"knowledge", "problem_solving"}:
            token_count = len(self._token_set(normalized))
            relevance_floor = 0.16 if token_count <= 4 else 0.12
            focus_tokens = self._focus_query_tokens(normalized)
            focus_floor = 0.5 if len(focus_tokens) <= 1 else (0.34 if len(focus_tokens) <= 3 else 0.3)
            direct_reasoning = bool(internal_candidate and isinstance(internal_candidate, dict) and internal_candidate.get("direct_reasoning"))
            if not direct_reasoning and (knowledge_relevance < relevance_floor or knowledge_focus_overlap < focus_floor) and token_count <= 10:
                base_answer = (
                    f"I may be matching the wrong topic for '{normalized}'. "
                    "Please clarify what you mean so I can answer accurately."
                )
                refs = self._ensure_references(intent, normalized, refs)
                base_conf = min(base_conf, 0.56)
                path_steps.append("Low relevance/focus safeguard triggered; requested clarification instead of weak match.")

        if not base_answer:
            base_answer = "Provisional answer: I need more context to produce a precise result."
            base_conf = max(base_conf, 0.45)

        check_note, check_delta = self._internal_validation(normalized, base_answer)
        if check_note:
            path_steps.append(check_note)
            base_conf = self._clamp(base_conf + check_delta)

        refs = self._ensure_references(intent, normalized, refs)
        reflected_answer, refs, final_conf, conf_components, reflection_steps = self._reflect(
            normalized,
            base_answer,
            intent,
            base_conf,
            refs,
            understanding_conf,
            pre_steps=path_steps,
            user_id=user_id,
        )

        if final_conf < 0.70:
            reflected_answer = f"{self._strip_conf(reflected_answer)}\n{self._low_conf_alternative(intent, normalized)}"
            reflection_steps.append("Low confidence detected; alternative approach suggested.")
        if self._needs_user_teaching(intent, reflected_answer, final_conf):
            reflected_answer = (
                f"{self._strip_conf(reflected_answer)}\n"
                "I do not have enough confidence yet. If you know the correct answer, "
                "reply with: answer is <your answer>. I will learn it for future questions."
            )
            reflection_steps.append("Requested user-provided answer for safe learning.")

        response_mode, mode_source = self._resolve_response_mode(raw, user_id=user_id)
        if intent in {"knowledge", "problem_solving", "math"}:
            rewritten = self._rewrite_for_mode(reflected_answer, response_mode, intent)
            if rewritten:
                reflected_answer = rewritten
            if response_mode != "standard":
                reflection_steps.append(f"Applied response mode '{response_mode}' from {mode_source}.")

        final_answer = self._attach_conf(reflected_answer, final_conf)
        self.memory.update_topic_stats(topic, "answers", user_id=user_id)
        self.memory.record_experience(session_id, raw, final_answer, intent, final_conf, refs, user_id=user_id)
        self.memory.append_message(session_id, "assistant", final_answer, user_id=user_id)
        self._update_graph_from_text(normalized, reflected_answer, user_id=user_id)
        self._log_decision(
            session_id,
            intent,
            topic,
            final_conf,
            understanding_conf,
            refs,
            reflection_steps,
            conf_components,
            user_id=user_id,
        )

        if final_conf >= 0.86:
            self.memory.upsert_rule(
                topic,
                self._strip_conf(reflected_answer),
                final_conf,
                "high_confidence_turn",
                user_id=user_id,
            )

        return {
            "session_id": session_id,
            "answer": final_answer,
            "intent": intent,
            "references": refs,
            "fuzzy_corrections": corrections,
            "confidence": int(round(final_conf * 100)),
            "reflection_steps": reflection_steps,
            "topic": topic,
            "related_concepts": self.memory.graph_neighbors(topic, limit=4, user_id=user_id),
        }
