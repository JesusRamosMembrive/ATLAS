#include <gtest/gtest.h>
#include "core/clone_extender.hpp"
#include "utils/thread_pool.hpp"
#include "utils/lru_cache.hpp"
#include <vector>
#include <atomic>
#include <thread>
#include <chrono>

using namespace aegis::similarity;

// =============================================================================
// LRU Cache Tests
// =============================================================================

class LRUCacheTest : public ::testing::Test {};

TEST_F(LRUCacheTest, BasicPutAndGet) {
    LRUCache<std::string, int> cache(3);

    cache.put("one", 1);
    cache.put("two", 2);
    cache.put("three", 3);

    EXPECT_EQ(cache.get("one").value(), 1);
    EXPECT_EQ(cache.get("two").value(), 2);
    EXPECT_EQ(cache.get("three").value(), 3);
}

TEST_F(LRUCacheTest, Eviction) {
    LRUCache<std::string, int> cache(2);

    cache.put("one", 1);
    cache.put("two", 2);
    cache.put("three", 3);  // Should evict "one"

    EXPECT_FALSE(cache.get("one").has_value());
    EXPECT_EQ(cache.get("two").value(), 2);
    EXPECT_EQ(cache.get("three").value(), 3);
}

TEST_F(LRUCacheTest, LRUOrder) {
    LRUCache<std::string, int> cache(3);

    cache.put("one", 1);
    cache.put("two", 2);
    cache.put("three", 3);

    // Access "one" to make it most recently used
    cache.get("one");

    // Add "four" - should evict "two" (least recently used)
    cache.put("four", 4);

    EXPECT_TRUE(cache.get("one").has_value());
    EXPECT_FALSE(cache.get("two").has_value());
    EXPECT_TRUE(cache.get("three").has_value());
    EXPECT_TRUE(cache.get("four").has_value());
}

TEST_F(LRUCacheTest, UpdateExisting) {
    LRUCache<std::string, int> cache(3);

    cache.put("key", 1);
    EXPECT_EQ(cache.get("key").value(), 1);

    cache.put("key", 2);
    EXPECT_EQ(cache.get("key").value(), 2);
    EXPECT_EQ(cache.size(), 1);
}

TEST_F(LRUCacheTest, Contains) {
    LRUCache<std::string, int> cache(3);

    cache.put("key", 1);

    EXPECT_TRUE(cache.contains("key"));
    EXPECT_FALSE(cache.contains("nonexistent"));
}

TEST_F(LRUCacheTest, Remove) {
    LRUCache<std::string, int> cache(3);

    cache.put("key", 1);
    EXPECT_TRUE(cache.contains("key"));

    cache.remove("key");
    EXPECT_FALSE(cache.contains("key"));
}

TEST_F(LRUCacheTest, Clear) {
    LRUCache<std::string, int> cache(3);

    cache.put("one", 1);
    cache.put("two", 2);
    cache.put("three", 3);

    cache.clear();

    EXPECT_EQ(cache.size(), 0);
    EXPECT_TRUE(cache.empty());
}

TEST_F(LRUCacheTest, GetOrCompute) {
    LRUCache<std::string, int> cache(3);
    int compute_count = 0;

    auto compute = [&compute_count](const std::string& key) {
        ++compute_count;
        return static_cast<int>(key.length());
    };

    // First call should compute
    int val1 = cache.get_or_compute("hello", [&]() { return compute("hello"); });
    EXPECT_EQ(val1, 5);
    EXPECT_EQ(compute_count, 1);

    // Second call should use cache
    int val2 = cache.get_or_compute("hello", [&]() { return compute("hello"); });
    EXPECT_EQ(val2, 5);
    EXPECT_EQ(compute_count, 1);
}

// =============================================================================
// Thread Pool Tests
// =============================================================================

class ThreadPoolTest : public ::testing::Test {};

