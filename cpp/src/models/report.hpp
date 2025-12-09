#pragma once

#include "models/clone_types.hpp"
#include <nlohmann/json.hpp>
#include <string>
#include <vector>
#include <chrono>
#include <map>
#include <set>

namespace aegis::similarity {

/**
 * Sanitize a string to ensure valid UTF-8 for JSON serialization.
 * Replaces invalid UTF-8 sequences with '?'.
 */
inline std::string sanitize_utf8(const std::string& input) {
    std::string result;
    result.reserve(input.size());

    for (size_t i = 0; i < input.size(); ) {
        unsigned char c = static_cast<unsigned char>(input[i]);

        // ASCII (valid single byte)
        if (c < 0x80) {
            // Control characters except tab/newline become spaces
            if (c < 0x20 && c != '\t' && c != '\n' && c != '\r') {
                result += ' ';
            } else {
                result += static_cast<char>(c);
            }
            ++i;
        }
        // Start of 2-byte sequence
        else if ((c & 0xE0) == 0xC0 && i + 1 < input.size()) {
            unsigned char c2 = static_cast<unsigned char>(input[i + 1]);
            if ((c2 & 0xC0) == 0x80) {
                result += input.substr(i, 2);
                i += 2;
            } else {
                result += "?";  // Invalid sequence
                ++i;
            }
        }
        // Start of 3-byte sequence
        else if ((c & 0xF0) == 0xE0 && i + 2 < input.size()) {
            unsigned char c2 = static_cast<unsigned char>(input[i + 1]);
            unsigned char c3 = static_cast<unsigned char>(input[i + 2]);
            if ((c2 & 0xC0) == 0x80 && (c3 & 0xC0) == 0x80) {
                result += input.substr(i, 3);
                i += 3;
            } else {
                result += "?";
                ++i;
            }
        }
        // Start of 4-byte sequence
        else if ((c & 0xF8) == 0xF0 && i + 3 < input.size()) {
            unsigned char c2 = static_cast<unsigned char>(input[i + 1]);
            unsigned char c3 = static_cast<unsigned char>(input[i + 2]);
            unsigned char c4 = static_cast<unsigned char>(input[i + 3]);
            if ((c2 & 0xC0) == 0x80 && (c3 & 0xC0) == 0x80 && (c4 & 0xC0) == 0x80) {
                result += input.substr(i, 4);
                i += 4;
            } else {
                result += "?";
                ++i;
            }
        }
        // Invalid byte
        else {
            result += "?";
            ++i;
        }
    }

    return result;
}

/**
 * Detailed information about a clone location for the report.
 */
struct CloneLocationInfo {
    std::string file;
    uint32_t start_line;
    uint32_t end_line;
    std::string snippet_preview;  // First few lines of the clone

    nlohmann::json to_json() const {
        return {
            {"file", sanitize_utf8(file)},
            {"start_line", start_line},
            {"end_line", end_line},
            {"snippet_preview", sanitize_utf8(snippet_preview)}
        };
    }
};

/**
 * A complete clone entry for the report.
 */
struct CloneEntry {
    std::string id;
    std::string type;  // "Type-1", "Type-2", "Type-3"
    float similarity;
    std::vector<CloneLocationInfo> locations;
    std::string recommendation;

    nlohmann::json to_json() const {
        nlohmann::json locs = nlohmann::json::array();
        for (const auto& loc : locations) {
            locs.push_back(loc.to_json());
        }

        return {
            {"id", id},
            {"type", type},
            {"similarity", similarity},
            {"locations", locs},
            {"recommendation", recommendation}
        };
    }
};

/**
 * Summary statistics for the analysis.
 */
struct ReportSummary {
    size_t files_analyzed = 0;
    size_t total_lines = 0;
    size_t clone_pairs_found = 0;
    std::string estimated_duplication;  // e.g., "12.5%"
    int64_t analysis_time_ms = 0;

    nlohmann::json to_json() const {
        return {
            {"files_analyzed", files_analyzed},
            {"total_lines", total_lines},
            {"clone_pairs_found", clone_pairs_found},
            {"estimated_duplication", estimated_duplication},
            {"analysis_time_ms", analysis_time_ms}
        };
    }
};

/**
 * Timing breakdown for performance analysis.
 */
struct TimingInfo {
    int64_t tokenize_ms = 0;
    int64_t hash_ms = 0;
    int64_t match_ms = 0;
    int64_t total_ms = 0;

    nlohmann::json to_json() const {
        return {
            {"tokenize_ms", tokenize_ms},
            {"hash_ms", hash_ms},
            {"match_ms", match_ms},
            {"total_ms", total_ms}
        };
    }
};

/**
 * Performance metrics for the analysis.
 */
struct PerformanceMetrics {
    double loc_per_second = 0.0;      // Lines of code processed per second
    size_t total_tokens = 0;           // Total tokens processed
    double tokens_per_second = 0.0;    // Tokens processed per second
    size_t files_per_second = 0;       // Files processed per second
    size_t thread_count = 0;           // Number of threads used
    bool parallel_enabled = false;     // Whether parallel processing was used

