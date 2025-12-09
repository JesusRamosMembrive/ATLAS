#include <gtest/gtest.h>
#include "core/rolling_hash.hpp"
#include <vector>

using namespace aegis::similarity;

class RollingHashTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Common setup if needed
    }
};

// =============================================================================
// Basic Functionality Tests
// =============================================================================

TEST_F(RollingHashTest, ConstructorSetsWindowSize) {
    RollingHash hasher(10);
    EXPECT_EQ(hasher.window_size(), 10);
    EXPECT_EQ(hasher.current_size(), 0);
    EXPECT_FALSE(hasher.is_full());
}

TEST_F(RollingHashTest, PushReturnsNulloptUntilWindowFull) {
    RollingHash hasher(3);

    auto result1 = hasher.push(100);
    EXPECT_FALSE(result1.has_value());
    EXPECT_EQ(hasher.current_size(), 1);

    auto result2 = hasher.push(200);
    EXPECT_FALSE(result2.has_value());
    EXPECT_EQ(hasher.current_size(), 2);

    auto result3 = hasher.push(300);
    EXPECT_TRUE(result3.has_value());
    EXPECT_TRUE(hasher.is_full());
}

TEST_F(RollingHashTest, ResetClearsState) {
    RollingHash hasher(3);
    hasher.push(100);
    hasher.push(200);
    hasher.push(300);

    hasher.reset();

    EXPECT_EQ(hasher.current_size(), 0);
    EXPECT_FALSE(hasher.is_full());
}

// =============================================================================
// Hash Consistency Tests
// =============================================================================

TEST_F(RollingHashTest, SameInputProducesSameHash) {
    RollingHash hasher1(3);
    RollingHash hasher2(3);

    hasher1.push(10);
    hasher1.push(20);
    auto hash1 = hasher1.push(30);

    hasher2.push(10);
    hasher2.push(20);
    auto hash2 = hasher2.push(30);

    ASSERT_TRUE(hash1.has_value());
    ASSERT_TRUE(hash2.has_value());
    EXPECT_EQ(*hash1, *hash2);
}

TEST_F(RollingHashTest, DifferentInputProducesDifferentHash) {
    RollingHash hasher1(3);
    RollingHash hasher2(3);

    hasher1.push(10);
    hasher1.push(20);
    auto hash1 = hasher1.push(30);

    hasher2.push(10);
    hasher2.push(20);
    auto hash2 = hasher2.push(99);  // Different!

    ASSERT_TRUE(hash1.has_value());
    ASSERT_TRUE(hash2.has_value());
    EXPECT_NE(*hash1, *hash2);
}

TEST_F(RollingHashTest, OrderMatters) {
    RollingHash hasher1(3);
    RollingHash hasher2(3);

    hasher1.push(10);
    hasher1.push(20);
    auto hash1 = hasher1.push(30);

    hasher2.push(30);  // Different order
    hasher2.push(20);
    auto hash2 = hasher2.push(10);

    ASSERT_TRUE(hash1.has_value());
    ASSERT_TRUE(hash2.has_value());
    EXPECT_NE(*hash1, *hash2);
}

// =============================================================================
// Rolling Window Tests
// =============================================================================

TEST_F(RollingHashTest, RollingWindowProducesCorrectHashes) {
    // Test that sliding window produces correct hashes
    RollingHash rolling(3);
    std::vector<uint64_t> tokens = {10, 20, 30, 40, 50};
    std::vector<uint64_t> hashes;

    for (auto token : tokens) {
        auto hash = rolling.push(token);
        if (hash.has_value()) {
            hashes.push_back(*hash);
        }
    }

    // Should get 3 hashes: [10,20,30], [20,30,40], [30,40,50]
    ASSERT_EQ(hashes.size(), 3);

    // Verify each hash independently
    EXPECT_EQ(hashes[0], RollingHash::compute_hash({10, 20, 30}));
    EXPECT_EQ(hashes[1], RollingHash::compute_hash({20, 30, 40}));
    EXPECT_EQ(hashes[2], RollingHash::compute_hash({30, 40, 50}));
}

TEST_F(RollingHashTest, ComputeHashMatchesRollingHash) {
    std::vector<uint64_t> tokens = {100, 200, 300, 400};

    // Compute using static method
    uint64_t static_hash = RollingHash::compute_hash(tokens);

    // Compute using rolling hasher
    RollingHash hasher(4);
    std::optional<uint64_t> rolling_hash;
    for (auto token : tokens) {
        rolling_hash = hasher.push(token);
    }

    ASSERT_TRUE(rolling_hash.has_value());
    EXPECT_EQ(static_hash, *rolling_hash);
}

// =============================================================================
// HashSequence Tests
// =============================================================================