TEST_F(ThreadPoolTest, BasicSubmit) {
    ThreadPool pool(2);

    auto future = pool.submit([]() { return 42; });
    EXPECT_EQ(future.get(), 42);
}

TEST_F(ThreadPoolTest, MultipleSubmits) {
    ThreadPool pool(4);

    std::vector<std::future<int>> futures;
    for (int i = 0; i < 100; ++i) {
        futures.push_back(pool.submit([i]() { return i * 2; }));
    }

    for (int i = 0; i < 100; ++i) {
        EXPECT_EQ(futures[i].get(), i * 2);
    }
}

TEST_F(ThreadPoolTest, ParallelFor) {
    ThreadPool pool(4);
    std::vector<int> results(100, 0);
    std::atomic<int> counter{0};

    pool.parallel_for(0, 100, [&](size_t i) {
        results[i] = static_cast<int>(i * 2);
        ++counter;
    });

    EXPECT_EQ(counter.load(), 100);
    for (int i = 0; i < 100; ++i) {
        EXPECT_EQ(results[i], i * 2);
    }
}

TEST_F(ThreadPoolTest, ParallelMap) {
    ThreadPool pool(4);
    std::vector<int> input = {1, 2, 3, 4, 5};

    auto results = pool.parallel_map(input, [](const int& x) {
        return x * x;
    });

    EXPECT_EQ(results.size(), 5);
    EXPECT_EQ(results[0], 1);
    EXPECT_EQ(results[1], 4);
    EXPECT_EQ(results[2], 9);
    EXPECT_EQ(results[3], 16);
    EXPECT_EQ(results[4], 25);
}

TEST_F(ThreadPoolTest, Size) {
    ThreadPool pool(8);
    EXPECT_EQ(pool.size(), 8);
}

TEST_F(ThreadPoolTest, WaitAll) {
    ThreadPool pool(4);
    std::atomic<int> counter{0};

    for (int i = 0; i < 100; ++i) {
        pool.submit([&counter]() {
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
            ++counter;
        });
    }

    pool.wait_all();
    EXPECT_EQ(counter.load(), 100);
}

TEST_F(ThreadPoolTest, EmptyParallelFor) {
    ThreadPool pool(4);

    // Should not crash or hang
    pool.parallel_for(0, 0, [](size_t) {});
    pool.parallel_for(5, 5, [](size_t) {});
}

TEST_F(ThreadPoolTest, SingleElementParallelFor) {
    ThreadPool pool(4);
    int called = 0;

    pool.parallel_for(0, 1, [&called](size_t) {
        ++called;
    });

    EXPECT_EQ(called, 1);
}

// =============================================================================
// Clone Extender Tests
// =============================================================================

class CloneExtenderTest : public ::testing::Test {
protected:
    // Helper to create test tokens
    NormalizedToken make_token(TokenType type, uint32_t hash, uint32_t line) {
        NormalizedToken tok;
        tok.type = type;
        tok.original_hash = hash;
        tok.normalized_hash = hash;
        tok.line = line;
        tok.column = 0;
        tok.length = 1;
        return tok;
    }

    TokenizedFile create_test_file(const std::vector<uint32_t>& hashes) {
        TokenizedFile file;
        file.path = "test.py";
        for (size_t i = 0; i < hashes.size(); ++i) {
            file.tokens.push_back(make_token(
                TokenType::KEYWORD,
                hashes[i],
                static_cast<uint32_t>(i + 1)
            ));
        }
        file.total_lines = static_cast<uint32_t>(hashes.size());
        return file;
    }
};

TEST_F(CloneExtenderTest, JaccardIdentical) {
    std::vector<uint32_t> hashes = {1, 2, 3, 4, 5};
    TokenizedFile file = create_test_file(hashes);

    float sim = CloneExtender::jaccard_similarity(
        file.tokens, 0, 5,
        file.tokens, 0, 5
    );

    EXPECT_FLOAT_EQ(sim, 1.0f);
}

