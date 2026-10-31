#pragma once

#include <cstddef>
#include <string>
#include <vector>

namespace comento {

// Illustrative 2.5D intensity, not physical camera distance.
struct DepthMap {
    std::size_t width = 0;
    std::size_t height = 0;
    std::vector<float> intensity; // row-major, normalized [0, 1]
};

struct Point3D {
    float x;
    float y;
    float z;
};

// Dependency boundary: gMock tests can simulate successful/failed image loading.
class IDepthSource {
public:
    virtual ~IDepthSource() = default;
    virtual DepthMap load(const std::string& filename) const = 0;
};

class DepthProjection {
public:
    // Same rule as the Python assignment: (column, row, intensity * z_scale).
    static std::vector<Point3D> project(const DepthMap& map,
                                        float z_scale = 40.0f,
                                        std::size_t max_points = 3'000'000);

    // Sample just for plotting: smallest uniform stride that respects the budget.
    static std::size_t sampling_step(std::size_t width, std::size_t height,
                                     std::size_t plot_budget);

    static std::vector<Point3D> sample(const DepthMap& map, float z_scale,
                                       std::size_t plot_budget);
};

class ProjectionService {
public:
    explicit ProjectionService(const IDepthSource& source) : source_(source) {}
    std::vector<Point3D> from_file(const std::string& path,
                                   float z_scale = 40.0f) const;
private:
    const IDepthSource& source_;
};

} // namespace comento
