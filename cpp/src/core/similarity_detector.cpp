#include "core/similarity_detector.hpp"
#include "core/clone_extender.hpp"
#include "utils/file_utils.hpp"
#include "tokenizers/python_normalizer.hpp"
#include <chrono>
#include <algorithm>
#include <mutex>

namespace aegis::similarity {

// Default cache capacity (number of files)
constexpr size_t DEFAULT_CACHE_CAPACITY = 1000;

SimilarityDetector::SimilarityDetector(DetectorConfig config)
    : config_(std::move(config))
{
}

void SimilarityDetector::ensure_initialized() {
    if (!thread_pool_) {
        size_t num_threads = config_.num_threads;
        if (num_threads == 0) {
            num_threads = std::thread::hardware_concurrency();
            if (num_threads == 0) num_threads = 4;
        }
        thread_pool_ = std::make_unique<ThreadPool>(num_threads);
    }

    if (!token_cache_) {
        token_cache_ = std::make_unique<LRUCache<std::string, TokenizedFile>>(DEFAULT_CACHE_CAPACITY);
    }
}

void SimilarityDetector::clear_cache() const
{
    if (token_cache_) {
        token_cache_->clear();
    }
}

LRUCache<std::string, TokenizedFile>::Stats SimilarityDetector::cache_stats() const {
    if (token_cache_) {
        return token_cache_->get_stats();
    }
    return {};
}

TokenNormalizer* SimilarityDetector::get_normalizer(const Language lang) {
    std::lock_guard<std::mutex> lock(normalizer_mutex_);

    auto it = normalizers_.find(lang);
    if (it != normalizers_.end()) {
        return it->second.get();
    }

    auto normalizer = create_normalizer(lang);
    if (!normalizer) {
        return nullptr;
    }

    auto* ptr = normalizer.get();
    normalizers_[lang] = std::move(normalizer);
    return ptr;
}

std::optional<TokenizedFile> SimilarityDetector::tokenize_single_file(
    const std::filesystem::path& file_path
) {
    // Detect language
    const auto ext = FileUtils::get_extension(file_path);
    const auto lang = detect_language(ext);

    auto* normalizer = get_normalizer(lang);
    if (!normalizer) {
        return std::nullopt;  // Unsupported language
    }

    // Read file
    const auto source = FileUtils::read_file(file_path);
    if (!source) {
        return std::nullopt;  // Read failed
    }

    // Tokenize
    auto tokenized = normalizer->normalize(*source);
    tokenized.path = file_path.string();

    return tokenized;
}

SimilarityReport SimilarityDetector::analyze(const std::filesystem::path& root) {
    const auto start_time = std::chrono::high_resolution_clock::now();

    // Initialize thread pool and cache
    ensure_initialized();

    // Find files
    const auto files = FileUtils::find_files(
        root,
        config_.extensions,
        config_.exclude_patterns
    );

    if (files.empty()) {
        SimilarityReport empty_report;
        empty_report.finalize(0, 0, 0);
        return empty_report;
    }

    // Run analysis
    AnalysisState state;
    tokenize_files(files, state);
    build_index(state);
    const auto clones = find_clones(state);

    const auto end_time = std::chrono::high_resolution_clock::now();
    const auto total_time = std::chrono::duration_cast<std::chrono::milliseconds>(
        end_time - start_time
    ).count();

    return generate_report(clones, state, total_time);
}

SimilarityReport SimilarityDetector::analyze(const std::vector<std::string>& file_paths) {
    const auto start_time = std::chrono::high_resolution_clock::now();

    // Initialize thread pool and cache
    ensure_initialized();

    std::vector<std::filesystem::path> files;
    files.reserve(file_paths.size());
    for (const auto& path : file_paths) {
        if (std::filesystem::exists(path)) {
            files.emplace_back(path);
        }
    }

    if (files.empty()) {
        SimilarityReport empty_report;
        empty_report.finalize(0, 0, 0);
        return empty_report;
    }

    AnalysisState state;
    tokenize_files(files, state);
    build_index(state);
    const auto clones = find_clones(state);

    const auto end_time = std::chrono::high_resolution_clock::now();
    const auto total_time = std::chrono::duration_cast<std::chrono::milliseconds>(
        end_time - start_time
    ).count();

    return generate_report(clones, state, total_time);
}

SimilarityReport SimilarityDetector::compare(
    const std::filesystem::path& file1,
    const std::filesystem::path& file2
) {
    return analyze({file1.string(), file2.string()});
}

void SimilarityDetector::tokenize_files(
    const std::vector<std::filesystem::path>& files,
    AnalysisState& state
) {
    const auto start = std::chrono::high_resolution_clock::now();

    // Track parallel processing info
    const bool use_parallel = files.size() >= 4 && thread_pool_;
    state.parallel_enabled = use_parallel;
    state.thread_count = use_parallel ? thread_pool_->size() : 1;

    // For small file sets, use sequential processing
    if (!use_parallel) {
        for (const auto& file_path : files) {
            auto tokenized = tokenize_single_file(file_path);
            if (!tokenized) continue;

            // Register file and store data
            auto source = FileUtils::read_file(file_path);
            if (!source) continue;

            uint32_t file_id = state.index.register_file(tokenized->path);
            state.sources[file_id] = std::move(*source);
            state.line_counts[file_id] = tokenized->total_lines;
            state.tokenized_files.push_back(std::move(*tokenized));
        }
    } else {
        // Parallel tokenization for larger file sets
        std::mutex state_mutex;
        std::vector<std::pair<TokenizedFile, std::string>> results;
        results.reserve(files.size());

        thread_pool_->parallel_for(0, files.size(), [&](size_t i) {
            const auto& file_path = files[i];

            auto tokenized = tokenize_single_file(file_path);
            if (!tokenized) return;

            auto source = FileUtils::read_file(file_path);
            if (!source) return;

            std::lock_guard<std::mutex> lock(state_mutex);
            results.emplace_back(std::move(*tokenized), std::move(*source));
        });

        // Register all files (sequential to maintain consistent IDs)
        for (auto& [tokenized, source] : results) {
            uint32_t file_id = state.index.register_file(tokenized.path);
            state.sources[file_id] = std::move(source);
            state.line_counts[file_id] = tokenized.total_lines;
            state.tokenized_files.push_back(std::move(tokenized));
        }
    }

    // Calculate total tokens processed
    state.total_tokens = 0;
    for (const auto& file : state.tokenized_files) {
        state.total_tokens += file.tokens.size();
    }

    const auto end = std::chrono::high_resolution_clock::now();
    state.tokenize_time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        end - start
    ).count();
}