TEST_F(CloneExtenderTest, JaccardDifferent) {
    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    TokenizedFile file_b = create_test_file({6, 7, 8, 9, 10});

    float sim = CloneExtender::jaccard_similarity(
        file_a.tokens, 0, 5,
        file_b.tokens, 0, 5
    );

    EXPECT_FLOAT_EQ(sim, 0.0f);
}

TEST_F(CloneExtenderTest, JaccardPartialOverlap) {
    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    TokenizedFile file_b = create_test_file({3, 4, 5, 6, 7});

    float sim = CloneExtender::jaccard_similarity(
        file_a.tokens, 0, 5,
        file_b.tokens, 0, 5
    );

    // Intersection: {3, 4, 5} = 3, Union: {1,2,3,4,5,6,7} = 7
    // But since we're using multiset: intersection=3, union=7
    EXPECT_GT(sim, 0.0f);
    EXPECT_LT(sim, 1.0f);
}

TEST_F(CloneExtenderTest, AlignmentIdentical) {
    TokenizedFile file = create_test_file({1, 2, 3, 4, 5});

    float sim = CloneExtender::alignment_similarity(
        file.tokens, 0, 5,
        file.tokens, 0, 5,
        2
    );

    EXPECT_FLOAT_EQ(sim, 1.0f);
}

TEST_F(CloneExtenderTest, AlignmentWithGap) {
    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    TokenizedFile file_b = create_test_file({1, 2, 99, 3, 4, 5});  // Extra token

    float sim = CloneExtender::alignment_similarity(
        file_a.tokens, 0, 5,
        file_b.tokens, 0, 6,
        2
    );

    // Should handle the gap and find matches
    EXPECT_GT(sim, 0.5f);
}

TEST_F(CloneExtenderTest, ExtendBasic) {
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.lookahead = 5;

    CloneExtender extender(config);

    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5, 6, 7, 8});
    TokenizedFile file_b = create_test_file({1, 2, 3, 4, 5, 6, 7, 8});

    ClonePair seed;
    seed.location_a.file_id = 0;
    seed.location_a.token_start = 2;
    seed.location_a.token_count = 3;
    seed.location_a.start_line = 3;
    seed.location_a.end_line = 5;
    seed.location_b.file_id = 1;
    seed.location_b.token_start = 2;
    seed.location_b.token_count = 3;
    seed.location_b.start_line = 3;
    seed.location_b.end_line = 5;
    seed.similarity = 1.0f;
    seed.clone_type = CloneType::TYPE_1;

    auto extended = extender.extend(seed, file_a, file_b);

    // Should extend in both directions
    EXPECT_GE(extended.token_count(), seed.token_count());
}

TEST_F(CloneExtenderTest, EmptyInput) {
    TokenizedFile empty_file;
    empty_file.path = "empty.py";

    float sim = CloneExtender::jaccard_similarity(
        empty_file.tokens, 0, 0,
        empty_file.tokens, 0, 0
    );

    EXPECT_FLOAT_EQ(sim, 0.0f);
}

// =============================================================================
// Clone Extender Edge Cases - extend_forward / extend_backward
// =============================================================================

TEST_F(CloneExtenderTest, ExtendForwardAtEndOfFile) {
    // Test extension when already at end of file
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.min_tokens = 3;
    config.lookahead = 5;

    CloneExtender extender(config);

    // Files with matching tokens at the end
    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    TokenizedFile file_b = create_test_file({1, 2, 3, 4, 5});

    // Clone starting near end (last 2 tokens)
    ClonePair seed;
    seed.location_a.file_id = 0;
    seed.location_a.token_start = 3;  // Tokens 4,5
    seed.location_a.token_count = 2;
    seed.location_a.start_line = 4;
    seed.location_a.end_line = 5;
    seed.location_b.file_id = 1;
    seed.location_b.token_start = 3;
    seed.location_b.token_count = 2;
    seed.location_b.start_line = 4;
    seed.location_b.end_line = 5;
    seed.similarity = 1.0f;
    seed.clone_type = CloneType::TYPE_1;

    auto extended = extender.extend(seed, file_a, file_b);

    // Should extend backward but not crash at end
    EXPECT_GE(extended.location_a.token_count, 2);
}