    nlohmann::json to_json() const {
        return {
            {"loc_per_second", loc_per_second},
            {"total_tokens", total_tokens},
            {"tokens_per_second", tokens_per_second},
            {"files_per_second", files_per_second},
            {"thread_count", thread_count},
            {"parallel_enabled", parallel_enabled}
        };
    }
};

/**
 * Metrics breakdown by category.
 */
struct ReportMetrics {
    std::map<std::string, size_t> by_type;      // Type-1, Type-2, Type-3
    std::map<std::string, size_t> by_language;  // python, javascript, etc.

    nlohmann::json to_json() const {
        return {
            {"by_type", by_type},
            {"by_language", by_language}
        };
    }
};

/**
 * Complete similarity analysis report.
 *
 * This is the main output of the SimilarityDetector, designed to be
 * JSON-serializable and compatible with the Code Map backend.
 */
class SimilarityReport {
public:
    ReportSummary summary;
    std::vector<CloneEntry> clones;
    std::vector<DuplicationHotspot> hotspots;
    ReportMetrics metrics;
    TimingInfo timing;
    PerformanceMetrics performance;

    /**
     * Convert the report to JSON.
     */
    nlohmann::json to_json() const {
        nlohmann::json j;

        j["summary"] = summary.to_json();

        j["clones"] = nlohmann::json::array();
        for (const auto& clone : clones) {
            j["clones"].push_back(clone.to_json());
        }

        j["hotspots"] = nlohmann::json::array();
        for (const auto& hotspot : hotspots) {
            j["hotspots"].push_back({
                {"file", sanitize_utf8(hotspot.file_path)},
                {"duplication_score", hotspot.duplication_score},
                {"clone_count", hotspot.clone_count},
                {"recommendation",
                    hotspot.duplication_score > 0.3
                        ? "High duplication - review for refactoring opportunities"
                        : "Moderate duplication - consider consolidating similar code"}
            });
        }

        j["metrics"] = metrics.to_json();
        j["timing"] = timing.to_json();
        j["performance"] = performance.to_json();

        return j;
    }

    /**
     * Convert to formatted JSON string.
     */
    std::string to_json_string(int indent = 2) const {
        return to_json().dump(indent);
    }

    /**
     * Add a clone pair to the report.
     *
     * @param pair The clone pair
     * @param file_paths Map of file_id to file path
     * @param sources Map of file_id to source code (for snippet extraction)
     */
    void add_clone(
        const ClonePair& pair,
        const std::vector<std::string>& file_paths,
        const std::map<uint32_t, std::string>& sources = {}
    ) {
        CloneEntry entry;
        entry.id = "clone_" + std::to_string(clones.size() + 1);
        entry.type = clone_type_to_string(pair.clone_type);
        entry.similarity = pair.similarity;

        // Location A
        CloneLocationInfo loc_a;
        loc_a.file = pair.location_a.file_id < file_paths.size()
            ? file_paths[pair.location_a.file_id]
            : "unknown";
        loc_a.start_line = pair.location_a.start_line;
        loc_a.end_line = pair.location_a.end_line;
        loc_a.snippet_preview = extract_snippet(
            pair.location_a.file_id,
            pair.location_a.start_line,
            sources
        );
        entry.locations.push_back(loc_a);

        // Location B
        CloneLocationInfo loc_b;
        loc_b.file = pair.location_b.file_id < file_paths.size()
            ? file_paths[pair.location_b.file_id]
            : "unknown";
        loc_b.start_line = pair.location_b.start_line;
        loc_b.end_line = pair.location_b.end_line;
        loc_b.snippet_preview = extract_snippet(
            pair.location_b.file_id,
            pair.location_b.start_line,
            sources
        );
        entry.locations.push_back(loc_b);

        // Generate recommendation
        entry.recommendation = generate_recommendation(pair);

        clones.push_back(entry);

        // Update metrics
        metrics.by_type[entry.type]++;
    }

