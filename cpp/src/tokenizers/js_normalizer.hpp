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
    static bool is_hex_digit(char c) ;
    static bool is_operator_char(char c) ;
    static bool could_be_regex(TokenType last_type) ;
};

}  // namespace aegis::similarity