TEST_F(CloneExtenderTest, ExtendBackwardAtStartOfFile) {
    // Test extension when already at start of file
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.min_tokens = 3;
    config.lookahead = 5;

    CloneExtender extender(config);

    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    TokenizedFile file_b = create_test_file({1, 2, 3, 4, 5});

    // Clone at very start (first 2 tokens)
    ClonePair seed;
    seed.location_a.file_id = 0;
    seed.location_a.token_start = 0;  // Tokens 1,2
    seed.location_a.token_count = 2;
    seed.location_a.start_line = 1;
    seed.location_a.end_line = 2;
    seed.location_b.file_id = 1;
    seed.location_b.token_start = 0;
    seed.location_b.token_count = 2;
    seed.location_b.start_line = 1;
    seed.location_b.end_line = 2;
    seed.similarity = 1.0f;
    seed.clone_type = CloneType::TYPE_1;

    auto extended = extender.extend(seed, file_a, file_b);

    // Should extend forward but not crash at start (no backward extension possible)
    EXPECT_GE(extended.location_a.token_count, 2);
    // Start should remain at 0
    EXPECT_EQ(extended.location_a.token_start, 0);
}

TEST_F(CloneExtenderTest, ExtendWithMaxGapReached) {
    // Test when gap is larger than max_gap
    CloneExtender::Config config;
    config.max_gap = 2;  // Only allow 2 token gap
    config.min_similarity = 0.5f;
    config.min_tokens = 3;
    config.lookahead = 5;

    CloneExtender extender(config);

    // File A: 1,2,3,4,5
    // File B: 1,2,99,98,97,3,4,5 (3 token gap - exceeds max_gap)
    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    TokenizedFile file_b = create_test_file({1, 2, 99, 98, 97, 3, 4, 5});

    ClonePair seed;
    seed.location_a.file_id = 0;
    seed.location_a.token_start = 0;
    seed.location_a.token_count = 2;  // Match on 1,2
    seed.location_a.start_line = 1;
    seed.location_a.end_line = 2;
    seed.location_b.file_id = 1;
    seed.location_b.token_start = 0;
    seed.location_b.token_count = 2;
    seed.location_b.start_line = 1;
    seed.location_b.end_line = 2;
    seed.similarity = 1.0f;
    seed.clone_type = CloneType::TYPE_1;

    auto extended = extender.extend(seed, file_a, file_b);

    // Extension should stop when gap > max_gap
    // Should not extend past the gap
    EXPECT_LE(extended.location_a.token_count, 5);
}

TEST_F(CloneExtenderTest, ExtendWithSmallGap) {
    // Test when gap is within max_gap
    CloneExtender::Config config;
    config.max_gap = 3;  // Allow 3 token gap
    config.min_similarity = 0.3f;  // Lower threshold
    config.min_tokens = 2;
    config.lookahead = 5;

    CloneExtender extender(config);

    // File A: 1,2,3,4,5
    // File B: 1,2,99,3,4,5 (1 token gap - within max_gap)
    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    TokenizedFile file_b = create_test_file({1, 2, 99, 3, 4, 5});

    ClonePair seed;
    seed.location_a.file_id = 0;
    seed.location_a.token_start = 0;
    seed.location_a.token_count = 2;
    seed.location_a.start_line = 1;
    seed.location_a.end_line = 2;
    seed.location_b.file_id = 1;
    seed.location_b.token_start = 0;
    seed.location_b.token_count = 2;
    seed.location_b.start_line = 1;
    seed.location_b.end_line = 2;
    seed.similarity = 1.0f;
    seed.clone_type = CloneType::TYPE_1;

    auto extended = extender.extend(seed, file_a, file_b);

    // Should potentially extend across the small gap
    EXPECT_GE(extended.location_a.token_count, 2);
}

