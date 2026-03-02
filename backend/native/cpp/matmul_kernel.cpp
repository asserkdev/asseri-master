// Optional C++ kernel scaffold for future pybind11 integration.
// Current runtime uses Python/NumPy/Torch backends.

#include <vector>
#include <stdexcept>

std::vector<std::vector<double>> matmul_cpp(
    const std::vector<std::vector<double>>& a,
    const std::vector<std::vector<double>>& b) {
    if (a.empty() || b.empty()) {
        throw std::runtime_error("Empty matrices are not allowed.");
    }
    const std::size_t rows_a = a.size();
    const std::size_t cols_a = a[0].size();
    const std::size_t rows_b = b.size();
    const std::size_t cols_b = b[0].size();
    if (cols_a != rows_b) {
        throw std::runtime_error("Matrix dimensions do not align.");
    }
    std::vector<std::vector<double>> out(rows_a, std::vector<double>(cols_b, 0.0));
    for (std::size_t i = 0; i < rows_a; ++i) {
        for (std::size_t k = 0; k < cols_a; ++k) {
            const double v = a[i][k];
            for (std::size_t j = 0; j < cols_b; ++j) {
                out[i][j] += v * b[k][j];
            }
        }
    }
    return out;
}

