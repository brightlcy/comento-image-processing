#include "depth_projection.hpp"
#include <cmath>
#include <limits>
#include <stdexcept>

namespace comento {
namespace {
void check_map(const DepthMap& d, std::size_t max_points) {
    if (d.width == 0 || d.height == 0 || max_points == 0 ||
        d.width > std::numeric_limits<std::size_t>::max() / d.height ||
        d.width * d.height > max_points || d.intensity.size() != d.width * d.height) {
        throw std::invalid_argument("Invalid depth shape or point budget exceeded");
    }
    for (float value : d.intensity) {
        if (!std::isfinite(value) || value < 0.0f || value > 1.0f) {
            throw std::invalid_argument("Depth intensity must be finite within [0,1]");
        }
    }
}
void check_scale(float z_scale) {
    if (!std::isfinite(z_scale) || z_scale <= 0.0f ||
        z_scale < std::numeric_limits<float>::denorm_min()) {
        throw std::invalid_argument("z_scale must be positive, finite, nonzero float");
    }
}
std::size_t ceil_div(std::size_t length, std::size_t stride) {
    return length / stride + (length % stride != 0);
}
}

std::vector<Point3D> DepthProjection::project(const DepthMap& d,
                                               float z_scale,
                                               std::size_t max_points) {
    check_map(d,max_points);
    check_scale(z_scale);
    std::vector<Point3D> points;
    points.reserve(d.intensity.size());
    for (std::size_t y=0;y<d.height;++y) {
        for (std::size_t x=0;x<d.width;++x) {
            float z=d.intensity[y*d.width+x]*z_scale;
            if (!std::isfinite(z)) throw std::invalid_argument("Projected z overflows float");
            points.push_back({static_cast<float>(x),static_cast<float>(y),z});
        }
    }
    return points;
}

std::size_t DepthProjection::sampling_step(std::size_t width,
                                            std::size_t height,
                                            std::size_t plot_budget) {
    if (width==0 || height==0 || plot_budget==0) {
        throw std::invalid_argument("Invalid plotting dimensions or point budget");
    }
    auto fits=[=](std::size_t step) {
        std::size_t rows=ceil_div(height,step);
        std::size_t cols=ceil_div(width,step);
        return cols <= plot_budget / rows; // avoid multiplication overflow
    };
    std::size_t lo=1, hi=(width>height?width:height);
    while (lo<hi) {
        std::size_t mid=lo+(hi-lo)/2;
        if (fits(mid)) hi=mid;
        else lo=mid+1;
    }
    return lo;
}

std::vector<Point3D> DepthProjection::sample(const DepthMap& d,
                                              float z_scale,
                                              std::size_t plot_budget) {
    check_map(d,3'000'000);
    check_scale(z_scale);
    const auto stride=sampling_step(d.width,d.height,plot_budget);
    std::vector<Point3D> points;
    points.reserve(ceil_div(d.width,stride)*ceil_div(d.height,stride));
    for (std::size_t y=0;y<d.height;y+=stride) {
        for (std::size_t x=0;x<d.width;x+=stride) {
            const float z=d.intensity[y*d.width+x]*z_scale;
            if(!std::isfinite(z)) throw std::invalid_argument("Projected z overflows float");
            points.push_back({static_cast<float>(x),static_cast<float>(y),z});
        }
    }
    return points;
}

std::vector<Point3D> ProjectionService::from_file(const std::string& path,
                                                   float z_scale) const {
    return DepthProjection::project(source_.load(path),z_scale);
}
} // namespace comento
