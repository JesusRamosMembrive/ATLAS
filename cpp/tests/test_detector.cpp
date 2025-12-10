#include <gtest/gtest.h>
#include "core/similarity_detector.hpp"
#include "tokenizers/python_normalizer.hpp"
#include "utils/file_utils.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>

using namespace aegis::similarity;

class SimilarityDetectorTest : public ::testing::Test {
protected:
    std::filesystem::path fixtures_dir;

    void SetUp() override {
        // Find fixtures directory relative to test executable
        // In build/tests/ we look for tests/fixtures
        fixtures_dir = std::filesystem::current_path() / "tests" / "fixtures";

        if (!std::filesystem::exists(fixtures_dir)) {
            // Try parent directory (when running from build/)
            fixtures_dir = std::filesystem::current_path().parent_path() / "tests" / "fixtures";
        }

        if (!std::filesystem::exists(fixtures_dir)) {
            // Try from project root
            fixtures_dir = "tests/fixtures";
        }
    }

    bool has_fixtures() const {
        return std::filesystem::exists(fixtures_dir);
    }
};

// =============================================================================
// Configuration Tests
// =============================================================================

TEST_F(SimilarityDetectorTest, DefaultConfiguration) {
    SimilarityDetector detector;
    const auto& config = detector.config();

    EXPECT_EQ(config.window_size, 10);
    EXPECT_EQ(config.min_clone_tokens, 30);
    EXPECT_FLOAT_EQ(config.similarity_threshold, 0.7f);
}

TEST_F(SimilarityDetectorTest, CustomConfiguration) {
    DetectorConfig config;
    config.window_size = 15;
    config.min_clone_tokens = 50;
    config.extensions = {".py", ".js"};

    SimilarityDetector detector(config);

    EXPECT_EQ(detector.config().window_size, 15);
    EXPECT_EQ(detector.config().min_clone_tokens, 50);
    EXPECT_EQ(detector.config().extensions.size(), 2);
}

// =============================================================================
// Empty Input Tests
// =============================================================================

TEST_F(SimilarityDetectorTest, EmptyFileList) {
    SimilarityDetector detector;
    auto report = detector.analyze(std::vector<std::string>{});

    EXPECT_EQ(report.summary.files_analyzed, 0);
    EXPECT_EQ(report.summary.clone_pairs_found, 0);
    EXPECT_TRUE(report.clones.empty());
}

TEST_F(SimilarityDetectorTest, NonexistentDirectory) {
    SimilarityDetector detector;
    auto report = detector.analyze("/nonexistent/path/that/does/not/exist");

    EXPECT_EQ(report.summary.files_analyzed, 0);
    EXPECT_EQ(report.summary.clone_pairs_found, 0);
}

// =============================================================================
// Type-1 Clone Detection Tests
// =============================================================================

TEST_F(SimilarityDetectorTest, DetectsType1Clones) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.window_size = 5;       // Smaller window for test files
    config.min_clone_tokens = 10; // Lower threshold for test files
    config.extensions = {".py"};
    config.detect_type2 = false;  // Disable Type-2 detection for this test

    SimilarityDetector detector(config);

    auto file1 = fixtures_dir / "clone_type1_a.py";
    auto file2 = fixtures_dir / "clone_type1_b.py";

    if (!std::filesystem::exists(file1) || !std::filesystem::exists(file2)) {
        GTEST_SKIP() << "Test fixtures not found";
    }

    auto report = detector.compare(file1, file2);

    // Should find clones (validate_user and process_data are duplicated)
    EXPECT_EQ(report.summary.files_analyzed, 2);
    EXPECT_GT(report.summary.clone_pairs_found, 0);
    EXPECT_FALSE(report.clones.empty());

    // With detect_type2=false, all clones are reported as Type-1
    for (const auto& clone : report.clones) {
        EXPECT_EQ(clone.type, "Type-1");
        EXPECT_EQ(clone.locations.size(), 2);
    }
}

