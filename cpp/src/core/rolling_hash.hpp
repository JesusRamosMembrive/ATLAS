#pragma once

#include <cstdint>
#include <deque>
#include <optional>
#include <vector>

namespace aegis::similarity {

/**
 * Rabin-Karp rolling hash implementation.
 *
 * This class computes rolling hashes over a sliding window of tokens,
 * allowing O(1) computation of the hash for each new window position.
 *
 * Algorithm:
 *   hash = (t[0] * BASE^(w-1) + t[1] * BASE^(w-2) + ... + t[w-1]) mod MOD
 *
 * When sliding the window:
 *   new_hash = ((old_hash - t[0] * BASE^(w-1)) * BASE + t[new]) mod MOD
 *
 * Constants chosen for low collision rate:
 *   BASE = 31 (small prime, good ASCII distribution)
 *   MOD = 1e9 + 9 (large prime)
 */
class RollingHash {
public:
    // Hash constants
    static constexpr uint64_t BASE = 31;
    static constexpr uint64_t MOD = 1'000'000'009ULL;

    /**
     * Construct a rolling hash with the specified window size.
     *
     * @param window_size Number of tokens in the sliding window
     */
    explicit RollingHash(size_t window_size);

    /**
     * Reset the rolling hash to initial state.
     * Call this when starting a new file.
     */
    void reset();

    /**
     * Push a new token hash into the window.
     *
     * @param token_hash Hash value of the token to add
     * @return The window hash if window is full, nullopt otherwise
     */
    std::optional<uint64_t> push(uint64_t token_hash);

    /**
     * Get the current window size.
     */
    size_t window_size() const { return window_size_; }

    /**
     * Get the number of tokens currently in the window.
     */
    size_t current_size() const { return window_.size(); }

    /**
     * Check if the window is full.
     */
    bool is_full() const { return window_.size() >= window_size_; }

    /**
     * Compute hash for a sequence of token hashes (non-rolling).
     * Useful for testing and one-off computations.
     *
     * @param token_hashes Vector of token hash values
     * @return Combined hash of the sequence
     */
    static uint64_t compute_hash(const std::vector<uint64_t>& token_hashes);

    /**
     * Compute BASE^exp mod MOD.
     * Useful for external calculations.
     */
    static uint64_t power_mod(uint64_t exp);

private:
    size_t window_size_;
    uint64_t hash_ = 0;
    uint64_t base_power_;  // BASE^(window_size-1) mod MOD
    std::deque<uint64_t> window_;
};

/**
 * Batch processor for computing all window hashes in a token sequence.
 * More efficient than calling push() repeatedly when you need all hashes.
 */
class HashSequence {
public:
    /**
     * Compute all window hashes for a token sequence.
     *
     * @param token_hashes Vector of token hash values
     * @param window_size Size of the sliding window
     * @return Vector of (position, hash) pairs
     */
    static std::vector<std::pair<size_t, uint64_t>> compute_all(
        const std::vector<uint64_t>& token_hashes,
        size_t window_size
    );
};

}  // namespace aegis::similarity
