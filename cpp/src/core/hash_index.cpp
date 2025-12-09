#include "core/hash_index.hpp"
#include "core/rolling_hash.hpp"
#include <algorithm>
#include <set>
#include <mutex>

namespace aegis::similarity {

void HashIndex::clear() {
    index_.clear();
    file_paths_.clear();
    path_to_id_.clear();
}

uint32_t HashIndex::register_file(const std::string& path) {
    auto it = path_to_id_.find(path);
    if (it != path_to_id_.end()) {
        return it->second;
    }

    uint32_t id = static_cast<uint32_t>(file_paths_.size());
    file_paths_.push_back(path);
    path_to_id_[path] = id;
    return id;
}

const std::string& HashIndex::get_file_path(uint32_t file_id) const {
    static const std::string empty;
    if (file_id >= file_paths_.size()) {
        return empty;
    }
    return file_paths_[file_id];
}

void HashIndex::add_hash(uint64_t hash, const HashLocation& location) {
    index_[hash].push_back(location);
}

const std::vector<HashLocation>* HashIndex::get_locations(uint64_t hash) const {
    auto it = index_.find(hash);
    if (it == index_.end()) {
        return nullptr;
    }
    return &it->second;
}

size_t HashIndex::location_count() const {
    size_t count = 0;
    for (const auto& [hash, locations] : index_) {
        count += locations.size();
    }
    return count;
}

std::vector<ClonePair> HashIndex::find_clone_pairs(size_t min_matches) const {
    std::vector<ClonePair> results;

    for (const auto& [hash, locations] : index_) {
        // Skip hashes that don't appear multiple times
        if (locations.size() < 2) {
            continue;
        }

        // Generate pairs from all combinations
        for (size_t i = 0; i < locations.size(); ++i) {
            for (size_t j = i + 1; j < locations.size(); ++j) {
                const auto& loc_a = locations[i];
                const auto& loc_b = locations[j];

                // Skip self-overlapping matches (same file, overlapping region)
                if (loc_a.file_id == loc_b.file_id && loc_a.overlaps(loc_b)) {
                    continue;
                }

                ClonePair pair;
                pair.location_a = loc_a;
                pair.location_b = loc_b;
                pair.clone_type = CloneType::TYPE_1;  // Initial classification
                pair.similarity = 1.0f;  // Exact match
                pair.shared_hash = hash;

                results.push_back(pair);
            }
        }
    }

    return results;
}

std::vector<ClonePair> HashIndex::find_clone_pairs_parallel(
    ThreadPool& pool,
    size_t min_matches
) const {
    // Collect all hashes with multiple locations into a vector for partitioning
    std::vector<std::pair<uint64_t, const std::vector<HashLocation>*>> work_items;
    work_items.reserve(index_.size());

    for (const auto& [hash, locations] : index_) {
        if (locations.size() >= 2) {
            work_items.emplace_back(hash, &locations);
        }
    }

    // For small workloads, use sequential processing
    if (work_items.size() < 100 || pool.size() <= 1) {
        return find_clone_pairs(min_matches);
    }

    // Thread-local results to avoid contention
    std::vector<std::vector<ClonePair>> thread_results(pool.size());
    std::mutex results_mutex;

    // Process work items in parallel
    pool.parallel_for(0, work_items.size(), [&](size_t idx) {
        const auto& [hash, locations_ptr] = work_items[idx];
        const auto& locations = *locations_ptr;

        std::vector<ClonePair> local_results;

        // Generate pairs from all combinations
        for (size_t i = 0; i < locations.size(); ++i) {
            for (size_t j = i + 1; j < locations.size(); ++j) {
                const auto& loc_a = locations[i];
                const auto& loc_b = locations[j];

                // Skip self-overlapping matches
                if (loc_a.file_id == loc_b.file_id && loc_a.overlaps(loc_b)) {
                    continue;
                }

                ClonePair pair;
                pair.location_a = loc_a;
                pair.location_b = loc_b;
                pair.clone_type = CloneType::TYPE_1;
                pair.similarity = 1.0f;
                pair.shared_hash = hash;

                local_results.push_back(pair);
            }
        }

        // Merge local results into thread-specific bucket
        if (!local_results.empty()) {
            size_t thread_idx = idx % pool.size();
            std::lock_guard<std::mutex> lock(results_mutex);
            auto& bucket = thread_results[thread_idx];
            bucket.insert(bucket.end(), local_results.begin(), local_results.end());
        }
    });

    // Merge all thread results
    size_t total_size = 0;
    for (const auto& bucket : thread_results) {
        total_size += bucket.size();
    }

    std::vector<ClonePair> results;
    results.reserve(total_size);

    for (auto& bucket : thread_results) {
        results.insert(results.end(),
                      std::make_move_iterator(bucket.begin()),
                      std::make_move_iterator(bucket.end()));
    }

    return results;
}

std::vector<ClonePair> HashIndex::merge_adjacent_clones(
    std::vector<ClonePair> pairs,
    size_t max_gap
) {
    if (pairs.empty()) {
        return pairs;
    }

    // Sort pairs by file pair and location
    std::sort(pairs.begin(), pairs.end(), [](const ClonePair& a, const ClonePair& b) {
        // First by file pair (normalized so smaller file_id is always first)
        auto a_file_min = std::min(a.location_a.file_id, a.location_b.file_id);
        auto a_file_max = std::max(a.location_a.file_id, a.location_b.file_id);
        auto b_file_min = std::min(b.location_a.file_id, b.location_b.file_id);
        auto b_file_max = std::max(b.location_a.file_id, b.location_b.file_id);

        if (a_file_min != b_file_min) return a_file_min < b_file_min;
        if (a_file_max != b_file_max) return a_file_max < b_file_max;

        // Then by start position in first file
        return a.location_a.token_start < b.location_a.token_start;
    });

    std::vector<ClonePair> merged;
    ClonePair current = pairs[0];

    for (size_t i = 1; i < pairs.size(); ++i) {
        const auto& next = pairs[i];

        // Check if same file pair
        bool same_files =
            (current.location_a.file_id == next.location_a.file_id &&
             current.location_b.file_id == next.location_b.file_id) ||
            (current.location_a.file_id == next.location_b.file_id &&
             current.location_b.file_id == next.location_a.file_id);

        if (!same_files) {
            merged.push_back(current);
            current = next;
            continue;
        }

        // Normalize so we compare same-direction locations
        HashLocation curr_a = current.location_a;
        HashLocation curr_b = current.location_b;
        HashLocation next_a = next.location_a;
        HashLocation next_b = next.location_b;

        if (current.location_a.file_id != next.location_a.file_id) {
            std::swap(next_a, next_b);
        }

        // Check if adjacent (with max_gap tolerance)
        uint32_t curr_end_a = curr_a.token_start + curr_a.token_count;
        uint32_t curr_end_b = curr_b.token_start + curr_b.token_count;

        bool adjacent_a = next_a.token_start <= curr_end_a + max_gap &&
                          next_a.token_start >= curr_a.token_start;
        bool adjacent_b = next_b.token_start <= curr_end_b + max_gap &&
                          next_b.token_start >= curr_b.token_start;

        if (adjacent_a && adjacent_b) {
            // Merge: extend current to include next
            uint32_t new_end_a = std::max(curr_end_a,
                next_a.token_start + next_a.token_count);
            uint32_t new_end_b = std::max(curr_end_b,
                next_b.token_start + next_b.token_count);

            current.location_a.token_count = new_end_a - current.location_a.token_start;
            current.location_b.token_count = new_end_b - current.location_b.token_start;

            // Update line ranges
            current.location_a.end_line = std::max(curr_a.end_line, next_a.end_line);
            current.location_b.end_line = std::max(curr_b.end_line, next_b.end_line);
        } else {
            merged.push_back(current);
            current = next;
        }
    }

    merged.push_back(current);
    return merged;
}

std::vector<ClonePair> HashIndex::filter_by_size(
    const std::vector<ClonePair>& pairs,
    size_t min_tokens
) {
    std::vector<ClonePair> filtered;
    filtered.reserve(pairs.size());

    for (const auto& pair : pairs) {
        if (pair.token_count() >= min_tokens) {
            filtered.push_back(pair);
        }
    }

    return filtered;
}

HashIndex::Stats HashIndex::get_stats() const {
    Stats stats{};
    stats.total_files = file_paths_.size();
    stats.total_hashes = index_.size();
    stats.total_locations = 0;
    stats.duplicate_hashes = 0;
    stats.max_locations_per_hash = 0;

    for (const auto& [hash, locations] : index_) {
        stats.total_locations += locations.size();
        if (locations.size() > 1) {
            stats.duplicate_hashes++;
        }
        stats.max_locations_per_hash = std::max(
            stats.max_locations_per_hash,
            locations.size()
        );
    }

    return stats;
}

// =============================================================================
// HashIndexBuilder
// =============================================================================

HashIndexBuilder::HashIndexBuilder(size_t window_size)
    : window_size_(window_size)
{
}

void HashIndexBuilder::add_file(const TokenizedFile& file, bool use_normalized) {
    if (file.tokens.empty()) {
        return;
    }

    uint32_t file_id = index_.register_file(file.path);

    // Extract hash values from tokens
    std::vector<uint64_t> token_hashes;
    token_hashes.reserve(file.tokens.size());

    for (const auto& token : file.tokens) {
        // Skip structural tokens that shouldn't participate in similarity
        if (token.type == TokenType::NEWLINE ||
            token.type == TokenType::INDENT ||
            token.type == TokenType::DEDENT) {
            continue;
        }

        uint64_t hash = use_normalized ? token.normalized_hash : token.original_hash;
        token_hashes.push_back(hash);
    }

    if (token_hashes.size() < window_size_) {
        return;  // File too small
    }

    // Compute rolling hashes and add to index
    auto window_hashes = HashSequence::compute_all(token_hashes, window_size_);

    // Map token index (excluding structural) back to original token
    size_t non_structural_idx = 0;
    std::vector<size_t> token_mapping;
    for (size_t i = 0; i < file.tokens.size(); ++i) {
        const auto& token = file.tokens[i];
        if (token.type != TokenType::NEWLINE &&
            token.type != TokenType::INDENT &&
            token.type != TokenType::DEDENT) {
            token_mapping.push_back(i);
        }
    }

    for (const auto& [pos, hash] : window_hashes) {
        // Map position back to original token array
        size_t orig_start = token_mapping[pos];
        size_t orig_end = token_mapping[std::min(pos + window_size_ - 1,
                                                  token_mapping.size() - 1)];

        HashLocation loc;
        loc.file_id = file_id;
        loc.start_line = file.tokens[orig_start].line;
        loc.end_line = file.tokens[orig_end].line;
        loc.start_col = file.tokens[orig_start].column;
        loc.end_col = file.tokens[orig_end].column + file.tokens[orig_end].length;
        loc.token_start = static_cast<uint32_t>(pos);
        loc.token_count = static_cast<uint32_t>(window_size_);

        index_.add_hash(hash, loc);
    }
}

}  // namespace aegis::similarity
