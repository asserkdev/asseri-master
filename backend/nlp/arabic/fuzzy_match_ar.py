from __future__ import annotations

import re
from collections import OrderedDict
from difflib import get_close_matches

try:
    from rapidfuzz import process

    RAPIDFUZZ_READY = True
except Exception:
    process = None
    RAPIDFUZZ_READY = False

from .normalizer import canonical_arabic_token, contains_arabic, normalize_arabic_text
from .tokenizer import tokenize_arabic

ARABIC_CORRECTION_MEMORY: OrderedDict[str, str] = OrderedDict()
MAX_ARABIC_CORRECTION_MEMORY = 200


class ArabicFuzzyMatcher:
    """Arabic normalization + typo-aware understanding layer."""

    def __init__(self) -> None:
        self.vocabulary = {
            "مرحبا",
            "اهلا",
            "سلام",
            "ما",
            "هو",
            "هي",
            "من",
            "انت",
            "انا",
            "اسمي",
            "اسمك",
            "ذكاء",
            "اصطناعي",
            "الذكاء",
            "الاصطناعي",
            "احسب",
            "حل",
            "معادلة",
            "جذر",
            "تكامل",
            "اشتق",
            "مشتقة",
            "زائد",
            "ناقص",
            "ضرب",
            "قسمة",
            "مقسوم",
            "على",
            "في",
            "صح",
            "صحيح",
            "خطا",
            "غلط",
            "نعم",
            "لا",
            "غير",
            "النبرة",
            "الي",
            "رسمي",
            "ودي",
            "عادي",
            "مباشر",
            "شل",
            "سريع",
            "اشرح",
            "شرح",
            "باختصار",
            "بالتفصيل",
            "ثقة",
            "مصادر",
            "مرجع",
            "مراجع",
            "طائرة",
            "وظيفة",
            "دور",
            "غوغل",
            "جوجل",
            "اليابان",
            "العاصمة",
            "كم",
            "لماذا",
            "كيف",
            "اين",
            "متى",
            "اريد",
            "تعلم",
        }
        self.typo_map = {
            "مرحبه": "مرحبا",
            "اهلن": "اهلا",
            "هاي": "مرحبا",
            "شنو": "ما",
            "ايش": "ما",
            "هاذا": "هذا",
            "هاد": "هذا",
            "ماهو": "ما هو",
            "ماهي": "ما هي",
            "منهو": "من هو",
            "منهي": "من هي",
            "اسمكك": "اسمك",
            "اسميي": "اسمي",
            "ذكاء اصطناعى": "ذكاء اصطناعي",
            "اصطناعى": "اصطناعي",
            "غوغل": "جوجل",
            "جووجل": "جوجل",
            "حيح": "صح",
            "صحح": "صح",
            "خطئ": "خطا",
            "غلط": "غلط",
            "بليز": "من فضلك",
            "عايز": "اريد",
            "عاوز": "اريد",
        }

    @staticmethod
    def _memory_key(text: str) -> str:
        return re.sub(r"\s+", " ", normalize_arabic_text(text).strip().lower())

    @staticmethod
    def _remember_correction(original_text: str, corrected_text: str) -> None:
        key = ArabicFuzzyMatcher._memory_key(original_text)
        val = ArabicFuzzyMatcher._memory_key(corrected_text)
        if not key or not val or key == val:
            return
        if key in ARABIC_CORRECTION_MEMORY:
            del ARABIC_CORRECTION_MEMORY[key]
        ARABIC_CORRECTION_MEMORY[key] = val
        while len(ARABIC_CORRECTION_MEMORY) > MAX_ARABIC_CORRECTION_MEMORY:
            ARABIC_CORRECTION_MEMORY.popitem(last=False)

    def is_arabic_text(self, text: str) -> bool:
        return contains_arabic(text)

    def _candidate_for_token(self, token: str, cutoff: int = 90) -> str:
        token = canonical_arabic_token(token)
        if not token or len(token) <= 2:
            return ""
        if RAPIDFUZZ_READY and process is not None:
            match = process.extractOne(token, list(self.vocabulary), score_cutoff=cutoff)
            if match:
                candidate = canonical_arabic_token(str(match[0]))
                if candidate and candidate[0] == token[0]:
                    return candidate
            return ""
        close = get_close_matches(token, list(self.vocabulary), n=1, cutoff=max(0.0, min(1.0, cutoff / 100.0)))
        if close:
            candidate = canonical_arabic_token(close[0])
            if candidate and candidate[0] == token[0]:
                return candidate
        return ""

    def normalize_math_text(self, text: str) -> str:
        out = normalize_arabic_text(text).lower()
        out = re.sub(r"\b(\u0645\u0627 \u0647\u0648|\u0645\u0627 \u0647\u064a|\u0627\u062d\u0633\u0628|\u0627\u0648\u062c\u062f|\u0627\u064a\u062c\u0627\u062f|\u062d\u0644)\b", " ", out)
        out = re.sub(r"\b(\u0632\u0627\u0626\u062f|\u0632\u0627\u064a\u062f)\b", " + ", out)
        out = re.sub(r"\b\u0646\u0627\u0642\u0635\b", " - ", out)
        out = re.sub(r"\b(\u0636\u0631\u0628|\u00d7|x)\b", " * ", out)
        out = re.sub(r"\b(\u0642\u0633\u0645\u0629|\u0645\u0642\u0633\u0648\u0645 \u0639\u0644\u0649|\u0639\u0644\u0649)\b", " / ", out)
        out = re.sub(r"\b\u0627\u0633\b", " ^ ", out)
        out = re.sub(r"\b\u062c\u0630\u0631\s+(-?\d+(?:\.\d+)?)", r"sqrt(\1)", out)
        out = re.sub(r"\s+", " ", out).strip()
        out = out.replace("+ +", "+").replace("- -", "-")
        return out

    def bridge_to_internal_query(self, text: str) -> str:
        q = normalize_arabic_text(text).lower()

        # Direct command conversions.
        if re.search(r"\b(غير|بدل|غي[ي]?ر)\s+النبره?\s+الي\s+رسمي\b", q):
            return "set tone to formal"
        if re.search(r"\b(غير|بدل|غي[ي]?ر)\s+النبره?\s+الي\s+(ودي|لطيف|ودي جدا)\b", q):
            return "set tone to friendly"
        if re.search(r"\b(غير|بدل|غي[ي]?ر)\s+النبره?\s+الي\s+عادي\b", q):
            return "set tone to casual"
        if re.search(r"\b(غير|بدل|غي[ي]?ر)\s+النبره?\s+الي\s+مباشر\b", q):
            return "set tone to direct"
        if re.search(r"\b(غير|بدل|غي[ي]?ر)\s+النبره?\s+الي\s+شل\b", q):
            return "set tone to chill"

        # Identity and profile.
        if re.search(r"\bما\s+اسمك\b", q) or re.search(r"\bمن\s+انت\b", q):
            return "what is your name"
        if re.search(r"\bمن\s+انا\b", q) or re.search(r"\bما\s+اسمي\b", q):
            return "what is my name"
        if re.search(r"\bكم\s+ثقتك\b", q) or re.search(r"\bما\s+نسبه\s+الثقه\b", q):
            return "how much confidence do you have"
        if re.search(r"\bمن\s+اين\s+تعلمت\b", q) or re.search(r"\bمن\s+اين\s+جبت\b", q):
            return "where did you learn this"
        if re.search(r"\bماذا\s+تستطيع\b", q) or re.search(r"\bماذا\s+يمكنك\s+ان\s+تفعل\b", q):
            return "what can you do"

        # Greetings.
        if q in {"مرحبا", "اهلا", "سلام", "هاي"}:
            return "hi"

        # Core knowledge term bridge.
        q = q.replace("الذكاء الاصطناعي", "artificial intelligence")
        q = q.replace("ذكاء اصطناعي", "artificial intelligence")
        q = q.replace("طائرة", "airplane")
        q = q.replace("وظيفة", "purpose")
        q = q.replace("دور", "purpose")
        q = q.replace("عاصمة", "capital")
        q = q.replace("اليابان", "japan")

        # Question starters.
        q = re.sub(r"\bما\s+هو\b", "what is", q)
        q = re.sub(r"\bما\s+هي\b", "what is", q)
        q = re.sub(r"\bمن\s+هو\b", "who is", q)
        q = re.sub(r"\bمن\s+هي\b", "who is", q)
        q = re.sub(r"\bاشرح\b", "explain", q)
        q = re.sub(r"\bاحسب\b", "calculate", q)
        q = re.sub(r"\bحل\b", "solve", q)

        q = re.sub(r"\s+", " ", q).strip()
        return q

    def extract_tone_command(self, text: str) -> str | None:
        q = normalize_arabic_text(text).lower()
        tone_map = {
            "رسمي": "formal",
            "ودي": "friendly",
            "عادي": "casual",
            "شل": "chill",
            "مباشر": "direct",
        }
        m = re.search(r"\b(?:غير|بدل|اضبط)\s+النبره?\s+الي\s+(\S+)\b", q)
        if m:
            return tone_map.get(m.group(1).strip())
        return None

    def analyze_text(self, text: str) -> dict[str, object]:
        original = str(text or "")
        normalized = normalize_arabic_text(original)

        key = self._memory_key(normalized)
        if key in ARABIC_CORRECTION_MEMORY:
            corrected = ARABIC_CORRECTION_MEMORY[key]
            del ARABIC_CORRECTION_MEMORY[key]
            ARABIC_CORRECTION_MEMORY[key] = corrected
            return {
                "normalized": corrected,
                "corrections": [{"from": normalized, "to": corrected}],
                "understanding_confidence": 0.94,
                "ambiguous_tokens": [],
                "clarification_suggestions": [],
                "suggested_sentence": corrected,
                "needs_confirmation": False,
                "soft_corrections": [],
            }

        tokens = tokenize_arabic(normalized)
        corrections: list[dict[str, str]] = []
        soft_corrections: list[dict[str, str]] = []
        fixed_tokens: list[str] = []
        suggested_tokens: list[str] = []
        ambiguous_tokens: list[str] = []

        for token in tokens:
            canonical = canonical_arabic_token(token)
            if not canonical:
                continue

            if canonical in self.typo_map:
                fixed = canonical_arabic_token(self.typo_map[canonical])
                fixed_tokens.append(fixed)
                suggested_tokens.append(fixed)
                corrections.append({"from": token, "to": fixed})
                continue

            if canonical in self.vocabulary or canonical.isdigit() or re.fullmatch(r"[\+\-\*\/\^=\(\)\.]+", canonical):
                fixed_tokens.append(canonical)
                suggested_tokens.append(canonical)
                continue

            strong = self._candidate_for_token(canonical, cutoff=92)
            if strong:
                fixed_tokens.append(strong)
                suggested_tokens.append(strong)
                corrections.append({"from": token, "to": strong})
                continue

            soft = self._candidate_for_token(canonical, cutoff=86)
            fixed_tokens.append(canonical)
            suggested_tokens.append(soft or canonical)
            ambiguous_tokens.append(canonical)
            if soft:
                soft_corrections.append({"from": token, "to": soft})

        normalized_sentence = " ".join(fixed_tokens).strip() or normalized
        suggested_sentence = " ".join(suggested_tokens).strip() or normalized_sentence

        change_count = len(corrections)
        soft_count = len(soft_corrections)
        amb_count = len(ambiguous_tokens)
        penalty = min(0.68, (change_count * 0.09) + (soft_count * 0.05) + (amb_count * 0.04))
        confidence = max(0.25, 1.0 - penalty)

        needs_confirmation = bool(
            suggested_sentence
            and suggested_sentence != normalized_sentence
            and (soft_count > 0 or change_count >= 2 or confidence < 0.88)
        )

        suggestions = [f"{row['from']} -> {row['to']}" for row in soft_corrections[:4]]

        if normalized_sentence != normalize_arabic_text(original):
            self._remember_correction(original, normalized_sentence)

        return {
            "normalized": normalized_sentence,
            "corrections": corrections,
            "understanding_confidence": round(confidence, 3),
            "ambiguous_tokens": ambiguous_tokens[:5],
            "clarification_suggestions": suggestions,
            "suggested_sentence": suggested_sentence,
            "needs_confirmation": needs_confirmation,
            "soft_corrections": soft_corrections[:8],
        }
