#include <gtest/gtest.h>
#include "core/hash_index.hpp"
#include "core/rolling_hash.hpp"
#include <chrono>
#include <iomanip>
#include <iostream>

using namespace aegis::similarity;

class HashIndexTest : public ::testing::Test {
protected:
    HashIndex index;
};

// =============================================================================
// File Registration Tests
// =============================================================================

TEST_F(HashIndexTest, RegisterFileReturnsUniqueIds) {
    auto id1 = index.register_file("/path/to/file1.py");
    auto id2 = index.register_file("/path/to/file2.py");
    auto id3 = index.register_file("/path/to/file3.py");

    EXPECT_EQ(id1, 0);
    EXPECT_EQ(id2, 1);
    EXPECT_EQ(id3, 2);
    EXPECT_EQ(index.file_count(), 3);
}

TEST_F(HashIndexTest, RegisterSameFileReturnsSameId) {
    auto id1 = index.register_file("/path/to/file.py");
    auto id2 = index.register_file("/path/to/file.py");

    EXPECT_EQ(id1, id2);
    EXPECT_EQ(index.file_count(), 1);
}

TEST_F(HashIndexTest, GetFilePath) {
    index.register_file("/path/to/file1.py");
    index.register_file("/path/to/file2.py");

    EXPECT_EQ(index.get_file_path(0), "/path/to/file1.py");
    EXPECT_EQ(index.get_file_path(1), "/path/to/file2.py");
    EXPECT_EQ(index.get_file_path(999), "");  // Invalid ID
}

// =============================================================================
// Hash Storage Tests
// =============================================================================

TEST_F(HashIndexTest, AddAndRetrieveHash) {
    HashLocation loc{0, 10, 15, 0, 50, 0, 10};
    index.add_hash(12345, loc);

    auto* locations = index.get_locations(12345);
    ASSERT_NE(locations, nullptr);
    ASSERT_EQ(locations->size(), 1);
    EXPECT_EQ((*locations)[0].file_id, 0);
    EXPECT_EQ((*locations)[0].start_line, 10);
}

TEST_F(HashIndexTest, MultipleLocationsPerHash) {
    HashLocation loc1{0, 10, 15, 0, 50, 0, 10};
    HashLocation loc2{1, 20, 25, 0, 50, 100, 10};
    HashLocation loc3{2, 30, 35, 0, 50, 200, 10};

    index.add_hash(12345, loc1);
    index.add_hash(12345, loc2);
    index.add_hash(12345, loc3);

    auto* locations = index.get_locations(12345);
    ASSERT_NE(locations, nullptr);
    EXPECT_EQ(locations->size(), 3);
}

TEST_F(HashIndexTest, NonexistentHashReturnsNull) {
    EXPECT_EQ(index.get_locations(99999), nullptr);
}

TEST_F(HashIndexTest, ClearRemovesAllData) {
    index.register_file("file.py");
    HashLocation loc{0, 10, 15, 0, 50, 0, 10};
    index.add_hash(12345, loc);

    index.clear();

    EXPECT_EQ(index.file_count(), 0);
    EXPECT_EQ(index.hash_count(), 0);
    EXPECT_EQ(index.get_locations(12345), nullptr);
}

// =============================================================================
// Clone Pair Detection Tests
// =============================================================================

TEST_F(HashIndexTest, FindClonePairsEmpty) {
    auto pairs = index.find_clone_pairs();
    EXPECT_TRUE(pairs.empty());
}

TEST_F(HashIndexTest, FindClonePairsSingleLocation) {
    HashLocation loc{0, 10, 15, 0, 50, 0, 10};
    index.add_hash(12345, loc);

    auto pairs = index.find_clone_pairs();
    EXPECT_TRUE(pairs.empty());  // Need at least 2 locations
}

TEST_F(HashIndexTest, FindClonePairsTwoLocations) {
    index.register_file("file1.py");
    index.register_file("file2.py");

    HashLocation loc1{0, 10, 15, 0, 50, 0, 10};
    HashLocation loc2{1, 20, 25, 0, 50, 0, 10};

    index.add_hash(12345, loc1);
    index.add_hash(12345, loc2);

    auto pairs = index.find_clone_pairs();
    ASSERT_EQ(pairs.size(), 1);
    EXPECT_EQ(pairs[0].location_a.file_id, 0);
    EXPECT_EQ(pairs[0].location_b.file_id, 1);
    EXPECT_EQ(pairs[0].shared_hash, 12345);
}

