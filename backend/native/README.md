# Native Acceleration Scaffold

This folder contains optional high-performance kernels:

- `cpp/matmul_kernel.cpp` for C++ extension work
- `cuda/matmul_kernel.cu` for CUDA GPU kernels

The runtime currently uses:

1. Torch CUDA when available
2. NumPy CPU backend
3. Pure Python fallback

You can later wire native C++/CUDA builds into `backend/compute_engine.py` without changing the public API.

