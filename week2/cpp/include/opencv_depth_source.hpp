#pragma once
#include "depth_projection.hpp"
#include <opencv2/core.hpp>

namespace comento {
class OpenCvDepthSource final : public IDepthSource {
public:
    DepthMap load(const std::string& path) const override;
    static DepthMap from_bgr(const cv::Mat& image);
};
}