TEST_F(HashIndexTest, FindClonePairsSkipsOverlapping) {
    index.register_file("file.py");

    // Two overlapping locations in same file
    HashLocation loc1{0, 10, 15, 0, 50, 0, 10};
    HashLocation loc2{0, 12, 17, 0, 50, 5, 10};  // Overlaps with loc1

    index.add_hash(12345, loc1);
    index.add_hash(12345, loc2);

    auto pairs = index.find_clone_pairs();
    EXPECT_TRUE(pairs.empty());  // Should skip overlapping
}

TEST_F(HashIndexTest, FindClonePairsNonOverlappingSameFile) {
    index.register_file("file.py");

    // Two non-overlapping locations in same file
    HashLocation loc1{0, 10, 15, 0, 50, 0, 10};
    HashLocation loc2{0, 100, 105, 0, 50, 500, 10};  // Far apart

    index.add_hash(12345, loc1);
    index.add_hash(12345, loc2);

    auto pairs = index.find_clone_pairs();
    ASSERT_EQ(pairs.size(), 1);  // Should find the pair
}

TEST_F(HashIndexTest, FindClonePairsMultipleHashes) {
    index.register_file("file1.py");
    index.register_file("file2.py");

    // Hash A appears in both files
    HashLocation loc1a{0, 10, 15, 0, 50, 0, 10};
    HashLocation loc2a{1, 20, 25, 0, 50, 0, 10};
    index.add_hash(111, loc1a);
    index.add_hash(111, loc2a);

    // Hash B also appears in both files
    HashLocation loc1b{0, 50, 55, 0, 50, 100, 10};
    HashLocation loc2b{1, 60, 65, 0, 50, 100, 10};
    index.add_hash(222, loc1b);
    index.add_hash(222, loc2b);

    auto pairs = index.find_clone_pairs();
    EXPECT_EQ(pairs.size(), 2);  // One pair per hash
}

// =============================================================================
// Merge Adjacent Clones Tests
// =============================================================================

TEST_F(HashIndexTest, MergeAdjacentClonesEmpty) {
    std::vector<ClonePair> empty;
    auto merged = HashIndex::merge_adjacent_clones(empty);
    EXPECT_TRUE(merged.empty());
}

TEST_F(HashIndexTest, MergeAdjacentClonesSinglePair) {
    ClonePair pair;
    pair.location_a = {0, 10, 15, 0, 50, 0, 10};
    pair.location_b = {1, 20, 25, 0, 50, 0, 10};

    std::vector<ClonePair> pairs = {pair};
    auto merged = HashIndex::merge_adjacent_clones(pairs);

    EXPECT_EQ(merged.size(), 1);
}

TEST_F(HashIndexTest, MergeAdjacentClonesAdjacentPairs) {
    ClonePair pair1;
    pair1.location_a = {0, 10, 12, 0, 50, 0, 5};
    pair1.location_b = {1, 20, 22, 0, 50, 0, 5};

    ClonePair pair2;
    pair2.location_a = {0, 13, 15, 0, 50, 5, 5};  // Adjacent in file 0
    pair2.location_b = {1, 23, 25, 0, 50, 5, 5};  // Adjacent in file 1

    std::vector<ClonePair> pairs = {pair1, pair2};
    auto merged = HashIndex::merge_adjacent_clones(pairs);

    EXPECT_EQ(merged.size(), 1);  // Should merge into one
    EXPECT_EQ(merged[0].location_a.token_count, 10);  // Combined size
}

TEST_F(HashIndexTest, MergeAdjacentClonesNonAdjacent) {
    ClonePair pair1;
    pair1.location_a = {0, 10, 15, 0, 50, 0, 10};
    pair1.location_b = {1, 20, 25, 0, 50, 0, 10};

    ClonePair pair2;
    pair2.location_a = {0, 100, 105, 0, 50, 500, 10};  // Far from pair1
    pair2.location_b = {1, 200, 205, 0, 50, 500, 10};

    std::vector<ClonePair> pairs = {pair1, pair2};
    auto merged = HashIndex::merge_adjacent_clones(pairs);

    EXPECT_EQ(merged.size(), 2);  // Should not merge
}

