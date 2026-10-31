#include <cmath>
#include <cstdint>
#include "opencv_depth_source.hpp"
#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>
#include <iostream>
#include <stdexcept>
#include <string>
int main(int argc,char** argv) {
    if (argc != 3) {
        std::cerr << "Usage: cpp_depth_demo <image> <depth_visualization_png>\n";
        return 2;
    }
    try {
        const comento::OpenCvDepthSource loader;
        auto d=loader.load(argv[1]);
        auto pts=comento::DepthProjection::project(d);
        cv::Mat gray(static_cast<int>(d.height),static_cast<int>(d.width),CV_8UC1);
        for(std::size_t y=0;y<d.height;++y) for(std::size_t x=0;x<d.width;++x)
            gray.at<std::uint8_t>(static_cast<int>(y),static_cast<int>(x)) =
                static_cast<std::uint8_t>(std::lround(d.intensity[y*d.width+x]*255.f));
        cv::Mat jet;cv::applyColorMap(gray,jet,cv::COLORMAP_JET);
        if (!cv::imwrite(argv[2],jet)) throw std::runtime_error("Cannot save PNG");
        std::cout << "points=" << pts.size() << ", width=" << d.width
                  << ", height=" << d.height << ", first_z=" << pts.front().z << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 1;
    }
}