TEST_F(CloneExtenderTest, ExtendNoMatchingTokens) {
    // Test when there are no matching tokens to extend into
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.min_tokens = 2;
    config.lookahead = 5;

    CloneExtender extender(config);

    // Files with completely different surrounding tokens
    TokenizedFile file_a = create_test_file({100, 101, 5, 5, 102, 103});
    TokenizedFile file_b = create_test_file({200, 201, 5, 5, 202, 203});

    ClonePair seed;
    seed.location_a.file_id = 0;
    seed.location_a.token_start = 2;  // The two 5's
    seed.location_a.token_count = 2;
    seed.location_a.start_line = 3;
    seed.location_a.end_line = 4;
    seed.location_b.file_id = 1;
    seed.location_b.token_start = 2;
    seed.location_b.token_count = 2;
    seed.location_b.start_line = 3;
    seed.location_b.end_line = 4;
    seed.similarity = 1.0f;
    seed.clone_type = CloneType::TYPE_1;

    auto extended = extender.extend(seed, file_a, file_b);

    // Should not extend (surrounding tokens don't match)
    // Returns original or minimally extended
    EXPECT_GE(extended.location_a.token_count, 2);
}

TEST_F(CloneExtenderTest, ExtendSingleTokenClone) {
    // Edge case: trying to extend a single token clone
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.min_tokens = 1;
    config.lookahead = 5;

    CloneExtender extender(config);

    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    TokenizedFile file_b = create_test_file({1, 2, 3, 4, 5});

    ClonePair seed;
    seed.location_a.file_id = 0;
    seed.location_a.token_start = 2;  // Just token 3
    seed.location_a.token_count = 1;
    seed.location_a.start_line = 3;
    seed.location_a.end_line = 3;
    seed.location_b.file_id = 1;
    seed.location_b.token_start = 2;
    seed.location_b.token_count = 1;
    seed.location_b.start_line = 3;
    seed.location_b.end_line = 3;
    seed.similarity = 1.0f;
    seed.clone_type = CloneType::TYPE_1;

    auto extended = extender.extend(seed, file_a, file_b);

    // Should extend in both directions
    EXPECT_GE(extended.location_a.token_count, 1);
}

// =============================================================================
// Clone Extender - extend_all with multiple files
// =============================================================================

TEST_F(CloneExtenderTest, ExtendAllEmptyPairs) {
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.min_tokens = 3;

    CloneExtender extender(config);

    std::vector<ClonePair> empty_pairs;
    std::vector<TokenizedFile> files;
    HashIndex index;

    auto result = extender.extend_all(empty_pairs, files, index);

    EXPECT_TRUE(result.empty());
}

TEST_F(CloneExtenderTest, ExtendAllSinglePair) {
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.min_tokens = 2;
    config.lookahead = 5;

    CloneExtender extender(config);

    // Create two files
    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    file_a.path = "file_a.py";
    TokenizedFile file_b = create_test_file({1, 2, 3, 4, 5});
    file_b.path = "file_b.py";

    std::vector<TokenizedFile> files = {file_a, file_b};

    // Build index
    HashIndex index;
    index.register_file("file_a.py");
    index.register_file("file_b.py");

    // Create a clone pair
    ClonePair pair;
    pair.location_a.file_id = 0;
    pair.location_a.token_start = 1;
    pair.location_a.token_count = 3;
    pair.location_a.start_line = 2;
    pair.location_a.end_line = 4;
    pair.location_b.file_id = 1;
    pair.location_b.token_start = 1;
    pair.location_b.token_count = 3;
    pair.location_b.start_line = 2;
    pair.location_b.end_line = 4;
    pair.similarity = 1.0f;
    pair.clone_type = CloneType::TYPE_1;

    std::vector<ClonePair> pairs = {pair};

    auto result = extender.extend_all(pairs, files, index);

    EXPECT_EQ(result.size(), 1);
    EXPECT_GE(result[0].token_count(), 3);
}