TEST_F(HashIndexTest, MergeAdjacentClonesDifferentFiles) {
    ClonePair pair1;
    pair1.location_a = {0, 10, 15, 0, 50, 0, 10};
    pair1.location_b = {1, 20, 25, 0, 50, 0, 10};

    ClonePair pair2;
    pair2.location_a = {0, 16, 20, 0, 50, 10, 10};  // Adjacent to pair1
    pair2.location_b = {2, 30, 35, 0, 50, 0, 10};   // Different file!

    std::vector<ClonePair> pairs = {pair1, pair2};
    auto merged = HashIndex::merge_adjacent_clones(pairs);

    EXPECT_EQ(merged.size(), 2);  // Should not merge (different file pairs)
}

// =============================================================================
// Filter By Size Tests
// =============================================================================

TEST_F(HashIndexTest, FilterBySizeRemovesSmall) {
    ClonePair small;
    small.location_a = {0, 10, 12, 0, 50, 0, 5};
    small.location_b = {1, 20, 22, 0, 50, 0, 5};

    ClonePair large;
    large.location_a = {0, 100, 120, 0, 50, 500, 50};
    large.location_b = {1, 200, 220, 0, 50, 500, 50};

    std::vector<ClonePair> pairs = {small, large};
    auto filtered = HashIndex::filter_by_size(pairs, 30);

    ASSERT_EQ(filtered.size(), 1);
    EXPECT_EQ(filtered[0].token_count(), 50);
}

TEST_F(HashIndexTest, FilterBySizeKeepsAll) {
    ClonePair pair;
    pair.location_a = {0, 10, 20, 0, 50, 0, 50};
    pair.location_b = {1, 20, 30, 0, 50, 0, 50};

    std::vector<ClonePair> pairs = {pair};
    auto filtered = HashIndex::filter_by_size(pairs, 10);

    EXPECT_EQ(filtered.size(), 1);
}

// =============================================================================
// Stats Tests
// =============================================================================

TEST_F(HashIndexTest, GetStatsEmpty) {
    auto stats = index.get_stats();

    EXPECT_EQ(stats.total_files, 0);
    EXPECT_EQ(stats.total_hashes, 0);
    EXPECT_EQ(stats.total_locations, 0);
    EXPECT_EQ(stats.duplicate_hashes, 0);
}

TEST_F(HashIndexTest, GetStatsWithData) {
    index.register_file("file1.py");
    index.register_file("file2.py");

    // Hash with multiple locations (duplicate)
    HashLocation loc1{0, 10, 15, 0, 50, 0, 10};
    HashLocation loc2{1, 20, 25, 0, 50, 0, 10};
    index.add_hash(111, loc1);
    index.add_hash(111, loc2);

    // Hash with single location
    HashLocation loc3{0, 50, 55, 0, 50, 100, 10};
    index.add_hash(222, loc3);

    auto stats = index.get_stats();

    EXPECT_EQ(stats.total_files, 2);
    EXPECT_EQ(stats.total_hashes, 2);
    EXPECT_EQ(stats.total_locations, 3);
    EXPECT_EQ(stats.duplicate_hashes, 1);
    EXPECT_EQ(stats.max_locations_per_hash, 2);
}

// =============================================================================
// HashIndexBuilder Tests
// =============================================================================

TEST(HashIndexBuilderTest, BuildFromTokenizedFile) {
    // Create a simple tokenized file
    TokenizedFile file;
    file.path = "test.py";

    // Add enough tokens to generate windows
    for (int i = 0; i < 20; ++i) {
        NormalizedToken tok;
        tok.type = TokenType::IDENTIFIER;
        tok.original_hash = static_cast<uint32_t>(i * 100);
        tok.normalized_hash = 999;  // All normalized to same
        tok.line = static_cast<uint32_t>(i + 1);
        tok.column = 1;
        tok.length = 3;
        file.tokens.push_back(tok);
    }

    HashIndexBuilder builder(5);  // Window size 5
    builder.add_file(file, true);

    const auto& index = builder.index();

    EXPECT_EQ(index.file_count(), 1);
    EXPECT_GT(index.hash_count(), 0);
}