    /**
     * Calculate hotspots from clone data.
     *
     * A "hotspot" is a file with duplicated code. The duplication_score
     * represents what percentage of the file's lines are involved in clones.
     */
    void calculate_hotspots(
        const std::vector<std::string>& file_paths,
        const std::map<uint32_t, size_t>& file_line_counts
    ) {
        // Track clone counts and unique duplicated line ranges per file
        std::map<uint32_t, size_t> clone_counts;
        // Use a set of line numbers to avoid counting overlapping clones multiple times
        std::map<uint32_t, std::set<uint32_t>> duplicated_line_sets;

        for (const auto& clone : clones) {
            for (const auto& loc : clone.locations) {
                // Find file ID
                for (size_t i = 0; i < file_paths.size(); ++i) {
                    if (file_paths[i] == loc.file) {
                        clone_counts[i]++;
                        // Add each line in the range to the set (deduplicates overlaps)
                        for (uint32_t line = loc.start_line; line <= loc.end_line; ++line) {
                            duplicated_line_sets[i].insert(line);
                        }
                        break;
                    }
                }
            }
        }

        // Create hotspot entries
        hotspots.clear();
        for (const auto& [file_id, count] : clone_counts) {
            DuplicationHotspot hotspot;
            hotspot.file_path = file_id < file_paths.size()
                ? file_paths[file_id]
                : "unknown";
            hotspot.clone_count = static_cast<uint32_t>(count);

            // Count unique duplicated lines (no double-counting)
            auto it_lines = duplicated_line_sets.find(file_id);
            hotspot.duplicated_lines = it_lines != duplicated_line_sets.end()
                ? static_cast<uint32_t>(it_lines->second.size())
                : 0;

            auto it = file_line_counts.find(file_id);
            hotspot.total_lines = it != file_line_counts.end()
                ? static_cast<uint32_t>(it->second)
                : 0;

            // Score is now guaranteed to be 0.0 - 1.0 (0% - 100%)
            hotspot.duplication_score = hotspot.total_lines > 0
                ? static_cast<float>(hotspot.duplicated_lines) / hotspot.total_lines
                : 0.0f;

            hotspots.push_back(hotspot);
        }

        // Sort by duplication score (highest first)
        std::sort(hotspots.begin(), hotspots.end(),
            [](const auto& a, const auto& b) {
                return a.duplication_score > b.duplication_score;
            });
    }

    /**
     * Finalize the report with summary calculations.
     */
    void finalize(
        size_t files_analyzed,
        size_t total_lines,
        int64_t analysis_time_ms
    ) {
        finalize_with_perf(files_analyzed, total_lines, analysis_time_ms, 0, 0, false);
    }

    /**
     * Finalize the report with summary and performance metrics.
     *
     * @param files_analyzed Number of files analyzed
     * @param total_lines Total lines of code processed
     * @param analysis_time_ms Total analysis time in milliseconds
     * @param total_tokens Total tokens processed
     * @param thread_count Number of threads used (0 = sequential)
     * @param parallel_enabled Whether parallel processing was enabled
     */
    void finalize_with_perf(
        size_t files_analyzed,
        size_t total_lines,
        int64_t analysis_time_ms,
        size_t total_tokens,
        size_t thread_count,
        bool parallel_enabled
    ) {
        summary.files_analyzed = files_analyzed;
        summary.total_lines = total_lines;
        summary.clone_pairs_found = clones.size();
        summary.analysis_time_ms = analysis_time_ms;

        // Calculate estimated duplication
        size_t duplicated_lines = 0;
        for (const auto& hotspot : hotspots) {
            duplicated_lines += hotspot.duplicated_lines;
        }

        if (total_lines > 0) {
            double pct = 100.0 * duplicated_lines / total_lines;
            char buf[32];
            snprintf(buf, sizeof(buf), "%.1f%%", pct);
            summary.estimated_duplication = buf;
        } else {
            summary.estimated_duplication = "0.0%";
        }

        timing.total_ms = analysis_time_ms;

        // Calculate performance metrics
        performance.total_tokens = total_tokens;
        performance.thread_count = thread_count;
        performance.parallel_enabled = parallel_enabled;

        if (analysis_time_ms > 0) {
            double seconds = analysis_time_ms / 1000.0;
            performance.loc_per_second = total_lines / seconds;
            performance.tokens_per_second = total_tokens / seconds;
            performance.files_per_second = static_cast<size_t>(files_analyzed / seconds);
        }
    }

private:
    std::string extract_snippet(
        uint32_t file_id,
        uint32_t start_line,
        const std::map<uint32_t, std::string>& sources
    ) {
        auto it = sources.find(file_id);
        if (it == sources.end()) {
            return "...";
        }

        const auto& source = it->second;
        std::vector<std::string> lines;

        // Split into lines
        size_t pos = 0;
        uint32_t line_num = 1;
        while (pos < source.size()) {
            size_t end = source.find('\n', pos);
            if (end == std::string::npos) end = source.size();

            if (line_num >= start_line && line_num < start_line + 3) {
                std::string line = source.substr(pos, end - pos);
                // Truncate long lines
                if (line.size() > 60) {
                    line = line.substr(0, 57) + "...";
                }
                lines.push_back(line);
            }

            if (line_num >= start_line + 2) break;

            pos = end + 1;
            line_num++;
        }

        if (lines.empty()) {
            return "...";
        }

        std::string result;
        for (size_t i = 0; i < lines.size(); ++i) {
            if (i > 0) result += "\n";
            result += lines[i];
        }

        // Sanitize to ensure valid UTF-8 for JSON
        return sanitize_utf8(result);
    }

    std::string generate_recommendation(const ClonePair& pair) {
        switch (pair.clone_type) {
            case CloneType::TYPE_1:
                return "Exact duplicate found - consider extracting to shared function";
            case CloneType::TYPE_2:
                return "Similar code with renamed variables - consider parameterizing";
            case CloneType::TYPE_3:
                return "Modified clone detected - review for potential abstraction";
            default:
                return "Review for refactoring opportunities";
        }
    }
};

}  // namespace aegis::similarity