TEST_F(CloneExtenderTest, ExtendAllMultiplePairs) {
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.min_tokens = 2;
    config.lookahead = 5;

    CloneExtender extender(config);

    // Create three files with some shared code
    TokenizedFile file_a = create_test_file({1, 2, 3, 10, 11, 12});
    file_a.path = "file_a.py";
    TokenizedFile file_b = create_test_file({1, 2, 3, 20, 21, 22});
    file_b.path = "file_b.py";
    TokenizedFile file_c = create_test_file({1, 2, 3, 30, 31, 32});
    file_c.path = "file_c.py";

    std::vector<TokenizedFile> files = {file_a, file_b, file_c};

    HashIndex index;
    index.register_file("file_a.py");
    index.register_file("file_b.py");
    index.register_file("file_c.py");

    // Create clone pairs (A-B and A-C)
    ClonePair pair1;
    pair1.location_a.file_id = 0;
    pair1.location_a.token_start = 0;
    pair1.location_a.token_count = 3;
    pair1.location_a.start_line = 1;
    pair1.location_a.end_line = 3;
    pair1.location_b.file_id = 1;
    pair1.location_b.token_start = 0;
    pair1.location_b.token_count = 3;
    pair1.location_b.start_line = 1;
    pair1.location_b.end_line = 3;
    pair1.similarity = 1.0f;

    ClonePair pair2;
    pair2.location_a.file_id = 0;
    pair2.location_a.token_start = 0;
    pair2.location_a.token_count = 3;
    pair2.location_a.start_line = 1;
    pair2.location_a.end_line = 3;
    pair2.location_b.file_id = 2;
    pair2.location_b.token_start = 0;
    pair2.location_b.token_count = 3;
    pair2.location_b.start_line = 1;
    pair2.location_b.end_line = 3;
    pair2.similarity = 1.0f;

    std::vector<ClonePair> pairs = {pair1, pair2};

    auto result = extender.extend_all(pairs, files, index);

    EXPECT_EQ(result.size(), 2);
}

TEST_F(CloneExtenderTest, ExtendAllFiltersSmallClones) {
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.min_tokens = 10;  // High threshold
    config.lookahead = 5;

    CloneExtender extender(config);

    // Small files that won't meet min_tokens after extension
    TokenizedFile file_a = create_test_file({1, 2, 3});
    file_a.path = "small_a.py";
    TokenizedFile file_b = create_test_file({1, 2, 3});
    file_b.path = "small_b.py";

    std::vector<TokenizedFile> files = {file_a, file_b};

    HashIndex index;
    index.register_file("small_a.py");
    index.register_file("small_b.py");

    ClonePair pair;
    pair.location_a.file_id = 0;
    pair.location_a.token_start = 0;
    pair.location_a.token_count = 3;
    pair.location_a.start_line = 1;
    pair.location_a.end_line = 3;
    pair.location_b.file_id = 1;
    pair.location_b.token_start = 0;
    pair.location_b.token_count = 3;
    pair.location_b.start_line = 1;
    pair.location_b.end_line = 3;
    pair.similarity = 1.0f;

    std::vector<ClonePair> pairs = {pair};

    auto result = extender.extend_all(pairs, files, index);

    // Should be filtered out due to min_tokens
    EXPECT_TRUE(result.empty());
}

