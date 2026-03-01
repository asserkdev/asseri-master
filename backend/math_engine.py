from __future__ import annotations

import ast
import operator
import re
from typing import Any

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
    """Safe math engine with arithmetic and symbolic operations."""

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

    @staticmethod
    def _normalize_words(text: str) -> str:
        out = text.lower()
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
            "modulo": "%",
            "remainder": "%",
            "square root of": "sqrt",
            "sqrt of": "sqrt",
        }
        for src, dst in replacements.items():
            out = out.replace(src, dst)
        out = out.replace("Ã—", "*").replace("Ã·", "/").replace("âˆ’", "-")
        out = out.replace("\u2212", "-").replace("\u00d7", "*").replace("\u00f7", "/")
        out = re.sub(r"\u221a\s*\(\s*([^)]+?)\s*\)", r"sqrt(\1)", out)
        out = re.sub(r"\u221a\s*(-?\d+(?:\.\d+)?)", r"sqrt(\1)", out)
        out = re.sub(r"\bsqrt\s*\(\s*([^)]+?)\s*\)", r"sqrt(\1)", out)
        out = re.sub(r"\bsqrt\s+(-?\d+(?:\.\d+)?)", r"sqrt(\1)", out)
        out = re.sub(r"(\d+)\s*percent", r"(\1/100)", out)
        out = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "*", out)
        out = re.sub(r"\s*:\s*", " ", out)
        out = re.sub(r"\s+", " ", out).strip()
        return out

    @staticmethod
    def is_math_query(text: str) -> bool:
        q = text.lower()
        triggers = [
            "calculate",
            "compute",
            "evaluate",
            "solve",
            "equation",
            "integrate",
            "differentiate",
            "derivative",
            "factor",
            "simplify",
            "expand",
            "limit",
            "matrix",
            "determinant",
            "inverse",
            "eigenvalue",
            "plus",
            "minus",
            "multiply",
            "divide",
            "sqrt",
            "root",
            "log",
        ]
        if any(t in q for t in triggers):
            return True
        if "âˆš" in q:
            return True
        if re.search(r"[\d\)\(]\s*[\+\-\*\/\^%]", q):
            return True
        return False

    @staticmethod
    def wants_steps(text: str) -> bool:
        markers = [
            "step by step",
            "show steps",
            "show work",
            "with steps",
            "how did you solve",
        ]
        t = text.lower()
        return any(m in t for m in markers)

    @staticmethod
    def _strip_step_markers(text: str) -> str:
        t = text
        for p in [
            r"\bstep by step\b",
            r"\bshow (?:the )?steps\b",
            r"\bshow (?:your )?work\b",
            r"\bwith steps\b",
            r"\bhow did you solve\b",
            r"\beach step\b",
            r"\beach steps\b",
            r"\bexplain each step\b",
            r"\bexplain each steps\b",
            r"\band explain each step\b",
            r"\band explain each steps\b",
            r"\band explain\b",
            r"\bexplain\b$",
        ]:
            t = re.sub(p, " ", t, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", t).strip(" ,.!?")

    def _safe_eval(self, node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return self._safe_eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._safe_eval(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in self.ops:
            left = self._safe_eval(node.left)
            right = self._safe_eval(node.right)
            return float(self.ops[type(node.op)](left, right))
        raise ValueError("Unsupported expression")

    def _eval_steps(self, node: ast.AST) -> tuple[float, str, list[str]]:
        if isinstance(node, ast.Expression):
            return self._eval_steps(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            value = float(node.value)
            text = str(int(value)) if value.is_integer() else str(value)
            return value, text, []
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value, expr, steps = self._eval_steps(node.operand)
            if isinstance(node.op, ast.USub):
                res = -value
                res_text = str(int(res)) if res.is_integer() else str(res)
                return res, res_text, steps + [f"-({expr}) = {res_text}"]
            return value, expr, steps
        if isinstance(node, ast.BinOp) and type(node.op) in self.ops:
            lv, lt, ls = self._eval_steps(node.left)
            rv, rt, rs = self._eval_steps(node.right)
            op = type(node.op)
            result = float(self.ops[op](lv, rv))
            result_text = str(int(result)) if result.is_integer() else str(result)
            step = f"({lt}) {self.symbols[op]} ({rt}) = {result_text}"
            return result, result_text, ls + rs + [step]
        raise ValueError("Unsupported expression")

    def _arithmetic(self, expr: str, show_steps: bool) -> dict[str, Any]:
        expr = re.sub(r"(\d)\s*\(", r"\1*(", expr)
        expr = re.sub(r"\)\s*(\d)", r")*\1", expr)
        expr = re.sub(r"\)\s*\(", r")*(", expr)
        if not re.fullmatch(r"[\d\s\+\-\*\/\%\(\)\.]+", expr):
            raise ValueError("Not a pure arithmetic expression")
        tree = ast.parse(expr, mode="eval")
        if show_steps:
            result, _, steps = self._eval_steps(tree)
            final = str(int(result)) if float(result).is_integer() else str(result)
            return {"answer": final, "steps": steps}
        value = self._safe_eval(tree)
        final = str(int(value)) if float(value).is_integer() else str(value)
        return {"answer": final, "steps": []}

    @staticmethod
    def _ensure_steps(steps: list[str], fallback: str) -> list[str]:
        if steps:
            return steps
        return [fallback]

    def solve(self, query: str, force_steps: bool = True) -> dict[str, Any]:
        raw = query.strip()
        show_steps = force_steps or self.wants_steps(raw)
        q = self._strip_step_markers(raw.lower())
        q = self._normalize_words(q)
        q = re.sub(r"^what is ", "", q)
        q = re.sub(r"^what's ", "", q)
        q = re.sub(r"^find ", "", q)
        q = re.sub(r"^solve\s*:\s*", "solve ", q)
        q = re.sub(r"^evaluate\s*:\s*", "evaluate ", q)
        q = q.strip(" .")

        references = [
            {"title": "Internal Math Engine", "url": "internal://math-engine"},
            {"title": "SymPy Documentation", "url": "https://docs.sympy.org/latest/index.html"},
        ]

        if not SYMPY_READY:
            ar = self._arithmetic(q, show_steps=show_steps)
            return {
                "answer": ar["answer"],
                "steps": self._ensure_steps(ar["steps"], "Evaluate arithmetic expression safely."),
                "confidence": 0.9,
                "references": references,
            }

        x, y, z = sp.symbols("x y z")
        local = {"x": x, "y": y, "z": z, "pi": sp.pi, "e": sp.E}

        try:
            neg_sqrt = re.fullmatch(r"sqrt\(\s*-\s*([0-9]+(?:\.\d+)?)\s*\)", q)
            if neg_sqrt:
                mag = sp.Float(neg_sqrt.group(1))
                root = sp.sqrt(mag)
                result = sp.I * root
                steps = [
                    f"Interpret expression as sqrt(-{mag}).",
                    "A square root of a negative number is not a real value.",
                    f"Use sqrt(-a) = i*sqrt(a): i*sqrt({mag}) = {result}.",
                ]
                return {
                    "answer": f"{sp.simplify(result)}",
                    "steps": steps if show_steps else [],
                    "confidence": 0.96,
                    "references": references,
                }

            if q.startswith("solve "):
                body = q[len("solve ") :].strip()
                if "=" in body:
                    lhs_raw, rhs_raw = body.split("=", 1)
                    lhs = parse_expr(lhs_raw, local_dict=local, transformations=SYMPY_TRANSFORMS)
                    rhs = parse_expr(rhs_raw, local_dict=local, transformations=SYMPY_TRANSFORMS)
                    eq = sp.Eq(lhs, rhs)
                    vars_ = sorted(list(eq.free_symbols), key=lambda s: s.name)
                    target = vars_[0] if len(vars_) == 1 else vars_
                    solution = sp.solve(eq, target, dict=True)
                    steps = [
                        f"Parsed equation: {sp.simplify(lhs)} = {sp.simplify(rhs)}",
                        f"Rearranged: {sp.expand(lhs - rhs)} = 0",
                        f"Solved for {target}: {solution}",
                    ]
                    return {
                        "answer": f"{solution}",
                        "steps": steps if show_steps else [],
                        "confidence": 0.95,
                        "references": references,
                    }
                q = body

            if q.startswith("differentiate ") or q.startswith("derivative of "):
                body = q.replace("differentiate ", "", 1).replace("derivative of ", "", 1).strip()
                expr = parse_expr(body, local_dict=local, transformations=SYMPY_TRANSFORMS)
                var = sorted(list(expr.free_symbols), key=lambda s: s.name)[0] if expr.free_symbols else x
                result = sp.diff(expr, var)
                return {
                    "answer": f"{result}",
                    "steps": self._ensure_steps(
                        [f"Differentiate {expr} with respect to {var}."] if show_steps else [],
                        "Apply symbolic differentiation.",
                    ),
                    "confidence": 0.95,
                    "references": references,
                }

            if q.startswith("integrate "):
                body = q[len("integrate ") :].strip()
                bounds = re.search(r"(.+)\s+from\s+([^\s]+)\s+to\s+([^\s]+)$", body)
                if bounds:
                    expr_raw, a_raw, b_raw = bounds.group(1), bounds.group(2), bounds.group(3)
                    expr = parse_expr(expr_raw, local_dict=local, transformations=SYMPY_TRANSFORMS)
                    var = sorted(list(expr.free_symbols), key=lambda s: s.name)[0] if expr.free_symbols else x
                    a = parse_expr(a_raw, local_dict=local, transformations=SYMPY_TRANSFORMS)
                    b = parse_expr(b_raw, local_dict=local, transformations=SYMPY_TRANSFORMS)
                    result = sp.integrate(expr, (var, a, b))
                    steps = [f"Integrate {expr} with bounds {var}: {a} -> {b}"] if show_steps else []
                    return {
                        "answer": f"{result}",
                        "steps": self._ensure_steps(steps, "Apply definite integration."),
                        "confidence": 0.95,
                        "references": references,
                    }
                expr = parse_expr(body, local_dict=local, transformations=SYMPY_TRANSFORMS)
                var = sorted(list(expr.free_symbols), key=lambda s: s.name)[0] if expr.free_symbols else x
                result = sp.integrate(expr, var)
                steps = [f"Integrate {expr} with respect to {var}."] if show_steps else []
                return {
                    "answer": f"{result}",
                    "steps": self._ensure_steps(steps, "Apply symbolic integration."),
                    "confidence": 0.95,
                    "references": references,
                }

            if q.startswith("factor "):
                expr = parse_expr(q[len("factor ") :], local_dict=local, transformations=SYMPY_TRANSFORMS)
                result = sp.factor(expr)
                return {
                    "answer": f"{result}",
                    "steps": self._ensure_steps(["Apply factorization."] if show_steps else [], "Factor expression."),
                    "confidence": 0.93,
                    "references": references,
                }

            if q.startswith("expand "):
                expr = parse_expr(q[len("expand ") :], local_dict=local, transformations=SYMPY_TRANSFORMS)
                result = sp.expand(expr)
                return {
                    "answer": f"{result}",
                    "steps": self._ensure_steps(["Apply expansion."] if show_steps else [], "Expand expression."),
                    "confidence": 0.93,
                    "references": references,
                }

            if q.startswith("simplify "):
                expr = parse_expr(q[len("simplify ") :], local_dict=local, transformations=SYMPY_TRANSFORMS)
                result = sp.simplify(expr)
                return {
                    "answer": f"{result}",
                    "steps": self._ensure_steps(["Apply simplification."] if show_steps else [], "Simplify expression."),
                    "confidence": 0.93,
                    "references": references,
                }

            if q.startswith("limit "):
                body = q[len("limit ") :].strip()
                m = re.search(r"(.+)\s+as\s+([a-z])\s*(?:->|approaches)\s*([^\s]+)$", body)
                if m:
                    expr_raw, var_raw, point_raw = m.group(1), m.group(2), m.group(3)
                    expr = parse_expr(expr_raw, local_dict=local, transformations=SYMPY_TRANSFORMS)
                    point = parse_expr(point_raw, local_dict=local, transformations=SYMPY_TRANSFORMS)
                    result = sp.limit(expr, sp.Symbol(var_raw), point)
                    steps = [f"Evaluate limit of {expr} as {var_raw}->{point}."] if show_steps else []
                    return {
                        "answer": f"{result}",
                        "steps": self._ensure_steps(steps, "Compute symbolic limit."),
                        "confidence": 0.94,
                        "references": references,
                    }

            if q.startswith("det ") or q.startswith("determinant "):
                body = q.split(" ", 1)[1].strip()
                matrix = ast.literal_eval(body)
                m = sp.Matrix(matrix)
                value = m.det()
                return {
                    "answer": f"{value}",
                    "steps": self._ensure_steps(["Compute determinant."] if show_steps else [], "Use determinant formula."),
                    "confidence": 0.94,
                    "references": references,
                }

            if q.startswith("inverse "):
                body = q[len("inverse ") :].strip()
                matrix = ast.literal_eval(body)
                m = sp.Matrix(matrix)
                value = m.inv()
                return {
                    "answer": f"{value}",
                    "steps": self._ensure_steps(["Compute matrix inverse."] if show_steps else [], "Apply inverse computation."),
                    "confidence": 0.93,
                    "references": references,
                }

            if q.startswith("eigenvalues "):
                body = q[len("eigenvalues ") :].strip()
                matrix = ast.literal_eval(body)
                m = sp.Matrix(matrix)
                value = m.eigenvals()
                return {
                    "answer": f"{value}",
                    "steps": self._ensure_steps(
                        ["Solve characteristic polynomial."] if show_steps else [],
                        "Compute eigenvalues from characteristic polynomial.",
                    ),
                    "confidence": 0.93,
                    "references": references,
                }

            expr = parse_expr(q, local_dict=local, transformations=SYMPY_TRANSFORMS)
            if expr.free_symbols:
                result = sp.simplify(expr)
                return {
                    "answer": f"{result}",
                    "steps": self._ensure_steps(
                        ["Simplify symbolic expression."] if show_steps else [],
                        "Simplify symbolic form.",
                    ),
                    "confidence": 0.9,
                    "references": references,
                }
            value = sp.N(expr)
            if hasattr(value, "as_real_imag"):
                real_part, imag_part = value.as_real_imag()
                if imag_part != 0:
                    steps = [
                        f"Parsed expression: {expr}",
                        "The result includes an imaginary component, so complex numbers are required.",
                        f"Computed value: {value}",
                    ] if show_steps else []
                    return {
                        "answer": f"{sp.simplify(value)}",
                        "steps": self._ensure_steps(steps, "Evaluate expression in complex domain."),
                        "confidence": 0.94,
                        "references": references,
                    }
            return {
                "answer": f"{value}",
                "steps": self._ensure_steps(
                    [f"Evaluate {expr} numerically."] if show_steps else [],
                    "Evaluate numeric expression.",
                ),
                "confidence": 0.9,
                "references": references,
            }
        except Exception:
            try:
                ar = self._arithmetic(q, show_steps=show_steps)
            except Exception:
                return {
                    "answer": "I could not parse that math expression safely. Try: sqrt(-16), 2*(3+4), or solve x^2=9.",
                    "steps": ["Parser fallback failed; returned safe guidance."],
                    "confidence": 0.52,
                    "references": references,
                }
            return {
                "answer": ar["answer"],
                "steps": self._ensure_steps(ar["steps"], "Fallback to arithmetic evaluation."),
                "confidence": 0.85,
                "references": references,
            }
