// Optional CUDA kernel scaffold for future integration.
// This file is not compiled by default.

#include <cuda_runtime.h>

extern "C" __global__ void matmul_kernel(
    const float* a,
    const float* b,
    float* c,
    int rows_a,
    int cols_a,
    int cols_b) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    if (row < rows_a && col < cols_b) {
        float sum = 0.0f;
        for (int k = 0; k < cols_a; ++k) {
            sum += a[row * cols_a + k] * b[k * cols_b + col];
        }
        c[row * cols_b + col] = sum;
    }
}

