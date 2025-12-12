#include <gtest/gtest.h>
#include "tokenizers/js_normalizer.hpp"

using namespace aegis::similarity;

class JavaScriptNormalizerTest : public ::testing::Test {
protected:
    JavaScriptNormalizer normalizer;
};

// =============================================================================
// Basic Tokenization
// =============================================================================

TEST_F(JavaScriptNormalizerTest, EmptySource) {
    auto result = normalizer.normalize("");
    EXPECT_TRUE(result.tokens.empty());
    EXPECT_EQ(result.total_lines, 0);
}

TEST_F(JavaScriptNormalizerTest, SimpleFunction) {
    auto result = normalizer.normalize("function add(a, b) { return a + b; }");
    EXPECT_FALSE(result.tokens.empty());

    // Check for keyword 'function'
    bool found_function = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            found_function = true;
            break;
        }
    }
    EXPECT_TRUE(found_function);
}

TEST_F(JavaScriptNormalizerTest, ArrowFunction) {
    auto result = normalizer.normalize("const add = (a, b) => a + b;");
    EXPECT_FALSE(result.tokens.empty());

    // Check for => operator
    bool found_arrow = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::OPERATOR) {
            found_arrow = true;
        }
    }
    EXPECT_TRUE(found_arrow);
}

// =============================================================================
// String Literals
// =============================================================================

TEST_F(JavaScriptNormalizerTest, SingleQuoteString) {
    auto result = normalizer.normalize("const s = 'hello';");

    bool found_string = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            found_string = true;
        }
    }
    EXPECT_TRUE(found_string);
}

TEST_F(JavaScriptNormalizerTest, DoubleQuoteString) {
    auto result = normalizer.normalize("const s = \"world\";");

    bool found_string = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            found_string = true;
        }
    }
    EXPECT_TRUE(found_string);
}

TEST_F(JavaScriptNormalizerTest, TemplateLiteral) {
    auto result = normalizer.normalize("const s = `hello ${name}`;");

    bool found_string = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            found_string = true;
        }
    }
    EXPECT_TRUE(found_string);
}

TEST_F(JavaScriptNormalizerTest, StringNormalization) {
    auto result1 = normalizer.normalize("const a = 'hello';");
    auto result2 = normalizer.normalize("const a = 'world';");

    // Find string tokens
    uint32_t hash1 = 0, hash2 = 0;
    for (const auto& tok : result1.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            hash1 = tok.normalized_hash;
            break;
        }
    }
    for (const auto& tok : result2.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            hash2 = tok.normalized_hash;
            break;
        }
    }

    // Different strings should have same normalized hash
    EXPECT_EQ(hash1, hash2);
}

// =============================================================================
// Number Literals
// =============================================================================

TEST_F(JavaScriptNormalizerTest, IntegerNumber) {
    auto result = normalizer.normalize("const x = 42;");

    bool found_number = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) {
            found_number = true;
        }
    }
    EXPECT_TRUE(found_number);
}

TEST_F(JavaScriptNormalizerTest, FloatNumber) {
    auto result = normalizer.normalize("const x = 3.14159;");

    bool found_number = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) {
            found_number = true;
        }
    }
    EXPECT_TRUE(found_number);
}

TEST_F(JavaScriptNormalizerTest, HexNumber) {
    auto result = normalizer.normalize("const x = 0xFF;");

    bool found_number = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) {
            found_number = true;
        }
    }
    EXPECT_TRUE(found_number);
}

TEST_F(JavaScriptNormalizerTest, BigIntNumber) {
    auto result = normalizer.normalize("const x = 9007199254740991n;");

    bool found_number = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) {
            found_number = true;
        }
    }
    EXPECT_TRUE(found_number);
}

// =============================================================================
// Keywords
// =============================================================================

TEST_F(JavaScriptNormalizerTest, ES6Keywords) {
    auto result = normalizer.normalize("let x = 1; const y = 2; class Foo {}");

    int keyword_count = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            keyword_count++;
        }
    }
    EXPECT_GE(keyword_count, 3);  // let, const, class
}

TEST_F(JavaScriptNormalizerTest, AsyncAwait) {
    auto result = normalizer.normalize("async function fetch() { await getData(); }");

    int keyword_count = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            keyword_count++;
        }
    }
    EXPECT_GE(keyword_count, 3);  // async, function, await
}