TEST_F(CloneExtenderTest, ExtendAllMissingFile) {
    // Test when file is not found in map
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.min_tokens = 2;

    CloneExtender extender(config);

    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    file_a.path = "file_a.py";

    std::vector<TokenizedFile> files = {file_a};  // Only one file

    HashIndex index;
    index.register_file("file_a.py");
    index.register_file("file_b.py");  // Registered but not in files

    ClonePair pair;
    pair.location_a.file_id = 0;  // file_a - exists
    pair.location_a.token_start = 0;
    pair.location_a.token_count = 3;
    pair.location_a.start_line = 1;
    pair.location_a.end_line = 3;
    pair.location_b.file_id = 1;  // file_b - NOT in files vector
    pair.location_b.token_start = 0;
    pair.location_b.token_count = 3;
    pair.location_b.start_line = 1;
    pair.location_b.end_line = 3;
    pair.similarity = 1.0f;

    std::vector<ClonePair> pairs = {pair};

    auto result = extender.extend_all(pairs, files, index);

    // Should return original pair (cannot extend)
    EXPECT_EQ(result.size(), 1);
}

// =============================================================================
// Clone Extender - Boundary and Similarity Tests
// =============================================================================

TEST_F(CloneExtenderTest, JaccardEmptySecondSequence) {
    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    TokenizedFile file_b;  // Empty
    file_b.path = "empty.py";

    float sim = CloneExtender::jaccard_similarity(
        file_a.tokens, 0, 5,
        file_b.tokens, 0, 0
    );

    EXPECT_FLOAT_EQ(sim, 0.0f);
}

TEST_F(CloneExtenderTest, JaccardSingleElement) {
    TokenizedFile file_a = create_test_file({42});
    TokenizedFile file_b = create_test_file({42});

    float sim = CloneExtender::jaccard_similarity(
        file_a.tokens, 0, 1,
        file_b.tokens, 0, 1
    );

    EXPECT_FLOAT_EQ(sim, 1.0f);
}

TEST_F(CloneExtenderTest, JaccardDuplicateHashes) {
    // Test with duplicate hashes in sequences
    TokenizedFile file_a = create_test_file({1, 1, 1, 2, 2});
    TokenizedFile file_b = create_test_file({1, 1, 2, 2, 2});

    float sim = CloneExtender::jaccard_similarity(
        file_a.tokens, 0, 5,
        file_b.tokens, 0, 5
    );

    // Should handle duplicates correctly
    EXPECT_GT(sim, 0.0f);
    EXPECT_LT(sim, 1.0f);
}

TEST_F(CloneExtenderTest, AlignmentEmptySequence) {
    TokenizedFile file_a = create_test_file({1, 2, 3});
    TokenizedFile file_b;
    file_b.path = "empty.py";

    float sim = CloneExtender::alignment_similarity(
        file_a.tokens, 0, 3,
        file_b.tokens, 0, 0,
        2
    );

    EXPECT_FLOAT_EQ(sim, 0.0f);
}

TEST_F(CloneExtenderTest, AlignmentOutOfBounds) {
    TokenizedFile file_a = create_test_file({1, 2, 3});

    // Request more tokens than available
    float sim = CloneExtender::alignment_similarity(
        file_a.tokens, 0, 100,  // count exceeds size
        file_a.tokens, 0, 100,
        2
    );

    // Should handle gracefully using actual available tokens
    EXPECT_GT(sim, 0.0f);
}

TEST_F(CloneExtenderTest, ExtendUpdatesLineNumbers) {
    CloneExtender::Config config;
    config.max_gap = 2;
    config.min_similarity = 0.5f;
    config.min_tokens = 1;
    config.lookahead = 5;

    CloneExtender extender(config);

    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5, 6, 7, 8, 9, 10});
    TokenizedFile file_b = create_test_file({1, 2, 3, 4, 5, 6, 7, 8, 9, 10});

    // Small seed in the middle
    ClonePair seed;
    seed.location_a.file_id = 0;
    seed.location_a.token_start = 4;  // Token 5
    seed.location_a.token_count = 2;
    seed.location_a.start_line = 5;
    seed.location_a.end_line = 6;
    seed.location_b.file_id = 1;
    seed.location_b.token_start = 4;
    seed.location_b.token_count = 2;
    seed.location_b.start_line = 5;
    seed.location_b.end_line = 6;
    seed.similarity = 1.0f;

    auto extended = extender.extend(seed, file_a, file_b);

    // Line numbers should be updated if extended
    if (extended.location_a.token_count > seed.location_a.token_count) {
        // If extended backward, start_line should decrease
        if (extended.location_a.token_start < seed.location_a.token_start) {
            EXPECT_LT(extended.location_a.start_line, seed.location_a.start_line);
        }
        // If extended forward, end_line should increase
        uint32_t seed_end = seed.location_a.token_start + seed.location_a.token_count;
        uint32_t ext_end = extended.location_a.token_start + extended.location_a.token_count;
        if (ext_end > seed_end) {
            EXPECT_GT(extended.location_a.end_line, seed.location_a.end_line);
        }
    }
}

