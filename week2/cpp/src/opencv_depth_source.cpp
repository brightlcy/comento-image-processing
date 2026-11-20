#include <cstdint>
#include "opencv_depth_source.hpp"
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <stdexcept>

namespace comento {
DepthMap OpenCvDepthSource::from_bgr(const cv::Mat& image) {
    if (image.empty() || image.dims != 2 || image.type() != CV_8UC3) {
        throw std::invalid_argument("Expected nonempty uint8 BGR image with 3 channels");
    }
    cv::Mat gray;
    cv::cvtColor(image,gray,cv::COLOR_BGR2GRAY);
    DepthMap map;
    map.width=static_cast<std::size_t>(gray.cols);
    map.height=static_cast<std::size_t>(gray.rows);
    map.intensity.reserve(map.width * map.height);
    for (int row=0;row<gray.rows;++row) {
        const auto* pixels=gray.ptr<std::uint8_t>(row);
        for(int col=0;col<gray.cols;++col) map.intensity.push_back(pixels[col] / 255.0f);
    }
    return map;
}
DepthMap OpenCvDepthSource::load(const std::string& path) const {
    cv::Mat image=cv::imread(path,cv::IMREAD_COLOR);
    if(image.empty()) throw std::runtime_error("Cannot load image: " + path);
    return from_bgr(image);
}
}