TEST_F(RollingHashTest, HashSequenceComputesAllWindows) {
    std::vector<uint64_t> tokens = {1, 2, 3, 4, 5, 6};
    auto results = HashSequence::compute_all(tokens, 3);

    // Window size 3 over 6 tokens = 4 windows
    ASSERT_EQ(results.size(), 4);

    // Verify positions
    EXPECT_EQ(results[0].first, 0);  // Window [1,2,3]
    EXPECT_EQ(results[1].first, 1);  // Window [2,3,4]
    EXPECT_EQ(results[2].first, 2);  // Window [3,4,5]
    EXPECT_EQ(results[3].first, 3);  // Window [4,5,6]

    // Verify hashes
    EXPECT_EQ(results[0].second, RollingHash::compute_hash({1, 2, 3}));
    EXPECT_EQ(results[1].second, RollingHash::compute_hash({2, 3, 4}));
    EXPECT_EQ(results[2].second, RollingHash::compute_hash({3, 4, 5}));
    EXPECT_EQ(results[3].second, RollingHash::compute_hash({4, 5, 6}));
}

TEST_F(RollingHashTest, HashSequenceEmptyForSmallInput) {
    std::vector<uint64_t> tokens = {1, 2};
    auto results = HashSequence::compute_all(tokens, 5);  // Window larger than input

    EXPECT_TRUE(results.empty());
}

TEST_F(RollingHashTest, HashSequenceHandlesSingleWindow) {
    std::vector<uint64_t> tokens = {1, 2, 3};
    auto results = HashSequence::compute_all(tokens, 3);

    ASSERT_EQ(results.size(), 1);
    EXPECT_EQ(results[0].first, 0);
    EXPECT_EQ(results[0].second, RollingHash::compute_hash({1, 2, 3}));
}

// =============================================================================
// Edge Cases
// =============================================================================

TEST_F(RollingHashTest, WindowSizeOne) {
    RollingHash hasher(1);

    auto hash1 = hasher.push(42);
    ASSERT_TRUE(hash1.has_value());
    EXPECT_EQ(*hash1, 42 % RollingHash::MOD);

    auto hash2 = hasher.push(100);
    ASSERT_TRUE(hash2.has_value());
    EXPECT_EQ(*hash2, 100 % RollingHash::MOD);
}

TEST_F(RollingHashTest, LargeTokenValues) {
    RollingHash hasher(3);

    uint64_t large1 = 0xFFFFFFFF;
    uint64_t large2 = 0xDEADBEEF;
    uint64_t large3 = 0xCAFEBABE;

    hasher.push(large1);
    hasher.push(large2);
    auto hash = hasher.push(large3);

    ASSERT_TRUE(hash.has_value());
    // Just verify it doesn't overflow and produces consistent result
    EXPECT_EQ(*hash, RollingHash::compute_hash({large1, large2, large3}));
}

TEST_F(RollingHashTest, PowerModCorrectness) {
    // BASE^0 = 1
    EXPECT_EQ(RollingHash::power_mod(0), 1);

    // BASE^1 = BASE
    EXPECT_EQ(RollingHash::power_mod(1), RollingHash::BASE);

    // BASE^2
    uint64_t expected = (RollingHash::BASE * RollingHash::BASE) % RollingHash::MOD;
    EXPECT_EQ(RollingHash::power_mod(2), expected);

    // Verify larger exponents don't overflow
    auto result = RollingHash::power_mod(1000);
    EXPECT_LT(result, RollingHash::MOD);
}

TEST_F(RollingHashTest, EmptyComputeHash) {
    std::vector<uint64_t> empty;
    EXPECT_EQ(RollingHash::compute_hash(empty), 0);
}

// =============================================================================
// Collision Resistance (Statistical Test)
// =============================================================================

TEST_F(RollingHashTest, LowCollisionRateForSequentialValues) {
    // Generate many sequential windows and check for collisions
    std::vector<uint64_t> tokens;
    for (uint64_t i = 0; i < 1000; ++i) {
        tokens.push_back(i);
    }

    auto results = HashSequence::compute_all(tokens, 10);

    // Check for unique hashes (should be very high uniqueness)
    std::set<uint64_t> unique_hashes;
    for (const auto& [pos, hash] : results) {
        unique_hashes.insert(hash);
    }

    // Expect at least 99% unique for sequential values
    double uniqueness = static_cast<double>(unique_hashes.size()) / results.size();
    EXPECT_GT(uniqueness, 0.99);
}

// =============================================================================
// Real-World Simulation
// =============================================================================

TEST_F(RollingHashTest, DetectDuplicateSequences) {
    // Simulate finding duplicate code sequences
    std::vector<uint64_t> file_tokens = {
        1, 2, 3, 4, 5,      // Unique prefix
        10, 20, 30, 40, 50, // First occurrence of pattern
        6, 7, 8,            // Some different tokens
        10, 20, 30, 40, 50, // Second occurrence (duplicate!)
        9, 10, 11           // Unique suffix
    };

    auto results = HashSequence::compute_all(file_tokens, 5);

    // Find the hash of [10, 20, 30, 40, 50]
    uint64_t pattern_hash = RollingHash::compute_hash({10, 20, 30, 40, 50});

    // Count occurrences
    int occurrences = 0;
    std::vector<size_t> positions;
    for (const auto& [pos, hash] : results) {
        if (hash == pattern_hash) {
            occurrences++;
            positions.push_back(pos);
        }
    }

    EXPECT_EQ(occurrences, 2);
    EXPECT_EQ(positions[0], 5);   // First at index 5
    EXPECT_EQ(positions[1], 13);  // Second at index 13
}
