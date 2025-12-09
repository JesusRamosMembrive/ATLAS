#pragma once

#include "models/clone_types.hpp"
#include "utils/thread_pool.hpp"
#include <unordered_map>
#include <vector>
#include <string>
#include <algorithm>

namespace aegis::similarity {

/**
 * Inverted index mapping rolling hashes to their source locations.
 *
 * This index enables efficient clone detection by:
 * 1. Storing all hash -> location mappings during analysis
 * 2. Finding potential clones by looking up duplicate hashes
 * 3. Merging adjacent clone pairs into larger regions
 */
class HashIndex {
public:
    /**
     * Clear all data from the index.
     */
    void clear();

    /**
     * Register a file and get its ID.
     *
     * @param path The file path
     * @return The assigned file ID
     */
    uint32_t register_file(const std::string& path);

    /**
     * Get the path for a file ID.
     */
    const std::string& get_file_path(uint32_t file_id) const;

    /**
     * Get the number of registered files.
     */
    size_t file_count() const { return file_paths_.size(); }

    /**
     * Add a hash and its location to the index.
     *
     * @param hash The rolling hash value
     * @param location Where this hash was found
     */
    void add_hash(uint64_t hash, const HashLocation& location);

    /**
     * Get all locations for a specific hash.
     */
    const std::vector<HashLocation>* get_locations(uint64_t hash) const;

    /**
     * Get the number of unique hashes in the index.
     */
    size_t hash_count() const { return index_.size(); }

    /**
     * Get total number of locations stored.
     */
    size_t location_count() const;

    /**
     * Find all clone pairs in the index.
     *
     * A clone pair is generated for each pair of locations that share
     * the same hash and don't overlap.
     *
     * @param min_matches Minimum hash matches to consider (default 1)
     * @return Vector of clone pairs
     */
    std::vector<ClonePair> find_clone_pairs(size_t min_matches = 1) const;

    /**
     * Find all clone pairs in the index using parallel processing.
     *
     * Partitions the hash index across multiple threads for faster processing
     * on large codebases.
     *
     * @param pool Thread pool to use for parallel execution
     * @param min_matches Minimum hash matches to consider (default 1)
     * @return Vector of clone pairs
     */
    std::vector<ClonePair> find_clone_pairs_parallel(
        ThreadPool& pool,
        size_t min_matches = 1
    ) const;

    /**
     * Merge adjacent clone pairs into larger clone regions.
     *
     * Adjacent pairs are merged if:
     * - They involve the same two files
     * - Their locations are adjacent or overlapping
     * - The gap between them is small enough
     *
     * @param pairs The clone pairs to merge
     * @param max_gap Maximum gap in tokens to allow merging
     * @return Merged clone pairs representing larger regions
     */
    static std::vector<ClonePair> merge_adjacent_clones(
        std::vector<ClonePair> pairs,
        size_t max_gap = 5
    );

    /**
     * Filter clone pairs by minimum size.
     *
     * @param pairs The clone pairs to filter
     * @param min_tokens Minimum token count
     * @return Filtered pairs
     */
    static std::vector<ClonePair> filter_by_size(
        const std::vector<ClonePair>& pairs,
        size_t min_tokens
    );

    /**
     * Get statistics about the index.
     */
    struct Stats {
        size_t total_files;
        size_t total_hashes;
        size_t total_locations;
        size_t duplicate_hashes;  // Hashes appearing more than once
        size_t max_locations_per_hash;
    };

    Stats get_stats() const;

private:
    // Hash -> list of locations
    std::unordered_map<uint64_t, std::vector<HashLocation>> index_;

    // File ID -> file path
    std::vector<std::string> file_paths_;

    // File path -> file ID (for deduplication)
    std::unordered_map<std::string, uint32_t> path_to_id_;
};

/**
 * Helper class to build HashIndex from tokenized files.
 */
class HashIndexBuilder {
public:
    /**
     * Construct a builder with the specified configuration.
     *
     * @param window_size Rolling hash window size
     */
    explicit HashIndexBuilder(size_t window_size = 10);

    /**
     * Add a tokenized file to the index.
     *
     * @param file The tokenized file
     * @param use_normalized Use normalized hashes (for Type-2 detection)
     */
    void add_file(const TokenizedFile& file, bool use_normalized = true);

    /**
     * Get the built index.
     */
    HashIndex& index() { return index_; }
    const HashIndex& index() const { return index_; }

private:
    size_t window_size_;
    HashIndex index_;
};

}  // namespace aegis::similarity
