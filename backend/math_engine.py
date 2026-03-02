from __future__ import annotations

import ast
import json
import operator
import re
from functools import lru_cache
from typing import Any

from .compute_engine import ComputeEngine

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


def compute_math_confidence(query: str, result: dict) -> float:
    mode = str(result.get("_solve_mode", "failed")).strip().lower()
    backend = str(result.get("_backend", "")).strip().lower()

    if mode == "symbolic":
        conf = 0.96
    elif mode == "arithmetic":
        conf = 0.90
    elif mode == "matrix_compute":
        conf = 0.94 if backend == "torch_cuda" else 0.91
    elif mode == "fallback_arithmetic":
        conf = 0.85
    else:
        conf = 0.58

    if bool(result.get("_fuzzy_corrected", False)):
        conf -= 0.05

    if bool(result.get("_ambiguous_vars", False)):
        conf -= 0.03

    conf = max(0.30, min(0.99, conf))
    if mode == "failed":
        conf = min(conf, 0.60)

    return round(conf, 3)


class MathEngine:
    """Safe hybrid arithmetic + symbolic math engine."""

    def __init__(self, compute_engine: ComputeEngine | None = None) -> None:
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
                "i": sp.I,
                "sqrt": sp.sqrt,
                "sin": sp.sin,
                "cos": sp.cos,
                "tan": sp.tan,
                "log": sp.log,
                "ln": sp.log,
                "exp": sp.exp,
                "abs": sp.Abs,
            }
        self.compute_engine = compute_engine or ComputeEngine()

    @staticmethod
    def is_math_query(text: str) -> bool:
        q = str(text or "").lower().strip()
        if not q:
            return False
        triggers = [
            "calculate",
            "compute",
            "evaluate",
            "solve",
            "equation",
            "integrate",
            "differentiate",
            "derivative",
            "simplify",
            "expand",
            "factor",
            "limit",
            "sqrt",
            "root",
            "matrix multiply",
            "matmul",
            "matrix product",
        ]
        if any(t in q for t in triggers):
            return True
        if re.search(r"(sum of|difference between|product of|quotient of)\s+-?\d", q):
            return True
        if re.search(r"(increase|decrease)\s+-?\d+(?:\.\d+)?\s+by\s+-?\d+(?:\.\d+)?\s*percent", q):
            return True
        if re.search(r"-?\d+(?:\.\d+)?\s*percent", q):
            return True
        if "\u221a" in q:
            return True
        if re.search(r"[\d\)\(]\s*[\+\-\*\/\^%=]", q):
            return True
        if re.search(r"\b[xyz]\b", q) and "=" in q:
            return True
        return False

    @staticmethod
    def wants_steps(text: str) -> bool:
        markers = ["step by step", "show steps", "show work", "with steps", "explain each step", "explain"]
        t = str(text or "").lower()
        return any(m in t for m in markers)

    @staticmethod
    def _explanation_mode(text: str) -> str:
        t = str(text or "").lower()
        if any(k in t for k in ["brief", "short answer", "quick"]):
            return "brief"
        if any(k in t for k in ["detailed", "explain fully", "show every step"]):
            return "detailed"
        return "normal"

    @staticmethod
    def _strip_step_markers(text: str) -> str:
        t = str(text or "")
        for p in [
            r"\bstep by step\b",
            r"\bshow (?:the )?steps\b",
            r"\bshow (?:your )?work\b",
            r"\bwith steps\b",
            r"\bexplain each step\b",
            r"\band explain each step\b",
            r"\band explain\b",
        ]:
            t = re.sub(p, " ", t, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", t).strip(" ,.!?")

    @staticmethod
    def _strip_mode_markers(text: str) -> str:
        t = str(text or "")
        for p in [
            r"\bbrief\b",
            r"\bshort answer\b",
            r"\bquick\b",
            r"\bdetailed\b",
            r"\bexplain fully\b",
            r"\bshow every step\b",
        ]:
            t = re.sub(p, " ", t, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", t).strip(" ,.!?")

    @staticmethod
    def _normalize_words_with_meta(text: str) -> tuple[str, bool]:
        out = str(text or "").lower()
        fuzzy_corrected = False

        typo_corrections = {
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
        for wrong, right in typo_corrections.items():
            updated = re.sub(rf"\b{re.escape(wrong)}\b", right, out)
            if updated != out:
                fuzzy_corrected = True
                out = updated

        out = out.replace("\u00d7", "*").replace("\u00f7", "/").replace("\u2212", "-")
        out = out.replace("\u221a", "sqrt")

        replacements = {
            "multiplied by": "*",
            "multiply by": "*",
            "times": "*",
            "plus": "+",
            "add": "+",
            "minus": "-",
            "subtract": "-",
            "divided by": "/",
            "divide by": "/",
            "over": "/",
            "to the power of": "^",
            "raised to": "^",
            "power of": "^",
            "squared": "^2",
            "cubed": "^3",
            "square root of": "sqrt",
            "root of": "sqrt",
        }
        for src, dst in replacements.items():
            out = out.replace(src, dst)

        out = re.sub(r"(?:the\s+)?sum of\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)", r"\1 + \2", out)
        out = re.sub(
            r"(?:the\s+)?difference between\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)",
            r"\1 - \2",
            out,
        )
        out = re.sub(r"(?:the\s+)?product of\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)", r"\1 * \2", out)
        out = re.sub(r"(?:the\s+)?quotient of\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)", r"\1 / \2", out)
        out = re.sub(
            r"increase\s+(-?\d+(?:\.\d+)?)\s+by\s+(-?\d+(?:\.\d+)?)\s*percent",
            r"\1 * (1 + \2/100)",
            out,
        )
        out = re.sub(
            r"decrease\s+(-?\d+(?:\.\d+)?)\s+by\s+(-?\d+(?:\.\d+)?)\s*percent",
            r"\1 * (1 - \2/100)",
            out,
        )

        out = re.sub(r"(-?\d+(?:\.\d+)?)\s*percent", r"(\1/100)", out)

        out = re.sub(r"\bsqrt\s*\(\s*([^)]+?)\s*\)", r"sqrt(\1)", out)
        out = re.sub(r"\bsqrt\s+(-?\d+(?:\.\d+)?)", r"sqrt(\1)", out)

        out = re.sub(r"^(?:what is|what's|whats|find|calculate|evaluate)\s+", "", out)
        out = re.sub(r"^solve\s*:\s*", "solve ", out)
        out = re.sub(r"^evaluate\s*:\s*", "evaluate ", out)
        out = re.sub(r"\bmatrix multiplication\b", "matrix multiply", out)
        out = re.sub(r"\bmat mul\b", "matmul", out)

        out = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "*", out)
        out = re.sub(r"\s+", " ", out).strip(" .")
        return out, fuzzy_corrected

    @staticmethod
    def _normalize_words(text: str) -> str:
        normalized, _ = MathEngine._normalize_words_with_meta(text)
        return normalized

    @staticmethod
    def _extract_matrix_pair(text: str) -> tuple[list[list[float]], list[list[float]]] | None:
        low = str(text or "").lower()
        if not any(k in low for k in ["matrix multiply", "matmul", "matrix product"]):
            return None
        chunks = re.findall(r"\[\s*\[.*?\]\s*\]", text)
        if len(chunks) < 2:
            return None
        try:
            a = json.loads(chunks[0])
            b = json.loads(chunks[1])
        except Exception:
            return None
        if not isinstance(a, list) or not isinstance(b, list):
            return None
        return a, b

    @staticmethod
    def _format_number(value: float) -> str:
        if float(value).is_integer():
            return str(int(value))
        return f"{value:.12g}"

    def _safe_eval(self, node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return self._safe_eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            val = self._safe_eval(node.operand)
            return val if isinstance(node.op, ast.UAdd) else -val
        if isinstance(node, ast.BinOp) and type(node.op) in self.ops:
            left = self._safe_eval(node.left)
            right = self._safe_eval(node.right)
            return float(self.ops[type(node.op)](left, right))
        raise ValueError("Unsupported arithmetic expression")

    def _arithmetic(self, expr: str, show_steps: bool) -> dict[str, Any]:
        safe_expr = re.sub(r"\^", "**", expr)
        safe_expr = re.sub(r"(\d)\s*\(", r"\1*(", safe_expr)
        safe_expr = re.sub(r"\)\s*(\d)", r")*\1", safe_expr)
        safe_expr = re.sub(r"\)\s*\(", r")*(", safe_expr)

        if not re.fullmatch(r"[0-9eE\.\+\-\*\/\%\(\)\s]+", safe_expr):
            raise ValueError("Unsafe arithmetic input")

        tree = ast.parse(safe_expr, mode="eval")
        value = self._safe_eval(tree)
        answer = self._format_number(value)
        steps = [f"{expr.strip()} = {answer}"] if show_steps else []
        return {"answer": answer, "steps": steps}

    @lru_cache(maxsize=256)
    def _parse_symbolic(self, expr: str):
        if not SYMPY_READY or parse_expr is None:
            raise ValueError("SymPy parser unavailable")
        return parse_expr(expr, local_dict=self.local, transformations=SYMPY_TRANSFORMS)

    @staticmethod
    def _clean_sympy_text(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value)).strip()

    def improve_steps(
        self,
        expr: Any,
        result: Any,
        operation_type: str,
        detail_mode: str = "normal",
        meta: dict[str, Any] | None = None,
    ) -> list[str]:
        meta = meta or {}
        expr_text = self._clean_sympy_text(expr)
        result_text = self._clean_sympy_text(result)

        if operation_type == "arithmetic":
            return [f"{expr_text} = {result_text}"]

        if operation_type == "equation":
            lhs = self._clean_sympy_text(meta.get("lhs", ""))
            rhs = self._clean_sympy_text(meta.get("rhs", ""))
            rearranged = self._clean_sympy_text(meta.get("rearranged", ""))
            target = self._clean_sympy_text(meta.get("target", "x"))
            steps = [f"Start from equation: {lhs} = {rhs}", f"Rearrange to zero form: {rearranged} = 0", f"Solve for {target}: {result_text}"]
            if detail_mode == "detailed":
                steps.append("Verify by substituting each solution into the original equation.")
            return steps

        if operation_type == "derivative":
            var = self._clean_sympy_text(meta.get("var", "x"))
            steps = [f"Differentiate with respect to {var}: d/d{var}({expr_text})", f"Derivative result: {result_text}"]
            return steps

        if operation_type == "integral":
            var = self._clean_sympy_text(meta.get("var", "x"))
            steps = [f"Set up integral: integral({expr_text}) d{var}", f"Antiderivative: {result_text}"]
            if detail_mode == "detailed":
                steps.append("Add + C for the constant of integration if needed.")
            return steps

        if operation_type == "definite_integral":
            var = self._clean_sympy_text(meta.get("var", "x"))
            a = self._clean_sympy_text(meta.get("a", ""))
            b = self._clean_sympy_text(meta.get("b", ""))
            antiderivative = self._clean_sympy_text(meta.get("antiderivative", "F"))
            return [
                f"Set up definite integral: integral[{a} to {b}] ({expr_text}) d{var}",
                f"Find antiderivative: F({var}) = {antiderivative}",
                f"Substitute bounds: F({b}) - F({a}) = {result_text}",
            ]

        if operation_type == "simplify":
            return [f"Simplify expression: {expr_text}", f"Simplified form: {result_text}"]

        if operation_type == "numeric":
            return [f"Simplify numeric expression: {expr_text}", f"Evaluate result: {result_text}"]

        return [f"{expr_text} -> {result_text}"]

    def _build_response(
        self,
        query: str,
        answer: str,
        steps: list[str],
        solve_mode: str,
        references: list[dict[str, str]],
        fuzzy_corrected: bool = False,
        ambiguous_vars: bool = False,
        show_steps: bool = True,
        backend_name: str = "",
    ) -> dict[str, Any]:
        payload = {
            "answer": str(answer).strip(),
            "steps": list(steps if show_steps else []),
            "_solve_mode": solve_mode,
            "_fuzzy_corrected": bool(fuzzy_corrected),
            "_ambiguous_vars": bool(ambiguous_vars),
            "_backend": backend_name,
        }
        confidence = compute_math_confidence(query, payload)
        return {
            "answer": payload["answer"],
            "steps": payload["steps"],
            "confidence": confidence,
            "references": list(references),
        }

    def solve(self, query: str, force_steps: bool = False) -> dict[str, Any]:
        raw = str(query or "").strip()
        detail_mode = self._explanation_mode(raw)
        show_steps = False if detail_mode == "brief" else (bool(force_steps) or self.wants_steps(raw) or detail_mode == "detailed")

        q = self._strip_step_markers(raw)
        q = self._strip_mode_markers(q)
        q, fuzzy_corrected = self._normalize_words_with_meta(q)

        references = [
            {"title": "Internal Math Engine", "url": "internal://math-engine"},
            {"title": "SymPy Documentation", "url": "https://docs.sympy.org/latest/index.html"},
        ]

        if not q:
            return self._build_response(
                query=raw,
                answer="I could not parse that math expression safely.",
                steps=["Could not extract a valid math expression."],
                solve_mode="failed",
                references=references,
                fuzzy_corrected=fuzzy_corrected,
                ambiguous_vars=False,
                show_steps=show_steps,
            )

        matrix_pair = self._extract_matrix_pair(q)
        if matrix_pair is not None:
            try:
                a, b = matrix_pair
                comp = self.compute_engine.matmul(a, b)
                result = comp.get("result", [])
                backend = str(comp.get("backend", "python"))
                device = str(comp.get("device", "cpu"))
                rows_a = len(a)
                cols_a = len(a[0]) if rows_a else 0
                rows_b = len(b)
                cols_b = len(b[0]) if rows_b else 0
                steps = [
                    f"Validated matrix dimensions: {rows_a}x{cols_a} multiplied by {rows_b}x{cols_b}.",
                    f"Computed matrix product using {backend} on {device}.",
                    f"Result matrix: {result}",
                ]
                refs = list(references) + [{"title": "Compute Engine", "url": "internal://compute-engine"}]
                return self._build_response(
                    query=raw,
                    answer=str(result),
                    steps=steps,
                    solve_mode="matrix_compute",
                    references=refs,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=False,
                    show_steps=show_steps,
                    backend_name=backend,
                )
            except Exception as exc:
                return self._build_response(
                    query=raw,
                    answer=f"Matrix computation failed safely: {exc}",
                    steps=["Validated matrix request.", "Stopped due to safety/shape limits."],
                    solve_mode="failed",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=False,
                    show_steps=show_steps,
                )

        if not SYMPY_READY:
            try:
                ar = self._arithmetic(q, show_steps=True)
                return self._build_response(
                    query=raw,
                    answer=ar["answer"],
                    steps=ar["steps"],
                    solve_mode="arithmetic",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=False,
                    show_steps=show_steps,
                )
            except Exception:
                return self._build_response(
                    query=raw,
                    answer="Math engine unavailable.",
                    steps=["Arithmetic fallback failed safely."],
                    solve_mode="failed",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=False,
                    show_steps=show_steps,
                )

        try:
            neg_sqrt = re.fullmatch(r"sqrt\(\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*\)", q)
            if neg_sqrt:
                mag = sp.Float(neg_sqrt.group(1))
                result = sp.I * sp.sqrt(mag)
                steps = [
                    f"Rewrite as sqrt(-{mag}).",
                    "Use identity: sqrt(-a) = i*sqrt(a).",
                    f"Compute: i*sqrt({mag}) = {result}",
                ]
                return self._build_response(
                    query=raw,
                    answer=self._clean_sympy_text(sp.simplify(result)),
                    steps=steps,
                    solve_mode="symbolic",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=False,
                    show_steps=show_steps,
                )

            if q.startswith("solve "):
                body = q[len("solve ") :].strip()
                if "=" in body:
                    lhs_raw, rhs_raw = body.split("=", 1)
                    lhs = self._parse_symbolic(lhs_raw)
                    rhs = self._parse_symbolic(rhs_raw)
                    eq = sp.Eq(lhs, rhs)
                    vars_ = sorted(list(eq.free_symbols), key=lambda s: s.name)
                    ambiguous = len(vars_) > 1
                    target = vars_[0] if vars_ else self.x
                    solution = sp.solve(eq, target)
                    steps = self.improve_steps(
                        expr=body,
                        result=solution,
                        operation_type="equation",
                        detail_mode=detail_mode,
                        meta={
                            "lhs": sp.simplify(lhs),
                            "rhs": sp.simplify(rhs),
                            "rearranged": sp.expand(lhs - rhs),
                            "target": target,
                        },
                    )
                    return self._build_response(
                        query=raw,
                        answer=self._clean_sympy_text(solution),
                        steps=steps,
                        solve_mode="symbolic",
                        references=references,
                        fuzzy_corrected=fuzzy_corrected,
                        ambiguous_vars=ambiguous,
                        show_steps=show_steps,
                    )
                q = body

            if q.startswith("differentiate ") or q.startswith("derivative of "):
                body = q.replace("differentiate ", "", 1).replace("derivative of ", "", 1).strip()
                expr = self._parse_symbolic(body)
                vars_ = sorted(list(expr.free_symbols), key=lambda s: s.name)
                ambiguous = len(vars_) > 1
                var = vars_[0] if vars_ else self.x
                result = sp.diff(expr, var)
                steps = self.improve_steps(
                    expr=expr,
                    result=result,
                    operation_type="derivative",
                    detail_mode=detail_mode,
                    meta={"var": var},
                )
                return self._build_response(
                    query=raw,
                    answer=self._clean_sympy_text(result),
                    steps=steps,
                    solve_mode="symbolic",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=ambiguous,
                    show_steps=show_steps,
                )

            if q.startswith("integrate "):
                body = q[len("integrate ") :].strip()
                bounds = re.search(r"(.+?)\s+from\s+([^\s]+)\s+to\s+([^\s]+)$", body)
                if bounds:
                    expr_raw, a_raw, b_raw = bounds.group(1), bounds.group(2), bounds.group(3)
                    expr = self._parse_symbolic(expr_raw)
                    vars_ = sorted(list(expr.free_symbols), key=lambda s: s.name)
                    ambiguous = len(vars_) > 1
                    var = vars_[0] if vars_ else self.x
                    a = self._parse_symbolic(a_raw)
                    b = self._parse_symbolic(b_raw)
                    antiderivative = sp.integrate(expr, var)
                    result = sp.integrate(expr, (var, a, b))
                    steps = self.improve_steps(
                        expr=expr,
                        result=result,
                        operation_type="definite_integral",
                        detail_mode=detail_mode,
                        meta={"var": var, "a": a, "b": b, "antiderivative": antiderivative},
                    )
                    return self._build_response(
                        query=raw,
                        answer=self._clean_sympy_text(result),
                        steps=steps,
                        solve_mode="symbolic",
                        references=references,
                        fuzzy_corrected=fuzzy_corrected,
                        ambiguous_vars=ambiguous,
                        show_steps=show_steps,
                    )

                expr = self._parse_symbolic(body)
                vars_ = sorted(list(expr.free_symbols), key=lambda s: s.name)
                ambiguous = len(vars_) > 1
                var = vars_[0] if vars_ else self.x
                result = sp.integrate(expr, var)
                steps = self.improve_steps(
                    expr=expr,
                    result=result,
                    operation_type="integral",
                    detail_mode=detail_mode,
                    meta={"var": var},
                )
                return self._build_response(
                    query=raw,
                    answer=self._clean_sympy_text(result),
                    steps=steps,
                    solve_mode="symbolic",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=ambiguous,
                    show_steps=show_steps,
                )

            if "=" in q and re.search(r"\b[xyz]\b", q):
                lhs_raw, rhs_raw = q.split("=", 1)
                lhs = self._parse_symbolic(lhs_raw)
                rhs = self._parse_symbolic(rhs_raw)
                eq = sp.Eq(lhs, rhs)
                vars_ = sorted(list(eq.free_symbols), key=lambda s: s.name)
                ambiguous = len(vars_) > 1
                target = vars_[0] if vars_ else self.x
                solution = sp.solve(eq, target)
                steps = self.improve_steps(
                    expr=q,
                    result=solution,
                    operation_type="equation",
                    detail_mode=detail_mode,
                    meta={
                        "lhs": sp.simplify(lhs),
                        "rhs": sp.simplify(rhs),
                        "rearranged": sp.expand(lhs - rhs),
                        "target": target,
                    },
                )
                return self._build_response(
                    query=raw,
                    answer=self._clean_sympy_text(solution),
                    steps=steps,
                    solve_mode="symbolic",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=ambiguous,
                    show_steps=show_steps,
                )

            try:
                ar = self._arithmetic(q, show_steps=True)
                return self._build_response(
                    query=raw,
                    answer=ar["answer"],
                    steps=ar["steps"],
                    solve_mode="arithmetic",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=False,
                    show_steps=show_steps,
                )
            except Exception:
                pass

            expr = self._parse_symbolic(q)
            simplified = sp.simplify(expr)
            ambiguous = len(getattr(expr, "free_symbols", set())) > 1

            if getattr(simplified, "free_symbols", set()):
                steps = self.improve_steps(
                    expr=expr,
                    result=simplified,
                    operation_type="simplify",
                    detail_mode=detail_mode,
                )
                return self._build_response(
                    query=raw,
                    answer=self._clean_sympy_text(simplified),
                    steps=steps,
                    solve_mode="symbolic",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=ambiguous,
                    show_steps=show_steps,
                )

            numeric = sp.N(simplified)
            steps = self.improve_steps(
                expr=expr,
                result=numeric,
                operation_type="numeric",
                detail_mode=detail_mode,
            )
            return self._build_response(
                query=raw,
                answer=self._clean_sympy_text(numeric),
                steps=steps,
                solve_mode="symbolic",
                references=references,
                fuzzy_corrected=fuzzy_corrected,
                ambiguous_vars=False,
                show_steps=show_steps,
            )

        except Exception:
            try:
                ar = self._arithmetic(q, show_steps=True)
                steps = ar["steps"] if ar["steps"] else [f"{q} = {ar['answer']}"]
                return self._build_response(
                    query=raw,
                    answer=ar["answer"],
                    steps=steps,
                    solve_mode="fallback_arithmetic",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=False,
                    show_steps=show_steps,
                )
            except Exception:
                return self._build_response(
                    query=raw,
                    answer="I could not parse that math expression safely.",
                    steps=["Parsing failed safely."],
                    solve_mode="failed",
                    references=references,
                    fuzzy_corrected=fuzzy_corrected,
                    ambiguous_vars=False,
                    show_steps=show_steps,
                )
