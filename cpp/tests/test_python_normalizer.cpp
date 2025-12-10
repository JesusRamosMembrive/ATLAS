#include <gtest/gtest.h>
#include "tokenizers/python_normalizer.hpp"

using namespace aegis::similarity;

class PythonNormalizerTest : public ::testing::Test {
protected:
    PythonNormalizer normalizer;
};

// =============================================================================
// Basic Functionality Tests
// =============================================================================

TEST_F(PythonNormalizerTest, LanguageName) {
    EXPECT_EQ(normalizer.language_name(), "Python");
}

TEST_F(PythonNormalizerTest, SupportedExtensions) {
    EXPECT_TRUE(normalizer.supports_extension(".py"));
    EXPECT_TRUE(normalizer.supports_extension(".pyw"));
    EXPECT_TRUE(normalizer.supports_extension(".pyi"));
    EXPECT_FALSE(normalizer.supports_extension(".js"));
    EXPECT_FALSE(normalizer.supports_extension(".cpp"));
}

TEST_F(PythonNormalizerTest, EmptySource) {
    auto result = normalizer.normalize("");
    EXPECT_TRUE(result.tokens.empty());
    EXPECT_EQ(result.code_lines, 0);
}

// =============================================================================
// Keyword Tests
// =============================================================================

TEST_F(PythonNormalizerTest, RecognizesKeywords) {
    auto result = normalizer.normalize("def if else for while class return");

    // Filter to just keywords
    std::vector<NormalizedToken> keywords;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            keywords.push_back(tok);
        }
    }

    EXPECT_EQ(keywords.size(), 7);
    for (const auto& tok : keywords) {
        EXPECT_EQ(tok.type, TokenType::KEYWORD);
        // Keywords should have same original and normalized hash
        EXPECT_EQ(tok.original_hash, tok.normalized_hash);
    }
}

TEST_F(PythonNormalizerTest, KeywordsPreserveOriginalHash) {
    auto result1 = normalizer.normalize("def");
    auto result2 = normalizer.normalize("def");

    ASSERT_FALSE(result1.tokens.empty());
    ASSERT_FALSE(result2.tokens.empty());

    auto& tok1 = result1.tokens[0];
    auto& tok2 = result2.tokens[0];

    EXPECT_EQ(tok1.original_hash, tok2.original_hash);
    EXPECT_EQ(tok1.normalized_hash, tok2.normalized_hash);
}

// =============================================================================
// Identifier Tests
// =============================================================================

TEST_F(PythonNormalizerTest, RecognizesIdentifiers) {
    auto result = normalizer.normalize("foo bar_baz _private __dunder__ CamelCase");

    std::vector<NormalizedToken> identifiers;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::IDENTIFIER) {
            identifiers.push_back(tok);
        }
    }

    EXPECT_EQ(identifiers.size(), 5);
}

TEST_F(PythonNormalizerTest, IdentifiersNormalizedToSameHash) {
    auto result = normalizer.normalize("foo bar completely_different_name x");

    std::vector<NormalizedToken> identifiers;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::IDENTIFIER) {
            identifiers.push_back(tok);
        }
    }

    ASSERT_EQ(identifiers.size(), 4);

    // All identifiers should have the same normalized hash
    uint32_t normalized = identifiers[0].normalized_hash;
    for (const auto& tok : identifiers) {
        EXPECT_EQ(tok.normalized_hash, normalized);
    }

    // But different original hashes
    EXPECT_NE(identifiers[0].original_hash, identifiers[1].original_hash);
}

// =============================================================================
// String Literal Tests
// =============================================================================

TEST_F(PythonNormalizerTest, ParsesSingleQuotedStrings) {
    auto result = normalizer.normalize("'hello world'");

    auto strings = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) strings++;
    }
    EXPECT_EQ(strings, 1);
}

TEST_F(PythonNormalizerTest, ParsesDoubleQuotedStrings) {
    auto result = normalizer.normalize("\"hello world\"");

    auto strings = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) strings++;
    }
    EXPECT_EQ(strings, 1);
}

TEST_F(PythonNormalizerTest, ParsesTripleQuotedStrings) {
    // Use assignment context so the triple-quoted string is NOT treated as a docstring
    auto result = normalizer.normalize("x = '''multi\nline\nstring'''");

    auto strings = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) strings++;
    }
    EXPECT_EQ(strings, 1);
}