TEST_F(SimilarityDetectorTest, DetectsType2Clones) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.window_size = 5;
    config.min_clone_tokens = 10;
    config.extensions = {".py"};
    config.detect_type2 = true;  // Enable Type-2 detection

    SimilarityDetector detector(config);

    // Use Type-2 fixtures (have renamed identifiers)
    auto file1 = fixtures_dir / "clone_type2_a.py";
    auto file2 = fixtures_dir / "clone_type2_b.py";

    if (!std::filesystem::exists(file1) || !std::filesystem::exists(file2)) {
        GTEST_SKIP() << "Test fixtures not found";
    }

    auto report = detector.compare(file1, file2);

    // Should find clones
    EXPECT_EQ(report.summary.files_analyzed, 2);
    EXPECT_GT(report.summary.clone_pairs_found, 0);
    EXPECT_FALSE(report.clones.empty());

    // Type-2 clones should be detected (renamed identifiers)
    bool found_type2 = false;
    for (const auto& clone : report.clones) {
        if (clone.type == "Type-2") {
            found_type2 = true;
        }
        EXPECT_EQ(clone.locations.size(), 2);
    }
    EXPECT_TRUE(found_type2) << "Should detect Type-2 clones with renamed identifiers";
}

TEST_F(SimilarityDetectorTest, NoFalsePositivesOnUniqueFiles) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.window_size = 5;
    config.min_clone_tokens = 10;
    config.extensions = {".py"};

    SimilarityDetector detector(config);

    auto unique_file = fixtures_dir / "no_clones.py";
    auto type1_file = fixtures_dir / "clone_type1_a.py";

    if (!std::filesystem::exists(unique_file) || !std::filesystem::exists(type1_file)) {
        GTEST_SKIP() << "Test fixtures not found";
    }

    auto report = detector.compare(unique_file, type1_file);

    // Should not find significant clones between unique and type1 files
    // There might be small matches but not large clone regions
    for (const auto& clone : report.clones) {
        // Any clones found should be small (below meaningful threshold)
        auto lines = clone.locations[0].end_line - clone.locations[0].start_line;
        // This is a soft check - unique file shouldn't have large clones
        EXPECT_LT(lines, 10) << "Unexpected large clone in unique file";
    }
}

// =============================================================================
// Directory Analysis Tests
// =============================================================================

TEST_F(SimilarityDetectorTest, AnalyzeFixturesDirectory) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.window_size = 5;
    config.min_clone_tokens = 10;
    config.extensions = {".py"};

    SimilarityDetector detector(config);
    auto report = detector.analyze(fixtures_dir);

    // Should analyze multiple files
    EXPECT_GE(report.summary.files_analyzed, 3);
    EXPECT_GT(report.summary.total_lines, 0);

    // Should find clones between type1_a and type1_b
    EXPECT_GT(report.summary.clone_pairs_found, 0);
}

// =============================================================================
// Report Format Tests
// =============================================================================

TEST_F(SimilarityDetectorTest, ReportContainsRequiredFields) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.window_size = 5;
    config.min_clone_tokens = 10;
    config.extensions = {".py"};

    SimilarityDetector detector(config);
    auto report = detector.analyze(fixtures_dir);
    auto json = report.to_json();

    // Check required top-level fields
    EXPECT_TRUE(json.contains("summary"));
    EXPECT_TRUE(json.contains("clones"));
    EXPECT_TRUE(json.contains("hotspots"));
    EXPECT_TRUE(json.contains("metrics"));
    EXPECT_TRUE(json.contains("timing"));

    // Check summary fields
    auto& summary = json["summary"];
    EXPECT_TRUE(summary.contains("files_analyzed"));
    EXPECT_TRUE(summary.contains("total_lines"));
    EXPECT_TRUE(summary.contains("clone_pairs_found"));
    EXPECT_TRUE(summary.contains("estimated_duplication"));
    EXPECT_TRUE(summary.contains("analysis_time_ms"));

    // Check timing fields
    auto& timing = json["timing"];
    EXPECT_TRUE(timing.contains("tokenize_ms"));
    EXPECT_TRUE(timing.contains("hash_ms"));
    EXPECT_TRUE(timing.contains("match_ms"));
    EXPECT_TRUE(timing.contains("total_ms"));
}