void SimilarityDetector::build_index(AnalysisState& state) const
{
    auto start = std::chrono::high_resolution_clock::now();

    // Use existing state.index to preserve file_id mappings from tokenize_files
    // This ensures line_counts keys match file_paths indices
    HashIndexBuilder builder(state.index, config_.window_size);

    for (const auto& file : state.tokenized_files) {
        builder.add_file(file, config_.detect_type2);
    }

    // Note: builder uses state.index directly, no need to move

    auto end = std::chrono::high_resolution_clock::now();
    state.hash_time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        end - start
    ).count();
}

std::vector<ClonePair> SimilarityDetector::find_clones(AnalysisState& state) {
    const auto start = std::chrono::high_resolution_clock::now();

    // Find raw clone pairs - use a parallel version for larger workloads
    std::vector<ClonePair> pairs;
    if (state.parallel_enabled && thread_pool_) {
        pairs = state.index.find_clone_pairs_parallel(*thread_pool_);
    } else {
        pairs = state.index.find_clone_pairs();
    }

    // Merge adjacent pairs
    pairs = HashIndex::merge_adjacent_clones(pairs, 5);

    // Filter by minimum size
    pairs = HashIndex::filter_by_size(pairs, config_.min_clone_tokens);

    // Classify clone types (Type-1 vs Type-2)
    for (auto& pair : pairs) {
        pair.clone_type = classify_clone(pair, state);
    }

    // Extend clones for Type-3 detection if enabled
    if (config_.detect_type3) {
        CloneExtender::Config ext_config;
        ext_config.max_gap = config_.max_gap_tokens;
        ext_config.min_similarity = config_.similarity_threshold;
        ext_config.min_tokens = config_.min_clone_tokens;
        ext_config.lookahead = 10;

        CloneExtender extender(ext_config);
        pairs = extender.extend_all(pairs, state.tokenized_files, state.index);
    }

    // Sort by size (largest first)
    std::ranges::sort(pairs, [](const auto& a, const auto& b) {
        return a.token_count() > b.token_count();
    });

    const auto end = std::chrono::high_resolution_clock::now();
    state.match_time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        end - start
    ).count();

    return pairs;
}