TEST(HashIndexBuilderTest, SkipsStructuralTokens) {
    TokenizedFile file;
    file.path = "test.py";

    // Mix of regular and structural tokens
    for (int i = 0; i < 15; ++i) {
        NormalizedToken tok;

        if (i % 3 == 0) {
            tok.type = TokenType::NEWLINE;  // Should be skipped
        } else {
            tok.type = TokenType::IDENTIFIER;
        }

        tok.original_hash = static_cast<uint32_t>(i * 100);
        tok.normalized_hash = static_cast<uint32_t>(i * 100);
        tok.line = static_cast<uint32_t>(i + 1);
        tok.column = 1;
        tok.length = 3;
        file.tokens.push_back(tok);
    }

    HashIndexBuilder builder(5);
    builder.add_file(file, false);

    // Should have processed non-structural tokens
    EXPECT_GT(builder.index().hash_count(), 0);
}

TEST(HashIndexBuilderTest, SmallFilesIgnored) {
    TokenizedFile file;
    file.path = "tiny.py";

    // Only 3 tokens, window size is 5
    for (int i = 0; i < 3; ++i) {
        NormalizedToken tok;
        tok.type = TokenType::IDENTIFIER;
        tok.original_hash = static_cast<uint32_t>(i);
        tok.normalized_hash = static_cast<uint32_t>(i);
        tok.line = 1;
        tok.column = static_cast<uint16_t>(i);
        tok.length = 1;
        file.tokens.push_back(tok);
    }

    HashIndexBuilder builder(5);
    builder.add_file(file, true);

    EXPECT_EQ(builder.index().hash_count(), 0);
}

// =============================================================================
// Parallel Clone Pair Detection Tests
// =============================================================================

TEST(HashIndexParallelTest, ParallelFindClonePairsMatchesSequential) {
    // Build an index with many duplicate hashes
    HashIndex index;
    uint32_t file1 = index.register_file("file1.py");
    uint32_t file2 = index.register_file("file2.py");
    uint32_t file3 = index.register_file("file3.py");

    // Add multiple locations for the same hash across files
    for (uint64_t hash = 1000; hash < 1100; ++hash) {
        for (uint32_t file_id : {file1, file2, file3}) {
            HashLocation loc;
            loc.file_id = file_id;
            loc.token_start = static_cast<uint32_t>((hash - 1000) * 10);
            loc.token_count = 10;
            loc.start_line = static_cast<uint32_t>(hash - 1000 + 1);
            loc.end_line = loc.start_line + 5;
            index.add_hash(hash, loc);
        }
    }

    ThreadPool pool(4);

    // Run both versions
    auto sequential_pairs = index.find_clone_pairs();
    auto parallel_pairs = index.find_clone_pairs_parallel(pool);

    // Should find the same number of clone pairs
    EXPECT_EQ(sequential_pairs.size(), parallel_pairs.size());

    // Both should find pairs (100 hashes * 3 locations each = 100 * C(3,2) = 300 pairs)
    EXPECT_EQ(sequential_pairs.size(), 300);
}

TEST(HashIndexParallelTest, ParallelWithSmallWorkloadFallsBackToSequential) {
    // With fewer than 100 work items, parallel should use sequential
    HashIndex index;
    uint32_t file1 = index.register_file("file1.py");
    uint32_t file2 = index.register_file("file2.py");

    // Add just 50 duplicate hashes (below threshold)
    for (uint64_t hash = 1000; hash < 1050; ++hash) {
        for (uint32_t file_id : {file1, file2}) {
            HashLocation loc;
            loc.file_id = file_id;
            loc.token_start = static_cast<uint32_t>((hash - 1000) * 10);
            loc.token_count = 10;
            loc.start_line = 1;
            loc.end_line = 5;
            index.add_hash(hash, loc);
        }
    }

    ThreadPool pool(4);

    auto sequential_pairs = index.find_clone_pairs();
    auto parallel_pairs = index.find_clone_pairs_parallel(pool);

    // Results should be identical
    EXPECT_EQ(sequential_pairs.size(), parallel_pairs.size());
    EXPECT_EQ(sequential_pairs.size(), 50);  // 50 hashes * 1 pair each
}

