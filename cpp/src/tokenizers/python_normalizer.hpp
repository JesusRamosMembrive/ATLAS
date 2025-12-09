#pragma once

#include "tokenizers/token_normalizer.hpp"
#include <unordered_set>
#include <regex>

namespace aegis::similarity {

/**
 * Tokenizer and normalizer for Python source code.
 *
 * Handles:
 * - Python keywords (def, class, if, for, while, etc.)
 * - Operators and punctuation
 * - String literals (single, double, triple-quoted, f-strings)
 * - Number literals (int, float, hex, binary, octal)
 * - Comments (# style)
 * - Indentation (significant in Python)
 *
 * Normalization:
 * - Identifiers -> $ID (same normalized hash)
 * - String literals -> $STR
 * - Number literals -> $NUM
 * - Keywords and operators -> preserved (original hash)
 */
class PythonNormalizer : public TokenNormalizer {
public:
    PythonNormalizer();

    TokenizedFile normalize(std::string_view source) override;

    std::string_view language_name() const override {
        return "Python";
    }

    std::vector<std::string> supported_extensions() const override {
        return {".py", ".pyw", ".pyi"};
    }

private:
    // Python keywords
    std::unordered_set<std::string> keywords_;

    // Python built-in types (treated specially for Type-2 detection)
    std::unordered_set<std::string> builtin_types_;

    // Operators and punctuation that should be preserved
    std::unordered_set<std::string> operators_;

    /**
     * Internal tokenization state.
     */
    struct TokenizerState {
        std::string_view source;
        size_t pos = 0;
        uint32_t line = 1;
        uint16_t column = 1;

        // Track indentation for INDENT/DEDENT tokens
        std::vector<size_t> indent_stack = {0};
        bool at_line_start = true;

        bool eof() const { return pos >= source.size(); }
        char peek() const { return eof() ? '\0' : source[pos]; }
        char peek_next() const {
            return (pos + 1 >= source.size()) ? '\0' : source[pos + 1];
        }
        char advance() {
            char c = peek();
            pos++;
            if (c == '\n') {
                line++;
                column = 1;
                at_line_start = true;
            } else {
                column++;
            }
            return c;
        }
        void skip_whitespace_on_line() {
            while (!eof() && (peek() == ' ' || peek() == '\t')) {
                advance();
            }
        }
    };

    // Token parsing methods
    NormalizedToken parse_string(TokenizerState& state);
    NormalizedToken parse_number(TokenizerState& state);
    NormalizedToken parse_identifier_or_keyword(TokenizerState& state);
    NormalizedToken parse_operator(TokenizerState& state);
    void skip_comment(TokenizerState& state);
    std::vector<NormalizedToken> handle_indentation(TokenizerState& state, size_t current_indent);

    // Helper methods
    bool is_identifier_start(char c) const;
    bool is_identifier_char(char c) const;
    bool is_digit(char c) const;
    bool is_hex_digit(char c) const;
    bool is_operator_char(char c) const;
};

}  // namespace aegis::similarity