SimilarityReport SimilarityDetector::generate_report(
    const std::vector<ClonePair>& clones,
    const AnalysisState& state,
    const int64_t total_time_ms
) {
    SimilarityReport report;

    // Get file paths
    std::vector<std::string> file_paths;
    for (size_t i = 0; i < state.index.file_count(); ++i) {
        file_paths.push_back(state.index.get_file_path(static_cast<uint32_t>(i)));
    }

    // Add clones to the report
    for (const auto& pair : clones) {
        report.add_clone(pair, file_paths, state.sources);
    }

    // Calculate metrics by language
    for (const auto& file : state.tokenized_files) {
        auto ext = FileUtils::get_extension(file.path);
        const auto lang = detect_language(ext);
        std::string lang_name = language_to_string(lang);

        // Count clones involving this file
        for (const auto& clone : clones) {
            const auto file_id_a = clone.location_a.file_id;

            if (auto file_id_b = clone.location_b.file_id; state.index.get_file_path(file_id_a) == file.path ||
                state.index.get_file_path(file_id_b) == file.path) {
                report.metrics.by_language[lang_name]++;
            }
        }
    }

    // Calculate hotspots
    report.calculate_hotspots(file_paths, state.line_counts);

    // Calculate totals
    size_t total_lines = 0;
    for (const auto& file : state.tokenized_files) {
        total_lines += file.total_lines;
    }

    // Set timing
    report.timing.tokenize_ms = state.tokenize_time_ms;
    report.timing.hash_ms = state.hash_time_ms;
    report.timing.match_ms = state.match_time_ms;

    // Finalize with performance metrics
    report.finalize_with_perf(
        state.tokenized_files.size(),
        total_lines,
        total_time_ms,
        state.total_tokens,
        state.thread_count,
        state.parallel_enabled
    );

    return report;
}

CloneType SimilarityDetector::classify_clone(
    const ClonePair& pair,
    const AnalysisState& state
) const
{
    // Type-2 detection: compare ALL original hashes in the cloned regions
    // - Type-1: ALL original hashes match (exact duplicate after whitespace/comment removal)
    // - Type-2: original hashes differ but normalized matched (renamed identifiers/literals)
    // - Type-3: similarity-based match (not implemented yet)

    if (!config_.detect_type2) {
        return CloneType::TYPE_1;  // Fallback if Type-2 detection disabled
    }

    // Find the tokenized files for both locations
    const TokenizedFile* file_a = nullptr;
    const TokenizedFile* file_b = nullptr;

    for (const auto& file : state.tokenized_files) {
        if (state.index.get_file_path(pair.location_a.file_id) == file.path) {
            file_a = &file;
        }
        if (state.index.get_file_path(pair.location_b.file_id) == file.path) {
            file_b = &file;
        }
    }

    if (!file_a || !file_b) {
        return CloneType::TYPE_1;  // Can't determine, default to Type-1
    }

    // Get token ranges
    const size_t start_a = pair.location_a.token_start;
    const size_t count_a = pair.location_a.token_count;
    const size_t start_b = pair.location_b.token_start;
    const size_t count_b = pair.location_b.token_count;

    // Bounds check
    if (start_a + count_a > file_a->tokens.size() ||
        start_b + count_b > file_b->tokens.size()) {
        return CloneType::TYPE_1;
    }

    // If token counts differ, likely Type-2 or structural difference
    if (count_a != count_b) {
        return CloneType::TYPE_2;
    }

    // Compare ALL tokens (not just normalizable ones)
    // Type-1 requires ALL original hashes to match
    bool all_original_match = true;

    for (size_t i = 0; i < count_a; ++i) {
        const auto& tok_a = file_a->tokens[start_a + i];

        // Check if original hashes differ
        if (const auto& tok_b = file_b->tokens[start_b + i]; tok_a.original_hash != tok_b.original_hash) {
            all_original_match = false;
            // This is a normalizable token difference (potential Type-2)
            // We already know normalized hashes match, so this must be
            // a renamed identifier, string, number, or type
            if (tok_a.type == TokenType::IDENTIFIER ||
                tok_a.type == TokenType::STRING_LITERAL ||
                tok_a.type == TokenType::NUMBER_LITERAL ||
                tok_a.type == TokenType::TYPE) {
                // Type-2 clone confirmed - different originals but same normalized
            }
        }
    }

    // Type-1: All original hashes match exactly
    // Type-2: Some normalizable tokens differ (but normalized matched, hence clone detected)
    if (all_original_match) {
        return CloneType::TYPE_1;  // Exact match
    } else {
        return CloneType::TYPE_2;  // Renamed/modified normalizable tokens
    }
}

}  // namespace aegis::similarity