TEST_F(PythonNormalizerTest, StringsNormalizedToSameHash) {
    // Use assignment context so strings are not treated as docstrings
    auto result = normalizer.normalize("x = 'short'\ny = \"longer string here\"\nz = '''triple'''");

    std::vector<NormalizedToken> strings;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            strings.push_back(tok);
        }
    }

    ASSERT_EQ(strings.size(), 3);

    // All strings should have the same normalized hash
    uint32_t normalized = strings[0].normalized_hash;
    for (const auto& tok : strings) {
        EXPECT_EQ(tok.normalized_hash, normalized);
    }
}

TEST_F(PythonNormalizerTest, ParsesFStrings) {
    auto result = normalizer.normalize("f'hello {name}'");

    auto strings = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) strings++;
    }
    EXPECT_GE(strings, 1);
}

// =============================================================================
// Number Literal Tests
// =============================================================================

TEST_F(PythonNormalizerTest, ParsesIntegers) {
    auto result = normalizer.normalize("42 0 123456");

    auto numbers = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) numbers++;
    }
    EXPECT_EQ(numbers, 3);
}

TEST_F(PythonNormalizerTest, ParsesFloats) {
    auto result = normalizer.normalize("3.14 .5 1e10 2.5e-3");

    auto numbers = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) numbers++;
    }
    EXPECT_EQ(numbers, 4);
}

TEST_F(PythonNormalizerTest, ParsesHexOctalBinary) {
    auto result = normalizer.normalize("0xFF 0o755 0b1010");

    auto numbers = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) numbers++;
    }
    EXPECT_EQ(numbers, 3);
}

TEST_F(PythonNormalizerTest, NumbersNormalizedToSameHash) {
    auto result = normalizer.normalize("42 3.14 0xFF 1e10");

    std::vector<NormalizedToken> numbers;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) {
            numbers.push_back(tok);
        }
    }

    ASSERT_EQ(numbers.size(), 4);

    // All numbers should have the same normalized hash
    uint32_t normalized = numbers[0].normalized_hash;
    for (const auto& tok : numbers) {
        EXPECT_EQ(tok.normalized_hash, normalized);
    }
}

// =============================================================================
// Operator Tests
// =============================================================================

TEST_F(PythonNormalizerTest, ParsesArithmeticOperators) {
    auto result = normalizer.normalize("+ - * / // % **");

    auto operators = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::OPERATOR) operators++;
    }
    EXPECT_EQ(operators, 7);
}

TEST_F(PythonNormalizerTest, ParsesComparisonOperators) {
    auto result = normalizer.normalize("== != < > <= >=");

    auto operators = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::OPERATOR) operators++;
    }
    EXPECT_EQ(operators, 6);
}

TEST_F(PythonNormalizerTest, OperatorsPreserveHash) {
    auto result1 = normalizer.normalize("+");
    auto result2 = normalizer.normalize("-");

    ASSERT_FALSE(result1.tokens.empty());
    ASSERT_FALSE(result2.tokens.empty());

    // Different operators should have different hashes
    EXPECT_NE(result1.tokens[0].original_hash, result2.tokens[0].original_hash);
}

// =============================================================================
// Comment Tests
// =============================================================================

TEST_F(PythonNormalizerTest, IgnoresComments) {
    auto result = normalizer.normalize("x = 1  # this is a comment\ny = 2");

    // Should not have any token containing "comment"
    for (const auto& tok : result.tokens) {
        // Comments should be skipped entirely
        EXPECT_NE(tok.type, TokenType::UNKNOWN);
    }
}

TEST_F(PythonNormalizerTest, CommentOnlyLinesCountedCorrectly) {
    auto result = normalizer.normalize("# comment\nx = 1\n# another comment");

    EXPECT_EQ(result.comment_lines, 2);
    EXPECT_EQ(result.code_lines, 1);
}

TEST_F(PythonNormalizerTest, IgnoresModuleDocstring) {
    // A triple-quoted string at the start of a file is a module docstring
    auto result = normalizer.normalize("\"\"\"This is a module docstring.\"\"\"\nx = 1");

    // Should have no STRING_LITERAL tokens (docstring is skipped)
    int strings = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) strings++;
    }
    EXPECT_EQ(strings, 0);
    EXPECT_GE(result.code_lines, 1);  // x = 1 is code
}

TEST_F(PythonNormalizerTest, IgnoresFunctionDocstring) {
    // A triple-quoted string after def name(): is a function docstring
    auto result = normalizer.normalize("def foo():\n    \"\"\"Function docstring.\"\"\"\n    return 1");

    // Should have no STRING_LITERAL tokens
    int strings = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) strings++;
    }
    EXPECT_EQ(strings, 0);
}

