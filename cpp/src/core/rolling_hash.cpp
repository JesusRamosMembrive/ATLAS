#include "core/rolling_hash.hpp"

namespace aegis::similarity {

RollingHash::RollingHash(size_t window_size)
    : window_size_(window_size)
    , base_power_(1)
{
    // Pre-calculate BASE^(window_size-1) mod MOD
    for (size_t i = 1; i < window_size_; ++i) {
        base_power_ = (base_power_ * BASE) % MOD;
    }
}

void RollingHash::reset() {
    hash_ = 0;
    window_.clear();
}

std::optional<uint64_t> RollingHash::push(uint64_t token_hash) {
    // If window is already full, remove oldest token first
    if (window_.size() >= window_size_) {
        // Remove oldest token from hash
        // hash = hash - old_token * BASE^(window_size-1)
        uint64_t old_token = window_.front();
        window_.pop_front();

        // Subtract old token contribution (handle potential underflow)
        uint64_t old_contribution = (old_token * base_power_) % MOD;
        if (hash_ >= old_contribution) {
            hash_ = hash_ - old_contribution;
        } else {
            hash_ = MOD - (old_contribution - hash_);
        }
    }

    // Add new token to hash
    // hash = hash * BASE + new_token
    hash_ = (hash_ * BASE + token_hash) % MOD;
    window_.push_back(token_hash);

    // Return hash only if window is now full
    if (window_.size() >= window_size_) {
        return hash_;
    }

    return std::nullopt;
}

uint64_t RollingHash::compute_hash(const std::vector<uint64_t>& token_hashes) {
    if (token_hashes.empty()) {
        return 0;
    }

    uint64_t hash = 0;
    for (uint64_t token_hash : token_hashes) {
        hash = (hash * BASE + token_hash) % MOD;
    }
    return hash;
}

uint64_t RollingHash::power_mod(uint64_t exp) {
    uint64_t result = 1;
    uint64_t base = BASE;

    while (exp > 0) {
        if (exp % 2 == 1) {
            result = (result * base) % MOD;
        }
        base = (base * base) % MOD;
        exp /= 2;
    }

    return result;
}

std::vector<std::pair<size_t, uint64_t>> HashSequence::compute_all(
    const std::vector<uint64_t>& token_hashes,
    size_t window_size
) {
    std::vector<std::pair<size_t, uint64_t>> result;

    if (token_hashes.size() < window_size) {
        return result;
    }

    // Pre-allocate for efficiency
    result.reserve(token_hashes.size() - window_size + 1);

    RollingHash hasher(window_size);

    for (size_t i = 0; i < token_hashes.size(); ++i) {
        auto hash = hasher.push(token_hashes[i]);
        if (hash.has_value()) {
            // Position is the start of the window
            size_t start_pos = i - window_size + 1;
            result.emplace_back(start_pos, *hash);
        }
    }

    return result;
}

}  // namespace aegis::similarity