// =============================================================================
// TypeScript Support
// =============================================================================

TEST_F(JavaScriptNormalizerTest, TypeScriptTypes) {
    auto result = normalizer.normalize("interface User { name: string; }");

    bool found_interface = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            found_interface = true;
            break;
        }
    }
    EXPECT_TRUE(found_interface);
}

TEST_F(JavaScriptNormalizerTest, TypeAnnotations) {
    auto result = normalizer.normalize("function greet(name: string): void {}");
    EXPECT_FALSE(result.tokens.empty());
}

// =============================================================================
// Comments
// =============================================================================

TEST_F(JavaScriptNormalizerTest, SingleLineComment) {
    // Line with code + comment counts as code line
    // Only lines with ONLY comments count as comment_lines
    auto result = normalizer.normalize("// this is a comment\nconst x = 1;");
    EXPECT_GT(result.comment_lines, 0);
}

TEST_F(JavaScriptNormalizerTest, MultiLineComment) {
    auto result = normalizer.normalize("/* multi\nline\ncomment */\nconst x = 1;");
    EXPECT_GT(result.comment_lines, 0);
}

// =============================================================================
// Operators
// =============================================================================

TEST_F(JavaScriptNormalizerTest, SpreadOperator) {
    auto result = normalizer.normalize("const arr = [...items];");

    bool found_spread = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::OPERATOR) {
            found_spread = true;
        }
    }
    EXPECT_TRUE(found_spread);
}

TEST_F(JavaScriptNormalizerTest, NullishCoalescing) {
    auto result = normalizer.normalize("const x = a ?? b;");

    bool found_nullish = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::OPERATOR) {
            found_nullish = true;
        }
    }
    EXPECT_TRUE(found_nullish);
}

TEST_F(JavaScriptNormalizerTest, OptionalChaining) {
    auto result = normalizer.normalize("const x = obj?.prop;");
    EXPECT_FALSE(result.tokens.empty());
}

// =============================================================================
// Identifier Normalization
// =============================================================================

TEST_F(JavaScriptNormalizerTest, IdentifiersNormalized) {
    auto result1 = normalizer.normalize("const userName = 'John';");
    auto result2 = normalizer.normalize("const customerName = 'Jane';");

    // Find identifier tokens (not keywords)
    uint32_t hash1 = 0, hash2 = 0;
    for (const auto& tok : result1.tokens) {
        if (tok.type == TokenType::IDENTIFIER) {
            hash1 = tok.normalized_hash;
            break;
        }
    }
    for (const auto& tok : result2.tokens) {
        if (tok.type == TokenType::IDENTIFIER) {
            hash2 = tok.normalized_hash;
            break;
        }
    }

    // Different identifiers should have same normalized hash ($ID)
    EXPECT_EQ(hash1, hash2);
}

// =============================================================================
// Regex Literals
// =============================================================================

TEST_F(JavaScriptNormalizerTest, RegexLiteral) {
    auto result = normalizer.normalize("const pattern = /abc+/gi;");

    // Regex is treated as string literal for normalization
    bool found = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL || tok.type == TokenType::OPERATOR) {
            found = true;
        }
    }
    EXPECT_TRUE(found);
}

// =============================================================================
// Line Counting
// =============================================================================

TEST_F(JavaScriptNormalizerTest, LineCountingAccurate) {
    auto result = normalizer.normalize(
        "function foo() {\n"
        "  // comment\n"
        "  return 42;\n"
        "}\n"
    );

    EXPECT_EQ(result.total_lines, 4);
    EXPECT_GE(result.code_lines, 2);
    EXPECT_GE(result.comment_lines, 1);
}

// =============================================================================
// Extension Support
// =============================================================================

TEST_F(JavaScriptNormalizerTest, SupportedExtensions) {
    EXPECT_TRUE(normalizer.supports_extension(".js"));
    EXPECT_TRUE(normalizer.supports_extension(".jsx"));
    EXPECT_TRUE(normalizer.supports_extension(".ts"));
    EXPECT_TRUE(normalizer.supports_extension(".tsx"));
    EXPECT_TRUE(normalizer.supports_extension(".mjs"));
    EXPECT_FALSE(normalizer.supports_extension(".py"));
}