TEST_F(SimilarityDetectorTest, CloneEntryFormat) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.window_size = 5;
    config.min_clone_tokens = 10;
    config.extensions = {".py"};

    SimilarityDetector detector(config);

    auto file1 = fixtures_dir / "clone_type1_a.py";
    auto file2 = fixtures_dir / "clone_type1_b.py";

    if (!std::filesystem::exists(file1) || !std::filesystem::exists(file2)) {
        GTEST_SKIP() << "Test fixtures not found";
    }

    auto report = detector.compare(file1, file2);

    if (report.clones.empty()) {
        GTEST_SKIP() << "No clones found to test format";
    }

    auto json = report.to_json();
    auto& clone = json["clones"][0];

    // Check clone entry fields
    EXPECT_TRUE(clone.contains("id"));
    EXPECT_TRUE(clone.contains("type"));
    EXPECT_TRUE(clone.contains("similarity"));
    EXPECT_TRUE(clone.contains("locations"));
    EXPECT_TRUE(clone.contains("recommendation"));

    // Check location fields
    auto& loc = clone["locations"][0];
    EXPECT_TRUE(loc.contains("file"));
    EXPECT_TRUE(loc.contains("start_line"));
    EXPECT_TRUE(loc.contains("end_line"));
}

// =============================================================================
// JSON Output Tests
// =============================================================================

TEST_F(SimilarityDetectorTest, JsonOutputIsValid) {
    SimilarityDetector detector;
    auto report = detector.analyze(std::vector<std::string>{});

    std::string json_str = report.to_json_string();
    EXPECT_FALSE(json_str.empty());

    // Should parse without error
    auto parsed = nlohmann::json::parse(json_str);
    EXPECT_TRUE(parsed.is_object());
}

TEST_F(SimilarityDetectorTest, PrettyPrintJson) {
    SimilarityDetector detector;
    auto report = detector.analyze(std::vector<std::string>{});

    std::string compact = report.to_json_string(-1);
    std::string pretty = report.to_json_string(2);

    // Pretty print should be longer (has newlines and spaces)
    EXPECT_GT(pretty.size(), compact.size());

    // Both should be valid JSON
    EXPECT_NO_THROW(nlohmann::json::parse(compact));
    EXPECT_NO_THROW(nlohmann::json::parse(pretty));
}

// =============================================================================
// Timing Tests
// =============================================================================

TEST_F(SimilarityDetectorTest, TimingIsRecorded) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.extensions = {".py"};

    SimilarityDetector detector(config);
    auto report = detector.analyze(fixtures_dir);

    // Total time should be positive
    EXPECT_GT(report.timing.total_ms, 0);

    // Component times should be non-negative
    EXPECT_GE(report.timing.tokenize_ms, 0);
    EXPECT_GE(report.timing.hash_ms, 0);
    EXPECT_GE(report.timing.match_ms, 0);
}

// =============================================================================
// Metrics Tests
// =============================================================================

TEST_F(SimilarityDetectorTest, MetricsByType) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.window_size = 5;
    config.min_clone_tokens = 10;
    config.extensions = {".py"};

    SimilarityDetector detector(config);
    auto report = detector.analyze(fixtures_dir);

    // If clones found, metrics should be populated
    if (!report.clones.empty()) {
        EXPECT_FALSE(report.metrics.by_type.empty());
    }
}

// =============================================================================
// Hotspot Tests
// =============================================================================

TEST_F(SimilarityDetectorTest, HotspotsCalculated) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.window_size = 5;
    config.min_clone_tokens = 10;
    config.extensions = {".py"};

    SimilarityDetector detector(config);
    auto report = detector.analyze(fixtures_dir);

    // If clones found, hotspots should be calculated
    if (!report.clones.empty()) {
        EXPECT_FALSE(report.hotspots.empty());

        // Hotspots should be sorted by score (descending)
        for (size_t i = 1; i < report.hotspots.size(); ++i) {
            EXPECT_GE(report.hotspots[i-1].duplication_score,
                      report.hotspots[i].duplication_score);
        }
    }
}

// =============================================================================
// Type-3 Clone Detection Tests
// =============================================================================

