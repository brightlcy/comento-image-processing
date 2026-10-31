// Standalone C++ tests that run even on offline machines without GoogleTest/OpenCV-dev.
// These are NOT GoogleTest; actual GoogleTest/gMock tests live in test_depth_projection.cpp.
#include "depth_projection.hpp"
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
using namespace comento;

static int cases=0;
static void test(bool ok,const char* name){++cases;if(!ok)throw std::runtime_error(name);}
template<typename Fn> static bool rejects(Fn fn){try{fn();return false;}catch(const std::invalid_argument&){return true;}}

struct FakeDepthSource: IDepthSource {
    DepthMap load(const std::string& name) const override {
        if(name!="fixture") throw std::runtime_error("missing");
        return {1,1,{.5f}};
    }
};

int main(){try {
    const auto pts=DepthProjection::project({2,3,{0,.1f,.2f,.3f,.4f,.5f}},10);
    test(pts.size()==6,"6 xyz points");
    test(pts[2].x==0 && pts[2].y==1 && std::abs(pts[2].z-2)<1e-5,"xy row major");
    test(pts[5].x==1 && pts[5].y==2 && pts[5].z==5,"xy last point");
    test(DepthProjection::project({1,1,{1}},40)[0].z==40,"white at 40");
    test(rejects([]{DepthProjection::project({0,1,{}});}),"zero shape");
    test(rejects([]{DepthProjection::project({2,2,{1}});}),"shape mismatch");
    test(rejects([]{DepthProjection::project({1,1,{-1}});}),"negative depth");
    test(rejects([]{DepthProjection::project({1,1,{std::numeric_limits<float>::infinity()}});}),"infinite depth");
    test(rejects([]{DepthProjection::project({1,1,{1}},0);}),"zero scale");
    test(rejects([]{DepthProjection::project({2,1,{0,1}},40,1);}),"point budget");
    test(rejects([]{DepthProjection::project({std::numeric_limits<size_t>::max(),2,{}});}),"dimension overflow");
    const auto step=DepthProjection::sampling_step(100000,1,7000);
    test(step>=15 && (100000/step+(100000%step!=0))<=7000,"skinny sampling");
    test(DepthProjection::sampling_step(512,512,7000)==7,"square sampling");
    test(rejects([]{DepthProjection::sampling_step(2,3,0);}),"zero plot budget");
    test(DepthProjection::sample({5,3,std::vector<float>(15,.5f)},10,4).size()==2,"bounded plotting");
    FakeDepthSource f;
    test(ProjectionService(f).from_file("fixture",10)[0].z==5,"fake input seam");
    std::cout<<"Portable C++ smoke: "<<cases<<"/"<<cases<<" PASS (NOT GoogleTest/gMock)\n";
    return 0;
} catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}}
