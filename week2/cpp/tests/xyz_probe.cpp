// Test utility, not an additional image-processing feature.
#include "opencv_depth_source.hpp"
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

int main(int argc,char** argv) {
    try {
        comento::DepthMap depth;
        float scale=40;
        std::size_t budget=0;
        if(argc==4 && std::string(argv[1])=="image") {
            depth=comento::OpenCvDepthSource().load(argv[2]);
            scale=std::stof(argv[3]);
        } else if(argc==2 && (std::string(argv[1])=="project" || std::string(argv[1])=="sample")) {
            if(!(std::cin>>depth.width>>depth.height>>scale>>budget) ||
               depth.width==0 || depth.height==0 || depth.height>3'000'000 ||
               depth.width>3'000'000/depth.height) throw std::invalid_argument("Bad test input shape");
            depth.intensity.resize(depth.width*depth.height);
            for(auto& value : depth.intensity) if(!(std::cin>>value))
                throw std::invalid_argument("Incomplete test input");
        } else {
            throw std::invalid_argument("Usage: cpp_xyz_probe {project|sample} < map.txt OR image <png> <scale>");
        }
        const auto points=argc==2 && std::string(argv[1])=="sample"
            ? comento::DepthProjection::sample(depth,scale,budget)
            : comento::DepthProjection::project(depth,scale);
        std::cout<<points.size()<<'\n'<<std::setprecision(std::numeric_limits<float>::max_digits10);
        for(const auto& p : points) std::cout<<p.x<<' '<<p.y<<' '<<p.z<<'\n';
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<e.what()<<'\n';return 1;
    }
}