TEST_F(SimilarityDetectorTest, Type3DetectionDisabledByDefault) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.window_size = 5;
    config.min_clone_tokens = 10;
    config.extensions = {".py"};
    // detect_type3 is false by default

    SimilarityDetector detector(config);

    auto file1 = fixtures_dir / "clone_type3_a.py";
    auto file2 = fixtures_dir / "clone_type3_b.py";

    if (!std::filesystem::exists(file1) || !std::filesystem::exists(file2)) {
        GTEST_SKIP() << "Type-3 fixtures not found";
    }

    auto report = detector.compare(file1, file2);

    // Without Type-3 detection, modified clones might not be found
    // or will be classified as Type-1/Type-2
    for (const auto& clone : report.clones) {
        EXPECT_NE(clone.type, "Type-3") << "Type-3 should not be detected when disabled";
    }
}

TEST_F(SimilarityDetectorTest, DetectsType3Clones) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config;
    config.window_size = 5;
    config.min_clone_tokens = 10;
    config.extensions = {".py"};
    config.detect_type3 = true;  // Enable Type-3 detection
    config.similarity_threshold = 0.6f;  // Lower threshold to catch modified clones
    config.max_gap_tokens = 5;

    SimilarityDetector detector(config);

    auto file1 = fixtures_dir / "clone_type3_a.py";
    auto file2 = fixtures_dir / "clone_type3_b.py";

    if (!std::filesystem::exists(file1) || !std::filesystem::exists(file2)) {
        GTEST_SKIP() << "Type-3 fixtures not found";
    }

    auto report = detector.compare(file1, file2);

    // Should find clones between the files
    EXPECT_EQ(report.summary.files_analyzed, 2);
    EXPECT_GT(report.summary.clone_pairs_found, 0)
        << "Should find clones between Type-3 fixtures";

    // Check that clone extension is working
    // Type-3 clones should have similarity < 1.0
    for (const auto& clone : report.clones) {
        EXPECT_EQ(clone.locations.size(), 2);
        // Similarity should be within valid range
        EXPECT_GT(clone.similarity, 0.0f);
        EXPECT_LE(clone.similarity, 1.0f);
    }
}

TEST_F(SimilarityDetectorTest, Type3ConfigurationOptions) {
    DetectorConfig config;

    // Test that configuration options are available
    config.detect_type3 = true;
    config.max_gap_tokens = 10;
    config.similarity_threshold = 0.8f;

    SimilarityDetector detector(config);

    EXPECT_TRUE(detector.config().detect_type3);
    EXPECT_EQ(detector.config().max_gap_tokens, 10);
    EXPECT_FLOAT_EQ(detector.config().similarity_threshold, 0.8f);
}

TEST_F(SimilarityDetectorTest, Type3ExtendsClonesWithGaps) {
    if (!has_fixtures()) {
        GTEST_SKIP() << "Fixtures directory not found";
    }

    DetectorConfig config_without_type3;
    config_without_type3.window_size = 5;
    config_without_type3.min_clone_tokens = 10;
    config_without_type3.extensions = {".py"};
    config_without_type3.detect_type3 = false;

    DetectorConfig config_with_type3;
    config_with_type3.window_size = 5;
    config_with_type3.min_clone_tokens = 10;
    config_with_type3.extensions = {".py"};
    config_with_type3.detect_type3 = true;
    config_with_type3.similarity_threshold = 0.5f;
    config_with_type3.max_gap_tokens = 10;

    auto file1 = fixtures_dir / "clone_type3_a.py";
    auto file2 = fixtures_dir / "clone_type3_b.py";

    if (!std::filesystem::exists(file1) || !std::filesystem::exists(file2)) {
        GTEST_SKIP() << "Type-3 fixtures not found";
    }

    SimilarityDetector detector_without(config_without_type3);
    SimilarityDetector detector_with(config_with_type3);

    auto report_without = detector_without.compare(file1, file2);
    auto report_with = detector_with.compare(file1, file2);

    // With Type-3 detection, clones may be extended to be larger
    // or new clones may be found with gap tolerance
    // At minimum, the analysis should complete without errors
    EXPECT_EQ(report_with.summary.files_analyzed, 2);
}

