from __future__ import annotations

import ast
import operator
import re
from typing import Any
from functools import lru_cache

try:
    import sympy as sp
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    SYMPY_READY = True
    SYMPY_TRANSFORMS = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )
except Exception:
    sp = None
    parse_expr = None
    SYMPY_READY = False
    SYMPY_TRANSFORMS = ()


class MathEngine:
    """Ultra-safe hybrid arithmetic + symbolic math engine (drop-in compatible)."""

    def __init__(self) -> None:
        self.ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
        }

        self.symbols = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.Div: "/",
            ast.Pow: "^",
            ast.Mod: "%",
        }

        if SYMPY_READY:
            self.x, self.y, self.z = sp.symbols("x y z")
            self.local = {
                "x": self.x,
                "y": self.y,
                "z": self.z,
                "pi": sp.pi,
                "e": sp.E,
                "sqrt": sp.sqrt,
                "sin": sp.sin,
                "cos": sp.cos,
                "tan": sp.tan,
                "log": sp.log,
                "ln": sp.log,
                "exp": sp.exp,
            }

    # -------------------------
    # BASIC TEXT PROCESSING
    # -------------------------

    @staticmethod
    def _normalize_words(text: str) -> str:
        out = text.lower()

        replacements = {
            "multiplied by": "*",
            "times": "*",
            "plus": "+",
            "minus": "-",
            "divided by": "/",
            "over": "/",
            "to the power of": "^",
            "raised to": "^",
            "squared": "^2",
            "cubed": "^3",
            "percent": "/100",
        }

        for src, dst in replacements.items():
            out = out.replace(src, dst)

        out = out.replace("×", "*").replace("÷", "/").replace("−", "-")
        out = re.sub(r"\s+", " ", out).strip()
        return out

    @staticmethod
    def wants_steps(text: str) -> bool:
        markers = ["step by step", "show steps", "show work"]
        return any(m in text.lower() for m in markers)

    @staticmethod
    def _strip_step_markers(text: str) -> str:
        return re.sub(
            r"(step by step|show steps|show work)",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

    # -------------------------
    # SAFE ARITHMETIC
    # -------------------------

    def _safe_eval(self, node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return self._safe_eval(node.body)

        if isinstance(node, ast.Constant):
            return float(node.value)

        if isinstance(node, ast.UnaryOp):
            value = self._safe_eval(node.operand)
            return -value if isinstance(node.op, ast.USub) else value

        if isinstance(node, ast.BinOp) and type(node.op) in self.ops:
            left = self._safe_eval(node.left)
            right = self._safe_eval(node.right)
            return self.ops[type(node.op)](left, right)

        raise ValueError("Unsupported arithmetic expression")

    def _arithmetic(self, expr: str) -> str:
        if not re.fullmatch(r"[0-9eE\.\+\-\*\/\%\(\)\s]+", expr):
            raise ValueError("Unsafe arithmetic input")

        tree = ast.parse(expr, mode="eval")
        value = self._safe_eval(tree)
        return str(int(value)) if float(value).is_integer() else str(value)

    # -------------------------
    # SYMPY PARSER (CACHED)
    # -------------------------

    @lru_cache(maxsize=256)
    def _parse_symbolic(self, expr: str):
        return parse_expr(expr, local_dict=self.local, transformations=SYMPY_TRANSFORMS)

    # -------------------------
    # MAIN SOLVER
    # -------------------------

    def solve(self, query: str, force_steps: bool = False) -> dict[str, Any]:
        raw = query.strip()
        show_steps = force_steps or self.wants_steps(raw)
        q = self._strip_step_markers(raw)
        q = self._normalize_words(q)

        references = [
            {"title": "Internal Math Engine", "url": "internal://math-engine"},
            {"title": "SymPy Documentation", "url": "https://docs.sympy.org"},
        ]

        # -------------------------
        # If SymPy Not Available
        # -------------------------

        if not SYMPY_READY:
            try:
                answer = self._arithmetic(q)
                return {
                    "answer": answer,
                    "steps": ["Evaluated using safe arithmetic."] if show_steps else [],
                    "confidence": 0.9,
                    "references": references,
                }
            except Exception:
                return {
                    "answer": "Math engine unavailable.",
                    "steps": [],
                    "confidence": 0.4,
                    "references": references,
                }

        # -------------------------
        # FULL SYMBOLIC POWER
        # -------------------------

        try:
            # Solve equation
            if "=" in q:
                lhs_raw, rhs_raw = q.split("=", 1)
                lhs = self._parse_symbolic(lhs_raw)
                rhs = self._parse_symbolic(rhs_raw)
                eq = sp.Eq(lhs, rhs)

                vars_ = list(eq.free_symbols)
                target = vars_[0] if vars_ else self.x
                solution = sp.solve(eq, target)

                return {
                    "answer": str(solution),
                    "steps": ["Solved symbolic equation."] if show_steps else [],
                    "confidence": 0.97,
                    "references": references,
                }

            expr = self._parse_symbolic(q)

            # Calculus detection
            if isinstance(expr, sp.Derivative):
                result = expr.doit()
                return {
                    "answer": str(result),
                    "steps": ["Computed derivative."] if show_steps else [],
                    "confidence": 0.97,
                    "references": references,
                }

            if isinstance(expr, sp.Integral):
                result = expr.doit()
                return {
                    "answer": str(result),
                    "steps": ["Computed integral."] if show_steps else [],
                    "confidence": 0.97,
                    "references": references,
                }

            if isinstance(expr, sp.Limit):
                result = expr.doit()
                return {
                    "answer": str(result),
                    "steps": ["Computed limit."] if show_steps else [],
                    "confidence": 0.97,
                    "references": references,
                }

            # Matrix
            if isinstance(expr, sp.Matrix):
                return {
                    "answer": str(expr),
                    "steps": ["Matrix evaluated."] if show_steps else [],
                    "confidence": 0.95,
                    "references": references,
                }

            # General evaluation
            simplified = sp.simplify(expr)

            if simplified.free_symbols:
                return {
                    "answer": str(simplified),
                    "steps": ["Simplified symbolic expression."] if show_steps else [],
                    "confidence": 0.95,
                    "references": references,
                }

            numeric = sp.N(simplified)

            return {
                "answer": str(numeric),
                "steps": ["Evaluated numerically."] if show_steps else [],
                "confidence": 0.95,
                "references": references,
            }

        except Exception:
            # Final fallback to arithmetic
            try:
                answer = self._arithmetic(q)
                return {
                    "answer": answer,
                    "steps": ["Fallback arithmetic evaluation."] if show_steps else [],
                    "confidence": 0.85,
                    "references": references,
                }
            except Exception:
                return {
                    "answer": "I could not parse that math expression safely.",
                    "steps": ["Parsing failed safely."],
                    "confidence": 0.5,
                    "references": references,
                }