#pragma once

#include "models/clone_types.hpp"
#include "models/report.hpp"
#include "core/hash_index.hpp"
#include "tokenizers/token_normalizer.hpp"
#include "utils/thread_pool.hpp"
#include "utils/lru_cache.hpp"
#include <filesystem>
#include <memory>
#include <vector>
#include <map>
#include <optional>

namespace aegis::similarity {

/**
 * Main orchestrator for code similarity detection.
 *
 * This class coordinates the entire analysis pipeline:
 * 1. File discovery
 * 2. Tokenization and normalization
 * 3. Hash computation and indexing
 * 4. Clone pair detection
 * 5. Report generation
 */
class SimilarityDetector {
public:
    /**
     * Construct a detector with the given configuration.
     */
    explicit SimilarityDetector(DetectorConfig config = {});

    /**
     * Analyze a project directory for code clones.
     *
     * @param root Root directory to analyze
     * @return Complete similarity report
     */
    SimilarityReport analyze(const std::filesystem::path& root);

    /**
     * Analyze specific files for code clones.
     *
     * @param files List of file paths to analyze
     * @return Complete similarity report
     */
    SimilarityReport analyze(const std::vector<std::string>& files);

    /**
     * Compare two specific files for similarity.
     *
     * @param file1 First file path
     * @param file2 Second file path
     * @return Similarity report for the two files
     */
    SimilarityReport compare(
        const std::filesystem::path& file1,
        const std::filesystem::path& file2
    );

    /**
     * Get the current configuration.
     */
    const DetectorConfig& config() const { return config_; }

    /**
     * Update configuration.
     */
    void set_config(const DetectorConfig& config) { config_ = config; }

    /**
     * Clear the token cache.
     */
    void clear_cache() const;

    /**
     * Get cache statistics.
     */
    LRUCache<std::string, TokenizedFile>::Stats cache_stats() const;

private:
    DetectorConfig config_;

    // Thread pool for parallel operations
    std::unique_ptr<ThreadPool> thread_pool_;

    // Cache for tokenized files
    std::unique_ptr<LRUCache<std::string, TokenizedFile>> token_cache_;

    // Cached normalizers by language
    std::map<Language, std::unique_ptr<TokenNormalizer>> normalizers_;

    // Mutex for thread-safe normalizer access
    mutable std::mutex normalizer_mutex_;

    // Internal analysis state
    struct AnalysisState {
        HashIndex index;
        std::vector<TokenizedFile> tokenized_files;
        std::map<uint32_t, std::string> sources;  // file_id -> source code
        std::map<uint32_t, size_t> line_counts;   // file_id -> line count

        int64_t tokenize_time_ms = 0;
        int64_t hash_time_ms = 0;
        int64_t match_time_ms = 0;

        // Performance tracking
        size_t total_tokens = 0;         // Total tokens processed
        size_t thread_count = 0;         // Number of threads used
        bool parallel_enabled = false;   // Whether parallel processing was used
    };

    /**
     * Get or create normalizer for a language.
     */
    TokenNormalizer* get_normalizer(Language lang);

    /**
     * Initialize thread pool and cache if needed.
     */
    void ensure_initialized();

    /**
     * Phase 1: Tokenize all files (with parallel support).
     */
    void tokenize_files(
        const std::vector<std::filesystem::path>& files,
        AnalysisState& state
    );

    /**
     * Tokenize a single file (thread-safe).
     */
    std::optional<TokenizedFile> tokenize_single_file(
        const std::filesystem::path& file_path
    );

    /**
     * Phase 2: Build hash index from tokenized files.
     */
    void build_index(AnalysisState& state) const;

    /**
     * Phase 3: Find and filter clone pairs.
     */
    std::vector<ClonePair> find_clones(AnalysisState& state);

    /**
     * Phase 4: Generate report from clone pairs.
     */
    static SimilarityReport generate_report(
        const std::vector<ClonePair>& clones,
        const AnalysisState& state,
        int64_t total_time_ms
    );

    /**
     * Classify clone type based on hash match type.
     */
    CloneType classify_clone(
        const ClonePair& pair,
        const AnalysisState& state
    ) const;
};

}  // namespace aegis::similarity