TEST(HashIndexParallelTest, ParallelWithSingleThreadFallsBackToSequential) {
    // With single thread pool, parallel should use sequential
    HashIndex index;
    uint32_t file1 = index.register_file("file1.py");
    uint32_t file2 = index.register_file("file2.py");

    // Add enough hashes to trigger parallel (>100)
    for (uint64_t hash = 1000; hash < 1200; ++hash) {
        for (uint32_t file_id : {file1, file2}) {
            HashLocation loc;
            loc.file_id = file_id;
            loc.token_start = static_cast<uint32_t>((hash - 1000) * 10);
            loc.token_count = 10;
            loc.start_line = 1;
            loc.end_line = 5;
            index.add_hash(hash, loc);
        }
    }

    ThreadPool pool(1);  // Single thread

    auto sequential_pairs = index.find_clone_pairs();
    auto parallel_pairs = index.find_clone_pairs_parallel(pool);

    // Results should be identical
    EXPECT_EQ(sequential_pairs.size(), parallel_pairs.size());
}

TEST(HashIndexParallelTest, ParallelHandlesLargeWorkload) {
    // Stress test with many hashes and locations
    HashIndex index;
    std::vector<uint32_t> files;
    for (int i = 0; i < 10; ++i) {
        files.push_back(index.register_file("file" + std::to_string(i) + ".py"));
    }

    // Add 500 hashes with locations in multiple files
    for (uint64_t hash = 1000; hash < 1500; ++hash) {
        // Each hash appears in 5 random files
        for (int i = 0; i < 5; ++i) {
            HashLocation loc;
            loc.file_id = files[i * 2];
            loc.token_start = static_cast<uint32_t>((hash - 1000) * 10 + i);
            loc.token_count = 10;
            loc.start_line = static_cast<uint32_t>(i + 1);
            loc.end_line = loc.start_line + 5;
            index.add_hash(hash, loc);
        }
    }

    ThreadPool pool(4);

    auto sequential_pairs = index.find_clone_pairs();
    auto parallel_pairs = index.find_clone_pairs_parallel(pool);

    // Results should match
    EXPECT_EQ(sequential_pairs.size(), parallel_pairs.size());

    // Should find 500 hashes * C(5,2) = 500 * 10 = 5000 pairs
    EXPECT_EQ(sequential_pairs.size(), 5000);
}

TEST(HashIndexParallelTest, ParallelPreservesClonePairFields) {
    HashIndex index;
    uint32_t file1 = index.register_file("test1.py");
    uint32_t file2 = index.register_file("test2.py");

    // Add locations with specific values
    HashLocation loc1;
    loc1.file_id = file1;
    loc1.token_start = 100;
    loc1.token_count = 50;
    loc1.start_line = 10;
    loc1.end_line = 20;

    HashLocation loc2;
    loc2.file_id = file2;
    loc2.token_start = 200;
    loc2.token_count = 50;
    loc2.start_line = 30;
    loc2.end_line = 40;

    // Add to 200+ hashes to trigger parallel mode
    for (uint64_t hash = 1000; hash < 1200; ++hash) {
        index.add_hash(hash, loc1);
        index.add_hash(hash, loc2);
    }

    ThreadPool pool(4);
    auto parallel_pairs = index.find_clone_pairs_parallel(pool);

    EXPECT_EQ(parallel_pairs.size(), 200);

    // All pairs should have correct values
    for (const auto& pair : parallel_pairs) {
        EXPECT_EQ(pair.clone_type, CloneType::TYPE_1);
        EXPECT_FLOAT_EQ(pair.similarity, 1.0f);
        EXPECT_GE(pair.shared_hash, 1000);
        EXPECT_LT(pair.shared_hash, 1200);
    }
}