TEST_F(PythonNormalizerTest, IgnoresClassDocstring) {
    // A triple-quoted string after class name: is a class docstring
    auto result = normalizer.normalize("class Foo:\n    \"\"\"Class docstring.\"\"\"\n    pass");

    // Should have no STRING_LITERAL tokens
    int strings = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) strings++;
    }
    EXPECT_EQ(strings, 0);
}

TEST_F(PythonNormalizerTest, KeepsNonDocstringTripleQuotedStrings) {
    // A triple-quoted string in an assignment is NOT a docstring
    auto result = normalizer.normalize("x = \"\"\"This is a regular string.\"\"\"");

    int strings = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) strings++;
    }
    EXPECT_EQ(strings, 1);
}

// =============================================================================
// Indentation Tests
// =============================================================================

TEST_F(PythonNormalizerTest, EmitsIndentToken) {
    auto result = normalizer.normalize("def foo():\n    pass");

    bool has_indent = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::INDENT) {
            has_indent = true;
            break;
        }
    }
    EXPECT_TRUE(has_indent);
}

TEST_F(PythonNormalizerTest, EmitsDedentToken) {
    auto result = normalizer.normalize("def foo():\n    pass\nx = 1");

    bool has_dedent = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::DEDENT) {
            has_dedent = true;
            break;
        }
    }
    EXPECT_TRUE(has_dedent);
}

TEST_F(PythonNormalizerTest, MultipleIndentLevels) {
    auto result = normalizer.normalize(
        "def foo():\n"
        "    if True:\n"
        "        pass\n"
        "    else:\n"
        "        pass\n"
    );

    int indent_count = 0;
    int dedent_count = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::INDENT) indent_count++;
        if (tok.type == TokenType::DEDENT) dedent_count++;
    }

    // Should have at least 2 indents and corresponding dedents
    EXPECT_GE(indent_count, 2);
    EXPECT_GE(dedent_count, 2);
}

// =============================================================================
// Line Metrics Tests
// =============================================================================

TEST_F(PythonNormalizerTest, CountsLinesCorrectly) {
    auto result = normalizer.normalize(
        "# Comment line\n"
        "x = 1\n"
        "\n"
        "y = 2\n"
    );

    EXPECT_EQ(result.total_lines, 4);
    EXPECT_EQ(result.code_lines, 2);
    EXPECT_EQ(result.blank_lines, 1);
    EXPECT_EQ(result.comment_lines, 1);
}

// =============================================================================
// Full Function Tests
// =============================================================================

TEST_F(PythonNormalizerTest, TokenizesSimpleFunction) {
    auto result = normalizer.normalize(
        "def add(a, b):\n"
        "    return a + b\n"
    );

    // Should have: def, add, (, a, ,, b, ), :, NEWLINE, INDENT, return, a, +, b, NEWLINE, DEDENT
    EXPECT_GT(result.tokens.size(), 10);
    EXPECT_EQ(result.code_lines, 2);
}

TEST_F(PythonNormalizerTest, TwoFunctionsWithSameStructure) {
    auto result1 = normalizer.normalize(
        "def calculate(price, tax):\n"
        "    return price * tax\n"
    );

    auto result2 = normalizer.normalize(
        "def compute(amount, rate):\n"
        "    return amount * rate\n"
    );

    // Extract normalized hashes
    std::vector<uint32_t> hashes1, hashes2;
    for (const auto& tok : result1.tokens) {
        hashes1.push_back(tok.normalized_hash);
    }
    for (const auto& tok : result2.tokens) {
        hashes2.push_back(tok.normalized_hash);
    }

    // Same structure should produce same normalized hash sequence
    // (This is the basis for Type-2 clone detection)
    EXPECT_EQ(hashes1.size(), hashes2.size());
    EXPECT_EQ(hashes1, hashes2);
}

// =============================================================================
// Built-in Types Tests
// =============================================================================

TEST_F(PythonNormalizerTest, RecognizesBuiltinTypes) {
    auto result = normalizer.normalize("int float str list dict set tuple");

    std::vector<NormalizedToken> types;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::TYPE) {
            types.push_back(tok);
        }
    }

    EXPECT_EQ(types.size(), 7);

    // All types should have same normalized hash
    uint32_t normalized = types[0].normalized_hash;
    for (const auto& tok : types) {
        EXPECT_EQ(tok.normalized_hash, normalized);
    }
}

// =============================================================================
// Edge Cases
// =============================================================================

TEST_F(PythonNormalizerTest, HandlesEscapedStrings) {
    auto result = normalizer.normalize("\"hello\\nworld\"");

    auto strings = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) strings++;
    }
    EXPECT_EQ(strings, 1);
}

