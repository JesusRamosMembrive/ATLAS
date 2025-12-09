#include "core/clone_extender.hpp"
#include "core/hash_index.hpp"
#include <algorithm>
#include <unordered_set>

namespace aegis::similarity {

CloneExtender::CloneExtender(Config config)
    : config_(std::move(config))
{
}

float CloneExtender::jaccard_similarity(
    const std::vector<NormalizedToken>& tokens_a,
    size_t start_a, size_t count_a,
    const std::vector<NormalizedToken>& tokens_b,
    size_t start_b, size_t count_b
) {
    if (count_a == 0 || count_b == 0) {
        return 0.0f;
    }

    // Build hash sets for both sequences (using normalized hashes)
    std::unordered_multiset<uint32_t> set_a;
    std::unordered_multiset<uint32_t> set_b;

    size_t end_a = std::min(start_a + count_a, tokens_a.size());
    size_t end_b = std::min(start_b + count_b, tokens_b.size());

    for (size_t i = start_a; i < end_a; ++i) {
        set_a.insert(tokens_a[i].normalized_hash);
    }
    for (size_t i = start_b; i < end_b; ++i) {
        set_b.insert(tokens_b[i].normalized_hash);
    }

    // Calculate intersection size
    size_t intersection = 0;
    for (const auto& hash : set_a) {
        if (set_b.count(hash) > 0) {
            size_t count = std::min(set_a.count(hash), set_b.count(hash));
            intersection += count;
            // Avoid counting same element multiple times
            while (set_b.count(hash) > 0) {
                set_b.erase(set_b.find(hash));
            }
        }
    }

    // Union = |A| + |B| - intersection
    size_t union_size = (end_a - start_a) + (end_b - start_b) - intersection;

    if (union_size == 0) {
        return 0.0f;
    }

    return static_cast<float>(intersection) / static_cast<float>(union_size);
}

float CloneExtender::alignment_similarity(
    const std::vector<NormalizedToken>& tokens_a,
    size_t start_a, size_t count_a,
    const std::vector<NormalizedToken>& tokens_b,
    size_t start_b, size_t count_b,
    size_t max_gap
) {
    if (count_a == 0 || count_b == 0) {
        return 0.0f;
    }

    size_t end_a = std::min(start_a + count_a, tokens_a.size());
    size_t end_b = std::min(start_b + count_b, tokens_b.size());

    size_t matches = 0;
    size_t pos_a = start_a;
    size_t pos_b = start_b;

    while (pos_a < end_a && pos_b < end_b) {
        if (tokens_a[pos_a].normalized_hash == tokens_b[pos_b].normalized_hash) {
            ++matches;
            ++pos_a;
            ++pos_b;
        } else {
            // Try to find a match within max_gap
            bool found = false;

            // Look ahead in B
            for (size_t g = 1; g <= max_gap && pos_b + g < end_b; ++g) {
                if (tokens_a[pos_a].normalized_hash == tokens_b[pos_b + g].normalized_hash) {
                    pos_b += g;
                    found = true;
                    break;
                }
            }

            if (!found) {
                // Look ahead in A
                for (size_t g = 1; g <= max_gap && pos_a + g < end_a; ++g) {
                    if (tokens_a[pos_a + g].normalized_hash == tokens_b[pos_b].normalized_hash) {
                        pos_a += g;
                        found = true;
                        break;
                    }
                }
            }

            if (!found) {
                ++pos_a;
                ++pos_b;
            }
        }
    }

    size_t total = std::max(count_a, count_b);
    return static_cast<float>(matches) / static_cast<float>(total);
}

size_t CloneExtender::extend_forward(
    const std::vector<NormalizedToken>& tokens_a, size_t pos_a,
    const std::vector<NormalizedToken>& tokens_b, size_t pos_b
) const {
    size_t extended = 0;
    size_t gap_a = 0;
    size_t gap_b = 0;

    while (pos_a < tokens_a.size() && pos_b < tokens_b.size()) {
        if (tokens_a[pos_a].normalized_hash == tokens_b[pos_b].normalized_hash) {
            ++extended;
            ++pos_a;
            ++pos_b;
            gap_a = 0;
            gap_b = 0;
        } else {
            // Try to resync
            bool resynced = false;

            // Look ahead in both sequences for a match
            for (size_t la = 0; la <= config_.lookahead && pos_a + la < tokens_a.size(); ++la) {
                for (size_t lb = 0; lb <= config_.lookahead && pos_b + lb < tokens_b.size(); ++lb) {
                    if (la == 0 && lb == 0) continue;

                    if (tokens_a[pos_a + la].normalized_hash == tokens_b[pos_b + lb].normalized_hash) {
                        // Check if gap is acceptable
                        if (la <= config_.max_gap && lb <= config_.max_gap) {
                            pos_a += la;
                            pos_b += lb;
                            resynced = true;
                            break;
                        }
                    }
                }
                if (resynced) break;
            }

            if (!resynced) {
                break;  // Can't extend further
            }
        }
    }

    return extended;
}

size_t CloneExtender::extend_backward(
    const std::vector<NormalizedToken>& tokens_a, size_t pos_a,
    const std::vector<NormalizedToken>& tokens_b, size_t pos_b
) const {
    size_t extended = 0;

    while (pos_a > 0 && pos_b > 0) {
        size_t check_a = pos_a - 1;
        size_t check_b = pos_b - 1;

        if (tokens_a[check_a].normalized_hash == tokens_b[check_b].normalized_hash) {
            ++extended;
            --pos_a;
            --pos_b;
        } else {
            // Try to resync backward
            bool resynced = false;

            for (size_t la = 0; la <= config_.lookahead && check_a >= la; ++la) {
                for (size_t lb = 0; lb <= config_.lookahead && check_b >= lb; ++lb) {
                    if (la == 0 && lb == 0) continue;

                    if (tokens_a[check_a - la].normalized_hash == tokens_b[check_b - lb].normalized_hash) {
                        if (la <= config_.max_gap && lb <= config_.max_gap) {
                            pos_a = check_a - la;
                            pos_b = check_b - lb;
                            resynced = true;
                            break;
                        }
                    }
                }
                if (resynced) break;
            }

            if (!resynced) {
                break;
            }
        }
    }

    return extended;
}

ClonePair CloneExtender::extend(
    const ClonePair& pair,
    const TokenizedFile& file_a,
    const TokenizedFile& file_b
) const {
    const auto& tokens_a = file_a.tokens;
    const auto& tokens_b = file_b.tokens;

    // Start positions
    size_t start_a = pair.location_a.token_start;
    size_t start_b = pair.location_b.token_start;
    size_t end_a = start_a + pair.location_a.token_count;
    size_t end_b = start_b + pair.location_b.token_count;

    // Extend backward
    size_t back_ext = extend_backward(tokens_a, start_a, tokens_b, start_b);
    start_a -= back_ext;
    start_b -= back_ext;

    // Extend forward
    size_t fwd_ext = extend_forward(tokens_a, end_a, tokens_b, end_b);
    end_a += fwd_ext;
    end_b += fwd_ext;

    // Calculate new similarity
    float sim = alignment_similarity(
        tokens_a, start_a, end_a - start_a,
        tokens_b, start_b, end_b - start_b,
        config_.max_gap
    );

    // Only accept extension if similarity is above threshold
    if (sim < config_.min_similarity) {
        return pair;  // Return original
    }

    // Create extended pair
    ClonePair extended = pair;
    extended.location_a.token_start = static_cast<uint32_t>(start_a);
    extended.location_a.token_count = static_cast<uint32_t>(end_a - start_a);
    extended.location_b.token_start = static_cast<uint32_t>(start_b);
    extended.location_b.token_count = static_cast<uint32_t>(end_b - start_b);
    extended.similarity = sim;

    // Update line numbers
    if (start_a < tokens_a.size()) {
        extended.location_a.start_line = tokens_a[start_a].line;
    }
    if (end_a > 0 && end_a <= tokens_a.size()) {
        extended.location_a.end_line = tokens_a[end_a - 1].line;
    }
    if (start_b < tokens_b.size()) {
        extended.location_b.start_line = tokens_b[start_b].line;
    }
    if (end_b > 0 && end_b <= tokens_b.size()) {
        extended.location_b.end_line = tokens_b[end_b - 1].line;
    }

    // Determine clone type
    if (sim >= 1.0f) {
        // Check if it's truly Type-1 or Type-2
        bool all_match = true;
        size_t count = std::min(end_a - start_a, end_b - start_b);
        for (size_t i = 0; i < count; ++i) {
            if (tokens_a[start_a + i].original_hash != tokens_b[start_b + i].original_hash) {
                all_match = false;
                break;
            }
        }
        extended.clone_type = all_match ? CloneType::TYPE_1 : CloneType::TYPE_2;
    } else {
        extended.clone_type = CloneType::TYPE_3;
    }

    return extended;
}

std::vector<ClonePair> CloneExtender::extend_all(
    const std::vector<ClonePair>& pairs,
    const std::vector<TokenizedFile>& files,
    const HashIndex& index
) const {
    std::vector<ClonePair> extended_pairs;
    extended_pairs.reserve(pairs.size());

    // Build file lookup
    std::unordered_map<std::string, const TokenizedFile*> file_map;
    for (const auto& file : files) {
        file_map[file.path] = &file;
    }

    for (const auto& pair : pairs) {
        // Get files for this pair
        const std::string& path_a = index.get_file_path(pair.location_a.file_id);
        const std::string& path_b = index.get_file_path(pair.location_b.file_id);

        auto it_a = file_map.find(path_a);
        auto it_b = file_map.find(path_b);

        if (it_a == file_map.end() || it_b == file_map.end()) {
            extended_pairs.push_back(pair);  // Can't extend, keep original
            continue;
        }

        ClonePair extended = extend(pair, *it_a->second, *it_b->second);

        // Only keep if meets minimum size
        if (extended.token_count() >= config_.min_tokens) {
            extended_pairs.push_back(extended);
        }
    }

    return extended_pairs;
}

}  // namespace aegis::similarity
