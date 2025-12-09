#pragma once

#include "models/clone_types.hpp"
#include <memory>
#include <string>
#include <string_view>
#include <functional>

namespace aegis::similarity {

/**
 * Abstract base class for language-specific tokenizers.
 *
 * Each language normalizer converts source code into a sequence of
 * NormalizedTokens that can be compared for clone detection.
 *
 * The normalization process:
 * 1. Lexical analysis (split source into tokens)
 * 2. Classification (identify token types)
 * 3. Normalization (replace identifiers/literals with placeholders)
 * 4. Hash computation (compute hash for each token)
 */
class TokenNormalizer {
public:
    virtual ~TokenNormalizer() = default;

    /**
     * Tokenize and normalize source code.
     *
     * @param source The source code to tokenize
     * @return TokenizedFile containing normalized tokens and metadata
     */
    virtual TokenizedFile normalize(std::string_view source) = 0;

    /**
     * Get the language name for this normalizer.
     */
    virtual std::string_view language_name() const = 0;

    /**
     * Get supported file extensions.
     */
    virtual std::vector<std::string> supported_extensions() const = 0;

    /**
     * Check if a file extension is supported.
     */
    bool supports_extension(std::string_view ext) const {
        for (const auto& supported : supported_extensions()) {
            if (ext == supported) return true;
        }
        return false;
    }

protected:
    /**
     * Compute a simple hash for a string.
     * Uses FNV-1a for fast, decent distribution.
     */
    static uint32_t hash_string(std::string_view str) {
        uint32_t hash = 2166136261u;  // FNV offset basis
        for (char c : str) {
            hash ^= static_cast<uint32_t>(c);
            hash *= 16777619u;  // FNV prime
        }
        return hash;
    }

    /**
     * Compute hash for a normalized placeholder.
     * All identifiers get the same hash, all strings get the same hash, etc.
     */
    static uint32_t hash_placeholder(TokenType type) {
        switch (type) {
            case TokenType::IDENTIFIER:     return hash_string("$ID");
            case TokenType::STRING_LITERAL: return hash_string("$STR");
            case TokenType::NUMBER_LITERAL: return hash_string("$NUM");
            case TokenType::TYPE:           return hash_string("$TYPE");
            default:                        return 0;
        }
    }
};

/**
 * Supported languages enumeration.
 */
enum class Language {
    PYTHON,
    JAVASCRIPT,
    TYPESCRIPT,
    CPP,
    C,
    UNKNOWN
};

/**
 * Detect language from file extension.
 */
inline Language detect_language(std::string_view extension) {
    if (extension == ".py" || extension == ".pyw") {
        return Language::PYTHON;
    }
    if (extension == ".js" || extension == ".mjs" || extension == ".cjs") {
        return Language::JAVASCRIPT;
    }
    if (extension == ".ts" || extension == ".tsx") {
        return Language::TYPESCRIPT;
    }
    if (extension == ".cpp" || extension == ".cxx" || extension == ".cc" ||
        extension == ".hpp" || extension == ".hxx" || extension == ".h") {
        return Language::CPP;
    }
    if (extension == ".c") {
        return Language::C;
    }
    return Language::UNKNOWN;
}

/**
 * Get string name of language.
 */
inline const char* language_to_string(Language lang) {
    switch (lang) {
        case Language::PYTHON:     return "Python";
        case Language::JAVASCRIPT: return "JavaScript";
        case Language::TYPESCRIPT: return "TypeScript";
        case Language::CPP:        return "C++";
        case Language::C:          return "C";
        case Language::UNKNOWN:    return "Unknown";
    }
    return "Unknown";
}

/**
 * Factory function to create appropriate normalizer for a language.
 * Returns nullptr if language is not supported.
 */
std::unique_ptr<TokenNormalizer> create_normalizer(Language language);

/**
 * Factory function to create normalizer based on file extension.
 */
std::unique_ptr<TokenNormalizer> create_normalizer_for_file(std::string_view extension);

}  // namespace aegis::similarity
