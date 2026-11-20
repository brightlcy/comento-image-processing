#include "opencv_depth_source.hpp"
#include <gtest/gtest.h>
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>
#include <cmath>
#include <filesystem>
#include <chrono>
#include <fstream>
#include <stdexcept>
using namespace comento;

namespace {
// Per-test filesystem fixtures keep loading checks independent of the checkout.
class TempImages {
public:
    std::filesystem::path path;
    TempImages() {
        const auto stamp=std::chrono::steady_clock::now().time_since_epoch().count();
        for(int i=0;i<100;++i) {
            path=std::filesystem::temp_directory_path()/
                ("comento-gtest-"+std::to_string(stamp)+"-"+std::to_string(i));
            if(std::filesystem::create_directory(path)) return;
        }
        throw std::runtime_error("Cannot create test directory");
    }
    ~TempImages() {std::error_code ignored;std::filesystem::remove_all(path,ignored);}
};
}

TEST(OpenCvAdapter, OneByTwoBlackAndWhiteBgrMatchesPythonRule) {
    cv::Mat img(1,2,CV_8UC3);
    img.at<cv::Vec3b>(0,0)=cv::Vec3b(0,0,0);
    img.at<cv::Vec3b>(0,1)=cv::Vec3b(255,255,255);
    auto depth=OpenCvDepthSource::from_bgr(img);
    ASSERT_EQ(depth.intensity.size(),2u);
    EXPECT_FLOAT_EQ(depth.intensity[0],0.f);
    EXPECT_FLOAT_EQ(depth.intensity[1],1.f);
}
TEST(OpenCvAdapter, KnownBlueBgrPixelNotMistakenForRed) {
    cv::Mat blue(1,1,CV_8UC3,cv::Scalar(255,0,0));
    auto depth=OpenCvDepthSource::from_bgr(blue);
    const cv::Mat gray=cv::Mat(1,1,CV_8UC1,cv::Scalar(29));
    EXPECT_NEAR(depth.intensity[0],gray.at<uint8_t>(0,0)/255.0f,1.0f/255.0f);
    EXPECT_FLOAT_EQ(depth.intensity[0],29.f/255.f);
}
TEST(OpenCvAdapter, DepthCoordinatesMatchInputLayout) {
    cv::Mat image(3,2,CV_8UC3,cv::Scalar(0,0,255));
    auto depth=OpenCvDepthSource::from_bgr(image);
    auto pts=DepthProjection::project(depth);
    ASSERT_EQ(pts.size(),6u);
    EXPECT_FLOAT_EQ(pts[4].x,0); EXPECT_FLOAT_EQ(pts[4].y,2);
}
TEST(OpenCvAdapter, RejectsUnsupportedTypesAndEmptyMat) {
    EXPECT_THROW(OpenCvDepthSource::from_bgr(cv::Mat()),std::invalid_argument);
    EXPECT_THROW(OpenCvDepthSource::from_bgr(cv::Mat(2,2,CV_8UC1)),std::invalid_argument);
    EXPECT_THROW(OpenCvDepthSource::from_bgr(cv::Mat(2,2,CV_32FC3)),std::invalid_argument);
}
TEST(OpenCvAdapter, MissingImageThrows) {
    const TempImages files;
    OpenCvDepthSource source;
    EXPECT_THROW(source.load((files.path/"missing.png").string()),std::runtime_error);
}