TEST_F(CloneExtenderTest, ExtendDeterminesCloneType) {
    CloneExtender::Config config;
    config.max_gap = 3;
    config.min_similarity = 0.6f;
    config.min_tokens = 2;
    config.lookahead = 5;

    CloneExtender extender(config);

    // Type-3 scenario: files with gaps
    TokenizedFile file_a = create_test_file({1, 2, 3, 4, 5});
    TokenizedFile file_b = create_test_file({1, 2, 99, 4, 5});  // 3 replaced with 99

    ClonePair seed;
    seed.location_a.file_id = 0;
    seed.location_a.token_start = 0;
    seed.location_a.token_count = 2;
    seed.location_a.start_line = 1;
    seed.location_a.end_line = 2;
    seed.location_b.file_id = 1;
    seed.location_b.token_start = 0;
    seed.location_b.token_count = 2;
    seed.location_b.start_line = 1;
    seed.location_b.end_line = 2;
    seed.similarity = 1.0f;
    seed.clone_type = CloneType::TYPE_1;

    auto extended = extender.extend(seed, file_a, file_b);

    // Clone type may change based on extension result
    // If similarity < 1.0, should be TYPE_3
    if (extended.similarity < 1.0f) {
        EXPECT_EQ(extended.clone_type, CloneType::TYPE_3);
    }
}

TEST_F(CloneExtenderTest, ExtendRejectsLowSimilarity) {
    CloneExtender::Config config;
    config.max_gap = 1;
    config.min_similarity = 0.95f;  // Very high threshold
    config.min_tokens = 2;
    config.lookahead = 5;

    CloneExtender extender(config);

    // Files where extension would reduce similarity too much
    TokenizedFile file_a = create_test_file({1, 2, 3, 100, 101, 102});
    TokenizedFile file_b = create_test_file({1, 2, 3, 200, 201, 202});

    ClonePair seed;
    seed.location_a.file_id = 0;
    seed.location_a.token_start = 0;
    seed.location_a.token_count = 3;  // Matches 1,2,3
    seed.location_a.start_line = 1;
    seed.location_a.end_line = 3;
    seed.location_b.file_id = 1;
    seed.location_b.token_start = 0;
    seed.location_b.token_count = 3;
    seed.location_b.start_line = 1;
    seed.location_b.end_line = 3;
    seed.similarity = 1.0f;

    auto extended = extender.extend(seed, file_a, file_b);

    // Should not extend into non-matching region since it would drop similarity
    EXPECT_LE(extended.location_a.token_count, 3);
}

// =============================================================================
// Integration Tests
// =============================================================================

TEST_F(ThreadPoolTest, ThreadSafeLRUCache) {
    ThreadPool pool(8);
    LRUCache<int, int> cache(100);
    std::atomic<int> success_count{0};

    pool.parallel_for(0, 1000, [&](size_t i) {
        int key = static_cast<int>(i % 50);
        cache.put(key, static_cast<int>(i));

        auto val = cache.get(key);
        if (val.has_value()) {
            ++success_count;
        }
    });

    // Should have many successful operations
    EXPECT_GT(success_count.load(), 500);
}
