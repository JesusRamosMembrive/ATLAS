#pragma once

#include "tokenizers/token_normalizer.hpp"
#include <unordered_set>

namespace aegis::similarity {

/**
 * Tokenizer and normalizer for JavaScript/TypeScript source code.
 *
 * Handles:
 * - ES6+ keywords (let, const, async, await, class, etc.)
 * - TypeScript keywords (interface, type, enum, etc.)
 * - Operators and punctuation
 * - String literals (single, double, template literals)
 * - Number literals (int, float, hex, binary, octal, bigint)
 * - Regular expression literals
 * - Comments (// and multi-line)
 * - JSX/TSX (basic support)
 *
 * Normalization:
 * - Identifiers -> $ID
 * - String literals -> $STR
 * - Number literals -> $NUM
 * - Template literals -> $STR
 * - Keywords and operators -> preserved
 */
class JavaScriptNormalizer : public TokenNormalizer {
public:
    JavaScriptNormalizer();

    TokenizedFile normalize(std::string_view source) override;

    std::string_view language_name() const override {
        return "JavaScript";
    }

    std::vector<std::string> supported_extensions() const override {
        return {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"};
    }

private:
    // JavaScript/ES6+ keywords
    std::unordered_set<std::string> keywords_;

    // TypeScript-specific keywords
    std::unordered_set<std::string> ts_keywords_;

    // Built-in types (for TypeScript)
    std::unordered_set<std::string> builtin_types_;

    // Operators and punctuation
    std::unordered_set<std::string> operators_;

    /**
     * Internal tokenization state.
     */
    struct TokenizerState {
        std::string_view source;
        size_t pos = 0;
        uint32_t line = 1;
        uint16_t column = 1;

        // Track if we might expect a regex (after certain tokens)
        bool may_be_regex = true;

        bool eof() const { return pos >= source.size(); }
        char peek() const { return eof() ? '\0' : source[pos]; }
        char peek_next() const {
            return (pos + 1 >= source.size()) ? '\0' : source[pos + 1];
        }
        char peek_at(size_t offset) const {
            return (pos + offset >= source.size()) ? '\0' : source[pos + offset];
        }
        char advance() {
            char c = peek();
            pos++;
            if (c == '\n') {
                line++;
                column = 1;
            } else {
                column++;
            }
            return c;
        }
    };

    // Token parsing methods
    static NormalizedToken parse_string(TokenizerState& state);
    static NormalizedToken parse_template_literal(TokenizerState& state);
    NormalizedToken parse_number(TokenizerState& state) const;
    NormalizedToken parse_identifier_or_keyword(TokenizerState& state) const;
    static NormalizedToken parse_operator(TokenizerState& state);
    NormalizedToken parse_regex(TokenizerState& state) const;
    static void skip_single_line_comment(TokenizerState& state);
    static void skip_multi_line_comment(TokenizerState& state);

    // Helper methods
    static bool is_identifier_start(char c);
    static bool is_identifier_char(char c);
    static bool is_digit(char c);
    static bool is_hex_digit(char c);
    static bool is_operator_char(char c);
    static bool could_be_regex(TokenType last_type);

    // Operator parsing helpers (extracted from parse_operator to reduce cyclomatic complexity)
    static bool try_match_four_char_operator(TokenizerState& state, std::string& value);
    static bool try_match_three_char_operator(TokenizerState& state, std::string& value);
    static bool try_match_two_char_operator(TokenizerState& state, std::string& value);
    static bool is_punctuation(const std::string& op);

    // Number parsing helpers (reduce cyclomatic complexity of parse_number)
    static bool parse_hex_number(TokenizerState& state, std::string& value);
    static bool parse_binary_number(TokenizerState& state, std::string& value);
    static bool parse_octal_number(TokenizerState& state, std::string& value);
    static void parse_integer_part(TokenizerState& state, std::string& value);
    static void parse_decimal_part(TokenizerState& state, std::string& value);
    static void parse_exponent_part(TokenizerState& state, std::string& value);
    static void skip_bigint_suffix(TokenizerState& state, std::string& value);

    /**
     * Line metrics tracking for code analysis.
     */
    struct LineMetrics {
        uint32_t code_lines = 0;
        uint32_t blank_lines = 0;
        uint32_t comment_lines = 0;
        uint32_t current_line = 0;
        bool line_has_code = false;
        bool line_has_comment = false;
    };

    // Normalize helpers (reduce cyclomatic complexity of normalize)
    static void update_line_metrics(TokenizerState& state, LineMetrics& metrics);
    static bool skip_whitespace(TokenizerState& state, char c);
    static bool process_newline(TokenizerState& state, char c);
    bool process_single_line_comment(TokenizerState& state, char c, LineMetrics& metrics) const;
    bool process_multi_line_comment(TokenizerState& state, char c, LineMetrics& metrics) const;
    bool process_regex(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics);
    static bool process_string(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics);
    static bool process_template_literal(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics);
    bool process_number(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics) const;
    bool process_identifier(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics);
    bool process_operator(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics);
    static void finalize_metrics(const TokenizerState& state, const LineMetrics& metrics,
                                 std::string_view source, TokenizedFile& result);
};

}  // namespace aegis::similarity