TEST(OpenCvAdapter, NonContinuousRoiUsesRowStrideAndPreservesInput) {
    cv::Mat padded(3,5,CV_8UC3,cv::Scalar(255,255,255));
    cv::Mat roi=padded(cv::Rect(1,0,2,3));
    const std::uint8_t expected[]={0,51,102,153,204,255};
    for(int y=0;y<3;++y) for(int x=0;x<2;++x) {
        const auto v=expected[y*2+x];
        roi.at<cv::Vec3b>(y,x)=cv::Vec3b(v,v,v);
    }
    ASSERT_FALSE(roi.isContinuous());
    const auto before=padded.clone();
    const auto depth=OpenCvDepthSource::from_bgr(roi);
    ASSERT_EQ(depth.width,2u); ASSERT_EQ(depth.height,3u);
    ASSERT_EQ(depth.intensity.size(),6u);
    for(std::size_t i=0;i<6;++i) EXPECT_FLOAT_EQ(depth.intensity[i],expected[i]/255.f);
    EXPECT_EQ(cv::norm(padded,before,cv::NORM_INF),0);
}
TEST(OpenCvAdapter, RejectsVolumeAndAdditionalChannelTypes) {
    const int dims[]={2,2,2};
    EXPECT_THROW(OpenCvDepthSource::from_bgr(cv::Mat(3,dims,CV_8UC3)),std::invalid_argument);
    EXPECT_THROW(OpenCvDepthSource::from_bgr(cv::Mat(2,2,CV_8UC4)),std::invalid_argument);
    EXPECT_THROW(OpenCvDepthSource::from_bgr(cv::Mat(2,2,CV_16UC3)),std::invalid_argument);
}
TEST(OpenCvAdapter, ActualPngLoadPreservesPixelsAndProjectsCoordinates) {
    const TempImages files;
    const auto path=files.path/"fixture.png";
    cv::Mat input(3,2,CV_8UC3);
    const std::uint8_t values[]={0,255,51,102,153,204};
    for(int y=0;y<3;++y) for(int x=0;x<2;++x) {
        const auto v=values[y*2+x];input.at<cv::Vec3b>(y,x)=cv::Vec3b(v,v,v);
    }
    ASSERT_TRUE(cv::imwrite(path.string(),input));
    const auto depth=OpenCvDepthSource().load(path.string());
    ASSERT_EQ(depth.width,2u); ASSERT_EQ(depth.height,3u);
    ASSERT_EQ(depth.intensity.size(),6u);
    for(std::size_t i=0;i<6;++i) EXPECT_FLOAT_EQ(depth.intensity[i],values[i]/255.f);
    const auto points=ProjectionService(OpenCvDepthSource()).from_file(path.string(),5);
    ASSERT_EQ(points.size(),6u);
    EXPECT_FLOAT_EQ(points[5].x,1); EXPECT_FLOAT_EQ(points[5].y,2); EXPECT_FLOAT_EQ(points[5].z,4);
}
TEST(OpenCvAdapter, EmptyAndCorruptFilesReject) {
    const TempImages files;
    const auto empty=files.path/"empty.png", corrupt=files.path/"corrupt.png";
    {std::ofstream out(empty);}
    {std::ofstream out(corrupt);out<<"not an image";}
    EXPECT_THROW(OpenCvDepthSource().load(empty.string()),std::runtime_error);
    EXPECT_THROW(OpenCvDepthSource().load(corrupt.string()),std::runtime_error);
}

TEST(OpenCvPixels, RedPixelDetectedByHueStartRange) {
    cv::Mat red(1,1,CV_8UC3,cv::Scalar(0,0,255));
    cv::Mat hsv; cv::cvtColor(red,hsv,cv::COLOR_BGR2HSV);
    cv::Mat mask; cv::inRange(hsv,cv::Scalar(0,70,70),cv::Scalar(10,255,255),mask);
    EXPECT_EQ(mask.at<std::uint8_t>(0,0),255);
}
TEST(OpenCvPixels, OtsuBinarySeparatesKnownLightRectangle) {
    cv::Mat gray(8,8,CV_8UC1,cv::Scalar(0));
    gray(cv::Rect(2,2,4,4)).setTo(cv::Scalar(255));
    cv::Mat binary;
    cv::threshold(gray,binary,0,255,cv::THRESH_BINARY|cv::THRESH_OTSU);
    EXPECT_EQ(cv::countNonZero(binary),16);
}