TEST(HashIndexParallelTest, ParallelExcludesOverlappingSameFile) {
    HashIndex index;
    uint32_t file1 = index.register_file("test.py");

    // Add overlapping locations in the same file
    HashLocation loc1;
    loc1.file_id = file1;
    loc1.token_start = 0;
    loc1.token_count = 20;
    loc1.start_line = 1;
    loc1.end_line = 10;

    HashLocation loc2;
    loc2.file_id = file1;
    loc2.token_start = 10;  // Overlaps with loc1
    loc2.token_count = 20;
    loc2.start_line = 5;
    loc2.end_line = 15;

    // Add non-overlapping location
    HashLocation loc3;
    loc3.file_id = file1;
    loc3.token_start = 100;  // No overlap
    loc3.token_count = 20;
    loc3.start_line = 50;
    loc3.end_line = 60;

    // Add to 200+ hashes to trigger parallel mode
    for (uint64_t hash = 1000; hash < 1200; ++hash) {
        index.add_hash(hash, loc1);
        index.add_hash(hash, loc2);
        index.add_hash(hash, loc3);
    }

    ThreadPool pool(4);
    auto parallel_pairs = index.find_clone_pairs_parallel(pool);

    // Should exclude overlapping pairs (loc1-loc2)
    // Only non-overlapping pairs: loc1-loc3, loc2-loc3
    // 200 hashes * 2 non-overlapping pairs = 400 pairs
    EXPECT_EQ(parallel_pairs.size(), 400);
}

// =============================================================================
// Performance Benchmark Tests
// =============================================================================

TEST(HashIndexBenchmarkTest, DISABLED_BenchmarkSequentialVsParallel) {
    // Disabled by default - enable manually for benchmarking
    // Use: ./similarity_tests --gtest_also_run_disabled_tests --gtest_filter="*Benchmark*"

    // Build a large index simulating real-world scenario
    HashIndex index;
    std::vector<uint32_t> files;
    const size_t num_files = 100;
    const size_t hashes_per_file = 2000;

    // Register files
    for (size_t i = 0; i < num_files; ++i) {
        files.push_back(index.register_file("file" + std::to_string(i) + ".py"));
    }

    // Add hashes - simulate many duplicates across files
    for (uint64_t hash = 1000; hash < 1000 + hashes_per_file; ++hash) {
        // Each hash appears in ~10 random files
        for (size_t i = 0; i < num_files; i += 5) {
            HashLocation loc;
            loc.file_id = files[i];
            loc.token_start = static_cast<uint32_t>((hash - 1000) * 20);
            loc.token_count = 15;
            loc.start_line = static_cast<uint32_t>(hash - 1000 + 1);
            loc.end_line = loc.start_line + 10;
            index.add_hash(hash, loc);
        }
    }

    auto stats = index.get_stats();
    std::cout << "\n=== Benchmark Configuration ===\n";
    std::cout << "Files: " << stats.total_files << "\n";
    std::cout << "Unique hashes: " << stats.total_hashes << "\n";
    std::cout << "Total locations: " << stats.total_locations << "\n";
    std::cout << "Duplicate hashes: " << stats.duplicate_hashes << "\n";

    // Warmup
    auto warmup = index.find_clone_pairs();

    // Benchmark sequential
    auto seq_start = std::chrono::high_resolution_clock::now();
    auto sequential_pairs = index.find_clone_pairs();
    auto seq_end = std::chrono::high_resolution_clock::now();
    auto seq_ms = std::chrono::duration_cast<std::chrono::microseconds>(seq_end - seq_start).count();

    // Benchmark parallel with different thread counts
    for (size_t threads : {2, 4, 8}) {
        ThreadPool pool(threads);

        auto par_start = std::chrono::high_resolution_clock::now();
        auto parallel_pairs = index.find_clone_pairs_parallel(pool);
        auto par_end = std::chrono::high_resolution_clock::now();
        auto par_ms = std::chrono::duration_cast<std::chrono::microseconds>(par_end - par_start).count();

        // Verify correctness
        EXPECT_EQ(sequential_pairs.size(), parallel_pairs.size());

        double speedup = static_cast<double>(seq_ms) / static_cast<double>(par_ms);
        std::cout << "\n=== " << threads << " threads ===\n";
        std::cout << "Sequential: " << seq_ms << " us\n";
        std::cout << "Parallel:   " << par_ms << " us\n";
        std::cout << "Speedup:    " << std::fixed << std::setprecision(2) << speedup << "x\n";
        std::cout << "Clone pairs found: " << parallel_pairs.size() << "\n";
    }
}
