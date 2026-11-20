#include "depth_projection.hpp"
#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>

using namespace comento;
using ::testing::Return;
using ::testing::Throw;

class MockDepthSource : public IDepthSource {
public:
    MOCK_METHOD(DepthMap, load, (const std::string& filename), (const, override));
};

TEST(Projection, BlackWhitePixelsHaveExpectedDepth) {
    const DepthMap d{2,1,{0.0f,1.0f}};
    auto pts = DepthProjection::project(d);
    ASSERT_EQ(pts.size(), 2u);
    EXPECT_FLOAT_EQ(pts[0].x, 0); EXPECT_FLOAT_EQ(pts[0].y, 0);
    EXPECT_FLOAT_EQ(pts[0].z, 0);
    EXPECT_FLOAT_EQ(pts[1].x, 1); EXPECT_FLOAT_EQ(pts[1].y, 0);
    EXPECT_FLOAT_EQ(pts[1].z, 40);
}
TEST(Projection, RowMajorCoordinatesAreNotTransposed) {
    const DepthMap d{2,3,{0,.1f,.2f,.3f,.4f,.5f}};
    const auto pts = DepthProjection::project(d,10);
    ASSERT_EQ(pts.size(),6u);
    EXPECT_FLOAT_EQ(pts[2].x,0); EXPECT_FLOAT_EQ(pts[2].y,1); EXPECT_FLOAT_EQ(pts[2].z,2);
    EXPECT_FLOAT_EQ(pts[5].x,1); EXPECT_FLOAT_EQ(pts[5].y,2); EXPECT_FLOAT_EQ(pts[5].z,5);
}
TEST(Projection, OnePixelWorks) {
    auto pts=DepthProjection::project({1,1,{0.25f}},8);
    ASSERT_EQ(pts.size(),1u); EXPECT_FLOAT_EQ(pts[0].z,2);
}
TEST(Projection, InputNotMutated) {
    DepthMap d{2,1,{.2f,.8f}};
    auto before=d.intensity;
    (void)DepthProjection::project(d);
    EXPECT_EQ(d.intensity,before);
}
TEST(Projection, RejectsMissingAndMalformedDepth) {
    EXPECT_THROW(DepthProjection::project({0,1,{}}),std::invalid_argument);
    EXPECT_THROW(DepthProjection::project({2,2,{.3f}}),std::invalid_argument);
    EXPECT_THROW(DepthProjection::project({1,1,{-.1f}}),std::invalid_argument);
    EXPECT_THROW(DepthProjection::project({1,1,{1.01f}}),std::invalid_argument);
    EXPECT_THROW(DepthProjection::project({1,1,{std::numeric_limits<float>::quiet_NaN()}}),std::invalid_argument);
    EXPECT_THROW(DepthProjection::project({1,1,{std::numeric_limits<float>::infinity()}}),std::invalid_argument);
}
TEST(Projection, RejectsInvalidScale) {
    DepthMap d{1,1,{1}};
    EXPECT_THROW(DepthProjection::project(d,0),std::invalid_argument);
    EXPECT_THROW(DepthProjection::project(d,-1),std::invalid_argument);
    EXPECT_THROW(DepthProjection::project(d,std::numeric_limits<float>::infinity()),std::invalid_argument);
    EXPECT_THROW(DepthProjection::project(d,std::numeric_limits<float>::quiet_NaN()),std::invalid_argument);
}
TEST(Projection, RejectsPointBudget) {
    EXPECT_THROW(DepthProjection::project({2,2,{0,0,0,0}},40,3),std::invalid_argument);
    EXPECT_THROW(DepthProjection::project({1,1,{.2f}},40,0),std::invalid_argument);
}
TEST(Projection, RejectsDimensionMultiplicationOverflow) {
    EXPECT_THROW(DepthProjection::project({std::numeric_limits<std::size_t>::max(),2,{}}),std::invalid_argument);
}
TEST(Sampling, SkinnyImagesNeverExceedBudget) {
    auto step=DepthProjection::sampling_step(100000,1,7000);
    EXPECT_GE(step,15u);
    EXPECT_LE((100000+step-1)/step,7000u);
    EXPECT_EQ(DepthProjection::sampling_step(512,512,7000),7u);
}
TEST(Sampling, RejectsBadBudgetAndSizes) {
    EXPECT_THROW(DepthProjection::sampling_step(0,10,100),std::invalid_argument);
    EXPECT_THROW(DepthProjection::sampling_step(10,0,100),std::invalid_argument);
    EXPECT_THROW(DepthProjection::sampling_step(10,10,0),std::invalid_argument);
}
TEST(Sampling, PreservesXAndYAndBudget) {
    DepthMap d{5,3,std::vector<float>(15,.5f)};
    auto out=DepthProjection::sample(d,10,4);
    ASSERT_LE(out.size(),4u);
    ASSERT_EQ(out.size(), 2u); // step=2 yields 6 > 4; step=3 yields 2
}
// A transposed/constant sample could satisfy the older count-only check.
TEST(Sampling, ExactSampleCoordinatesAndHeights) {
    const DepthMap d{5,4,{0,.05f,.10f,.15f,.20f,
                         .25f,.30f,.35f,.40f,.45f,
                         .50f,.55f,.60f,.65f,.70f,
                         .75f,.80f,.85f,.90f,.95f}};
    const auto out=DepthProjection::sample(d,20,4);
    const Point3D expected[]={{0,0,0},{3,0,3},{0,3,15},{3,3,18}};
    ASSERT_EQ(out.size(),4u);
    for(std::size_t i=0;i<out.size();++i) {
        EXPECT_FLOAT_EQ(out[i].x,expected[i].x);
        EXPECT_FLOAT_EQ(out[i].y,expected[i].y);
        EXPECT_FLOAT_EQ(out[i].z,expected[i].z);
    }
}
TEST(Sampling, RealLongRowAndColumnStayWithinBudget) {
    for(const bool vertical : {false,true}) {
        const DepthMap d{vertical?1u:100000u,vertical?100000u:1u,
                         std::vector<float>(100000,.5f)};
        const auto out=DepthProjection::sample(d,10,7000);
        ASSERT_EQ(out.size(),6667u);
        EXPECT_FLOAT_EQ(out.back().x,vertical?0.f:99990.f);
        EXPECT_FLOAT_EQ(out.back().y,vertical?99990.f:0.f);
        EXPECT_FLOAT_EQ(out.back().z,5.f);
    }
}
TEST(Sampling, SizeMaxDimensionsDoNotOverflowStrideSearch) {
    const auto max=std::numeric_limits<std::size_t>::max();
    EXPECT_EQ(DepthProjection::sampling_step(max,1,1),max);
    EXPECT_EQ(DepthProjection::sampling_step(1,max,1),max);
    EXPECT_EQ(DepthProjection::sampling_step(max,max,1),max);
}
TEST(Sampling, RejectsMalformedDepthAndNonfiniteValues) {
    EXPECT_THROW(DepthProjection::sample({0,1,{}},10,1),std::invalid_argument);
    EXPECT_THROW(DepthProjection::sample({2,2,{.5f}},10,1),std::invalid_argument);
    EXPECT_THROW(DepthProjection::sample({1,1,{std::numeric_limits<float>::quiet_NaN()}},10,1),std::invalid_argument);
    EXPECT_THROW(DepthProjection::sample({1,1,{1.01f}},10,1),std::invalid_argument);
}
TEST(Projection, SmallestAndLargestFiniteFloatScales) {
    for(const float scale : {std::numeric_limits<float>::denorm_min(),
                             std::numeric_limits<float>::max()}) {
        const auto out=DepthProjection::project({2,1,{0,1}},scale);
        ASSERT_EQ(out.size(),2u);
        EXPECT_FLOAT_EQ(out[0].z,0.f);
        EXPECT_FLOAT_EQ(out[1].z,scale);
        EXPECT_EQ(out[1].z,scale); // ULP tolerance alone can equate denorm_min to zero.
        EXPECT_GT(out[1].z,0.f);
        EXPECT_TRUE(std::isfinite(out[1].z));
    }
}
TEST(MockSource, LoadsExactlyOnceAndConverts) {
    MockDepthSource src;
    EXPECT_CALL(src,load("fixture.png")).Times(1).WillOnce(Return(DepthMap{1,1,{.5f}}));
    auto pts=ProjectionService(src).from_file("fixture.png",10);
    ASSERT_EQ(pts.size(),1u); EXPECT_FLOAT_EQ(pts[0].z,5);
}
TEST(MockSource, PropagatesLoadFailure) {
    MockDepthSource src;
    EXPECT_CALL(src,load("missing.png")).WillOnce(Throw(std::runtime_error("file not found")));
    EXPECT_THROW(ProjectionService(src).from_file("missing.png"),std::runtime_error);
}
TEST(MockSource, RejectsCorruptLoadedDimensions) {
    MockDepthSource src;
    EXPECT_CALL(src,load("corrupt.png")).WillOnce(Return(DepthMap{2,2,{.5f}}));
    EXPECT_THROW(ProjectionService(src).from_file("corrupt.png"),std::invalid_argument);
}
TEST(MockSource, RejectsNonfiniteLoadedIntensityAfterOneLoad) {
    MockDepthSource src;
    EXPECT_CALL(src,load("nan.png")).Times(1).WillOnce(Return(
        DepthMap{1,1,{std::numeric_limits<float>::quiet_NaN()}}));
    EXPECT_THROW(ProjectionService(src).from_file("nan.png"),std::invalid_argument);
}
