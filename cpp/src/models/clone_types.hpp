#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include <optional>

namespace aegis::similarity {

/**
 * Token types for normalized code representation.
 * Used to abstract away specific identifiers/values for clone detection.
 */
enum class TokenType : uint8_t {
    IDENTIFIER,      // Variable/function names -> normalized to $ID
    STRING_LITERAL,  // String values -> normalized to $STR
    NUMBER_LITERAL,  // Numeric values -> normalized to $NUM
    KEYWORD,         // Language keywords (if, for, while, def, etc.)
    OPERATOR,        // Operators (+, -, *, /, =, ==, etc.)
    PUNCTUATION,     // Punctuation ({, }, (, ), [, ], etc.)
    TYPE,            // Type names -> normalized to $TYPE
    NEWLINE,         // Logical line separator
    INDENT,          // Indentation (for Python)
    DEDENT,          // Dedentation (for Python)
    UNKNOWN          // Unrecognized token
};

/**
 * String representation of token types for debugging/output.
 */
inline const char* token_type_to_string(const TokenType type) {
    switch (type) {
        case TokenType::IDENTIFIER:     return "IDENTIFIER";
        case TokenType::STRING_LITERAL: return "STRING_LITERAL";
        case TokenType::NUMBER_LITERAL: return "NUMBER_LITERAL";
        case TokenType::KEYWORD:        return "KEYWORD";
        case TokenType::OPERATOR:       return "OPERATOR";
        case TokenType::PUNCTUATION:    return "PUNCTUATION";
        case TokenType::TYPE:           return "TYPE";
        case TokenType::NEWLINE:        return "NEWLINE";
        case TokenType::INDENT:         return "INDENT";
        case TokenType::DEDENT:         return "DEDENT";
        case TokenType::UNKNOWN:        return "UNKNOWN";
    }
    return "UNKNOWN";
}

/**
 * A normalized token from source code.
 * Contains both original and normalized hash for Type-1 vs Type-2 detection.
 */
struct NormalizedToken {
    TokenType type;

    // Hash of the original token value (for Type-1 exact match)
    uint32_t original_hash;

    // Hash of the normalized value (for Type-2 renamed match)
    // e.g., all identifiers hash to the same value
    uint32_t normalized_hash;

    // Source location
    uint32_t line;
    uint16_t column;

    // Original token length (for snippet extraction)
    uint16_t length;

    // Comparison for testing
    bool operator==(const NormalizedToken& other) const {
        return type == other.type &&
               original_hash == other.original_hash &&
               normalized_hash == other.normalized_hash;
    }
};

/**
 * A location in the source code where a hash was found.
 */
struct HashLocation {
    uint32_t file_id;      // Index into a file list
    uint32_t start_line;
    uint32_t end_line;
    uint16_t start_col;
    uint16_t end_col;
    uint32_t token_start;  // Start index in token array
    uint32_t token_count;  // Number of tokens in this region

    // Check if this location overlaps with another
    [[nodiscard]] bool overlaps(const HashLocation& other) const {
        if (file_id != other.file_id) return false;
        return !(end_line < other.start_line || start_line > other.end_line);
    }
};

/**
 * Clone type classification.
 */
enum class CloneType {
    TYPE_1,  // Exact match (ignoring whitespace/comments)
    TYPE_2,  // Renamed identifiers/literals
    TYPE_3   // Modified (lines added/removed)
};

inline const char* clone_type_to_string(CloneType type) {
    switch (type) {
        case CloneType::TYPE_1: return "Type-1";
        case CloneType::TYPE_2: return "Type-2";
        case CloneType::TYPE_3: return "Type-3";
    }
    return "Unknown";
}

/**
 * A pair of code locations identified as clones.
 */
struct ClonePair {
    HashLocation location_a;
    HashLocation location_b;
    CloneType clone_type;
    float similarity;          // 0.0 to 1.0
    uint64_t shared_hash;      // The hash that matched (for debugging)

    // Token count of the cloned region
    [[nodiscard]] uint32_t token_count() const {
        return std::min(location_a.token_count, location_b.token_count);
    }

    // Line count of the cloned region
    [[nodiscard]] uint32_t line_count() const {
        const auto a_lines = location_a.end_line - location_a.start_line + 1;
        const auto b_lines = location_b.end_line - location_b.start_line + 1;
        return std::min(a_lines, b_lines);
    }
};

/**
 * A "hotspot" - a file with high duplication.
 */
struct DuplicationHotspot {
    std::string file_path;
    float duplication_score;   // 0.0 to 1.0 (ratio of duplicated lines)
    uint32_t clone_count;      // Number of clones involving this file
    uint32_t duplicated_lines; // Estimated duplicated lines
    uint32_t total_lines;      // Total lines in file
};

/**
 * Configuration for the similarity detector.
 */
struct DetectorConfig {
    // Rolling hash window size (in tokens)
    size_t window_size = 10;

    // Minimum tokens for a region to be reported as a clone
    size_t min_clone_tokens = 30;

    // Minimum similarity threshold for Type-3 clones (0.0 to 1.0)
    float similarity_threshold = 0.7f;

    // Enable Type-2 detection (normalized identifiers)
    bool detect_type2 = true;

    // Enable Type-3 detection (with gaps)
    bool detect_type3 = false;  // Disabled in Phase 1

    // Maximum gap allowed for Type-3 extension
    size_t max_gap_tokens = 5;

    // Number of threads (0 = auto-detect)
    size_t num_threads = 0;

    // File extensions to analyze
    std::vector<std::string> extensions = {".py"};

    // Patterns to exclude (glob patterns)
    std::vector<std::string> exclude_patterns = {
        "**/node_modules/**",
        "**/__pycache__/**",
        "**/venv/**",
        "**/.git/**",
        "**/_deps/**",           // CMake FetchContent dependencies
        "**/build/**",           // Build directories
        "**/cmake-build-*/**",   // CLion build directories
        "**/vcpkg_installed/**", // vcpkg dependencies
        "**/third_party/**",     // Third-party code
        "**/vendor/**",          // Vendor directories
        "**/external/**"         // External dependencies
    };
};

/**
 * Result of tokenizing a single file.
 */
struct TokenizedFile {
    std::string path;
    std::vector<NormalizedToken> tokens;
    uint32_t total_lines = 0;
    uint32_t code_lines = 0;
    uint32_t blank_lines = 0;
    uint32_t comment_lines = 0;

    [[nodiscard]] bool empty() const { return tokens.empty(); }
};

}  // namespace aegis::similarity
