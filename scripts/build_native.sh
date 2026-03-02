#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Native build scaffold only."
echo "Compile backend/native/cpp/matmul_kernel.cpp with pybind11 if you enable native extension builds."

