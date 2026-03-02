from __future__ import annotations

from typing import Any

import numpy as np

try:
    import torch

    TORCH_READY = True
except Exception:
    torch = None
    TORCH_READY = False


class ComputeEngine:
    """Optional acceleration layer (NumPy / Torch CUDA / Python fallback)."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.prefer_gpu = bool(cfg.get("prefer_gpu", True))
        self.allow_torch_cuda = bool(cfg.get("allow_torch_cuda", True))
        self.allow_native_cpp = bool(cfg.get("allow_native_cpp", False))
        self.max_matrix_size = max(2, int(cfg.get("max_matrix_size", 128)))

    def capabilities(self) -> dict[str, Any]:
        cuda_available = bool(TORCH_READY and torch is not None and torch.cuda.is_available() and self.allow_torch_cuda)
        return {
            "numpy": True,
            "torch_installed": bool(TORCH_READY),
            "cuda_available": cuda_available,
            "prefer_gpu": self.prefer_gpu,
            "allow_native_cpp": self.allow_native_cpp,
            "max_matrix_size": self.max_matrix_size,
        }

    @staticmethod
    def _validate_matrix_payload(a: list[list[float]], b: list[list[float]]) -> tuple[int, int, int]:
        if not a or not b or not isinstance(a, list) or not isinstance(b, list):
            raise ValueError("Matrices must be non-empty lists.")
        if not all(isinstance(row, list) and row for row in a):
            raise ValueError("First matrix rows must be non-empty lists.")
        if not all(isinstance(row, list) and row for row in b):
            raise ValueError("Second matrix rows must be non-empty lists.")
        rows_a = len(a)
        cols_a = len(a[0])
        rows_b = len(b)
        cols_b = len(b[0])
        if any(len(row) != cols_a for row in a):
            raise ValueError("First matrix has inconsistent row sizes.")
        if any(len(row) != cols_b for row in b):
            raise ValueError("Second matrix has inconsistent row sizes.")
        if cols_a != rows_b:
            raise ValueError("Matrix dimensions do not align for multiplication.")
        return rows_a, cols_a, cols_b

    def _matmul_python(self, a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
        rows_a, cols_a, cols_b = self._validate_matrix_payload(a, b)
        out = [[0.0 for _ in range(cols_b)] for _ in range(rows_a)]
        for i in range(rows_a):
            for k in range(cols_a):
                aik = float(a[i][k])
                for j in range(cols_b):
                    out[i][j] += aik * float(b[k][j])
        return out

    @staticmethod
    def _normalize_result(mat: Any) -> list[list[float]]:
        arr = np.asarray(mat, dtype=float)
        return [[float(v) for v in row] for row in arr.tolist()]

    def matmul(self, a: list[list[float]], b: list[list[float]]) -> dict[str, Any]:
        rows_a, cols_a, cols_b = self._validate_matrix_payload(a, b)
        if max(rows_a, cols_a, cols_b) > self.max_matrix_size:
            raise ValueError(f"Matrix size exceeds configured limit ({self.max_matrix_size}).")

        if self.prefer_gpu and TORCH_READY and torch is not None and self.allow_torch_cuda and torch.cuda.is_available():
            ta = torch.tensor(a, dtype=torch.float32, device="cuda")
            tb = torch.tensor(b, dtype=torch.float32, device="cuda")
            tc = ta @ tb
            return {
                "result": self._normalize_result(tc.detach().cpu().numpy()),
                "backend": "torch_cuda",
                "device": "gpu",
            }

        try:
            na = np.asarray(a, dtype=float)
            nb = np.asarray(b, dtype=float)
            nc = na @ nb
            return {"result": self._normalize_result(nc), "backend": "numpy", "device": "cpu"}
        except Exception:
            out = self._matmul_python(a, b)
            return {"result": out, "backend": "python", "device": "cpu"}