TEST_F(PythonNormalizerTest, HandlesRawStrings) {
    auto result = normalizer.normalize("r\"raw\\nstring\"");

    auto strings = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) strings++;
    }
    EXPECT_EQ(strings, 1);
}

TEST_F(PythonNormalizerTest, HandlesUnderscoresInNumbers) {
    auto result = normalizer.normalize("1_000_000 3.14_15");

    auto numbers = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) numbers++;
    }
    EXPECT_EQ(numbers, 2);
}

TEST_F(PythonNormalizerTest, HandlesComplexNumbers) {
    auto result = normalizer.normalize("3+4j 2.5j");

    auto numbers = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) numbers++;
    }
    EXPECT_GE(numbers, 2);
}

// =============================================================================
// Import Statement Handling
// =============================================================================

TEST_F(PythonNormalizerTest, IgnoresSimpleImport) {
    // "import os" should be skipped entirely
    // "x = 1" should produce: IDENTIFIER, OPERATOR, NUMBER
    auto result = normalizer.normalize("import os\nx = 1");

    // Count tokens - should only have tokens from "x = 1"
    // Without imports: x (ID), = (OP), 1 (NUM) = 3 tokens
    // We expect around 3 tokens, not 5+ (which would include import/os)
    EXPECT_LE(result.tokens.size(), 5) << "Should have few tokens without import";

    // Verify we have an identifier and a number (from "x = 1")
    int identifiers = 0, numbers = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::IDENTIFIER) identifiers++;
        if (tok.type == TokenType::NUMBER_LITERAL) numbers++;
    }
    EXPECT_GE(identifiers, 1) << "Should have identifier x";
    EXPECT_GE(numbers, 1) << "Should have number 1";
}

TEST_F(PythonNormalizerTest, IgnoresFromImport) {
    auto result = normalizer.normalize("from dataclasses import dataclass\ndef foo(): pass");

    // Should have "def" keyword and some tokens from the function
    bool has_def = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            has_def = true;  // "def" is a keyword
            break;
        }
    }
    EXPECT_TRUE(has_def) << "Code after import should be tokenized";

    // Should have very few tokens (just the function definition)
    // "def foo(): pass" = def, foo, (, ), :, pass ~ 6 tokens max
    EXPECT_LE(result.tokens.size(), 10) << "Should not have import tokens";
}

TEST_F(PythonNormalizerTest, IgnoresFutureImport) {
    auto result = normalizer.normalize("from __future__ import annotations\nx = 1");

    // Should have tokens from "x = 1" only
    EXPECT_LE(result.tokens.size(), 5) << "Should have few tokens without import";
}

TEST_F(PythonNormalizerTest, IgnoresMultilineImportWithParentheses) {
    auto result = normalizer.normalize(
        "from typing import (\n"
        "    List,\n"
        "    Dict,\n"
        "    Optional\n"
        ")\n"
        "x = 1"
    );

    // Should only have tokens from "x = 1"
    EXPECT_LE(result.tokens.size(), 5) << "Multi-line import should be skipped";

    // Should have identifier and number
    int identifiers = 0, numbers = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::IDENTIFIER) identifiers++;
        if (tok.type == TokenType::NUMBER_LITERAL) numbers++;
    }
    EXPECT_GE(identifiers, 1) << "Should have identifier x";
    EXPECT_GE(numbers, 1) << "Should have number 1";
}

TEST_F(PythonNormalizerTest, IgnoresMultilineImportWithBackslash) {
    auto result = normalizer.normalize(
        "from typing import List, \\\n"
        "    Dict, Optional\n"
        "x = 1"
    );

    // Should only have tokens from "x = 1"
    EXPECT_LE(result.tokens.size(), 5) << "Backslash-continued import should be skipped";

    // Should have identifier and number
    int identifiers = 0, numbers = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::IDENTIFIER) identifiers++;
        if (tok.type == TokenType::NUMBER_LITERAL) numbers++;
    }
    EXPECT_GE(identifiers, 1) << "Should have identifier x";
    EXPECT_GE(numbers, 1) << "Should have number 1";
}

TEST_F(PythonNormalizerTest, IgnoresMultipleImports) {
    auto result = normalizer.normalize(
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "def main(): pass"
    );

    // Should have keywords (def, pass) from the function
    int keywords = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) keywords++;
    }
    EXPECT_GE(keywords, 1) << "Should have keyword 'def' from function";

    // Should have few tokens (just the function definition, no imports)
    EXPECT_LE(result.tokens.size(), 10) << "All imports should be skipped";
}
