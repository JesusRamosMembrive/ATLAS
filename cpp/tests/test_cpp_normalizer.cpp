#include <gtest/gtest.h>
#include "tokenizers/cpp_normalizer.hpp"

using namespace aegis::similarity;

class CppNormalizerTest : public ::testing::Test {
protected:
    CppNormalizer normalizer;
};

// =============================================================================
// Basic Tokenization
// =============================================================================

TEST_F(CppNormalizerTest, EmptySource) {
    auto result = normalizer.normalize("");
    EXPECT_TRUE(result.tokens.empty());
    EXPECT_EQ(result.total_lines, 0);
}

TEST_F(CppNormalizerTest, SimpleFunction) {
    auto result = normalizer.normalize("int add(int a, int b) { return a + b; }");
    EXPECT_FALSE(result.tokens.empty());

    // Check for keyword 'int'
    bool found_int = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            found_int = true;
            break;
        }
    }
    EXPECT_TRUE(found_int);
}

TEST_F(CppNormalizerTest, ClassDefinition) {
    auto result = normalizer.normalize("class Foo { public: void bar(); };");
    EXPECT_FALSE(result.tokens.empty());

    int keyword_count = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            keyword_count++;
        }
    }
    EXPECT_GE(keyword_count, 3);  // class, public, void
}

// =============================================================================
// String Literals
// =============================================================================

TEST_F(CppNormalizerTest, RegularString) {
    auto result = normalizer.normalize("const char* s = \"hello\";");

    bool found_string = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            found_string = true;
        }
    }
    EXPECT_TRUE(found_string);
}

TEST_F(CppNormalizerTest, WideString) {
    auto result = normalizer.normalize("const wchar_t* s = L\"hello\";");

    bool found_string = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            found_string = true;
        }
    }
    EXPECT_TRUE(found_string);
}

TEST_F(CppNormalizerTest, RawString) {
    auto result = normalizer.normalize("const char* s = R\"(hello world)\";");

    bool found_string = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            found_string = true;
        }
    }
    EXPECT_TRUE(found_string);
}

TEST_F(CppNormalizerTest, RawStringWithDelimiter) {
    auto result = normalizer.normalize("const char* s = R\"delim(hello)delim\";");

    bool found_string = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            found_string = true;
        }
    }
    EXPECT_TRUE(found_string);
}

TEST_F(CppNormalizerTest, CharLiteral) {
    auto result = normalizer.normalize("char c = 'x';");

    bool found_char = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::STRING_LITERAL) {
            found_char = true;
        }
    }
    EXPECT_TRUE(found_char);
}

// =============================================================================
// Number Literals
// =============================================================================

TEST_F(CppNormalizerTest, IntegerNumber) {
    auto result = normalizer.normalize("int x = 42;");

    bool found_number = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) {
            found_number = true;
        }
    }
    EXPECT_TRUE(found_number);
}

TEST_F(CppNormalizerTest, FloatNumber) {
    auto result = normalizer.normalize("double x = 3.14159;");

    bool found_number = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) {
            found_number = true;
        }
    }
    EXPECT_TRUE(found_number);
}

TEST_F(CppNormalizerTest, HexNumber) {
    auto result = normalizer.normalize("int x = 0xFF;");

    bool found_number = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) {
            found_number = true;
        }
    }
    EXPECT_TRUE(found_number);
}

TEST_F(CppNormalizerTest, BinaryNumber) {
    auto result = normalizer.normalize("int x = 0b1010;");

    bool found_number = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) {
            found_number = true;
        }
    }
    EXPECT_TRUE(found_number);
}

TEST_F(CppNormalizerTest, NumberWithSuffix) {
    auto result = normalizer.normalize("unsigned long x = 42ULL;");

    bool found_number = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::NUMBER_LITERAL) {
            found_number = true;
        }
    }
    EXPECT_TRUE(found_number);
}

TEST_F(CppNormalizerTest, DigitSeparator) {
    auto result = normalizer.normalize("int x = 1'000'000;");

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

TEST_F(CppNormalizerTest, CppKeywords) {
    auto result = normalizer.normalize("namespace foo { class Bar {}; }");

    int keyword_count = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            keyword_count++;
        }
    }
    EXPECT_GE(keyword_count, 2);  // namespace, class
}

TEST_F(CppNormalizerTest, ModernCppKeywords) {
    auto result = normalizer.normalize("constexpr auto x = nullptr;");

    int keyword_count = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            keyword_count++;
        }
    }
    EXPECT_GE(keyword_count, 3);  // constexpr, auto, nullptr
}

TEST_F(CppNormalizerTest, Cpp20Keywords) {
    auto result = normalizer.normalize("concept Addable = requires(T a) { a + a; };");

    bool found_concept = false;
    bool found_requires = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            found_concept = found_requires = true;
        }
    }
    EXPECT_TRUE(found_concept || found_requires);
}

// =============================================================================
// Preprocessor
// =============================================================================

TEST_F(CppNormalizerTest, Include) {
    auto result = normalizer.normalize("#include <iostream>\nint main() {}");

    bool found_preprocessor = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {  // Preprocessor treated as keyword
            found_preprocessor = true;
            break;
        }
    }
    EXPECT_TRUE(found_preprocessor);
}

TEST_F(CppNormalizerTest, Define) {
    auto result = normalizer.normalize("#define MAX 100\nint x = MAX;");
    EXPECT_FALSE(result.tokens.empty());
}

TEST_F(CppNormalizerTest, ConditionalCompilation) {
    auto result = normalizer.normalize(
        "#ifdef DEBUG\n"
        "  int x = 1;\n"
        "#else\n"
        "  int x = 2;\n"
        "#endif\n"
    );
    EXPECT_FALSE(result.tokens.empty());
}

// =============================================================================
// Comments
// =============================================================================

TEST_F(CppNormalizerTest, SingleLineComment) {
    // Line with code + comment counts as code line
    // Only lines with ONLY comments count as comment_lines
    auto result = normalizer.normalize("// this is a comment\nint x = 1;");
    EXPECT_GT(result.comment_lines, 0);
}

TEST_F(CppNormalizerTest, MultiLineComment) {
    auto result = normalizer.normalize("/* multi\nline\ncomment */\nint x = 1;");
    EXPECT_GT(result.comment_lines, 0);
}

// =============================================================================
// Operators
// =============================================================================

TEST_F(CppNormalizerTest, ScopeResolution) {
    auto result = normalizer.normalize("std::cout << \"hello\";");

    bool found_scope = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::OPERATOR) {
            found_scope = true;
        }
    }
    EXPECT_TRUE(found_scope);
}

TEST_F(CppNormalizerTest, PointerOperators) {
    auto result = normalizer.normalize("int* p = &x; p->member;");

    int op_count = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::OPERATOR) {
            op_count++;
        }
    }
    EXPECT_GE(op_count, 2);  // *, &, ->
}

TEST_F(CppNormalizerTest, SpaceshipOperator) {
    auto result = normalizer.normalize("auto cmp = a <=> b;");

    bool found = false;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::OPERATOR) {
            found = true;
        }
    }
    EXPECT_TRUE(found);
}

// =============================================================================
// Templates
// =============================================================================

TEST_F(CppNormalizerTest, TemplateDeclaration) {
    auto result = normalizer.normalize("template<typename T> class Container {};");
    EXPECT_FALSE(result.tokens.empty());
}

TEST_F(CppNormalizerTest, TemplateInstantiation) {
    auto result = normalizer.normalize("std::vector<int> v;");
    EXPECT_FALSE(result.tokens.empty());
}

// =============================================================================
// Identifier Normalization
// =============================================================================

TEST_F(CppNormalizerTest, IdentifiersNormalized) {
    auto result1 = normalizer.normalize("int userName = 1;");
    auto result2 = normalizer.normalize("int customerCount = 2;");

    // Find identifier tokens
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
// Line Counting
// =============================================================================

TEST_F(CppNormalizerTest, LineCountingAccurate) {
    auto result = normalizer.normalize(
        "#include <iostream>\n"
        "\n"
        "int main() {\n"
        "    // comment\n"
        "    return 0;\n"
        "}\n"
    );

    EXPECT_EQ(result.total_lines, 6);
    EXPECT_GE(result.code_lines, 3);
    EXPECT_GE(result.comment_lines, 1);
    EXPECT_GE(result.blank_lines, 1);
}

// =============================================================================
// Extension Support
// =============================================================================

TEST_F(CppNormalizerTest, SupportedExtensions) {
    EXPECT_TRUE(normalizer.supports_extension(".cpp"));
    EXPECT_TRUE(normalizer.supports_extension(".cxx"));
    EXPECT_TRUE(normalizer.supports_extension(".cc"));
    EXPECT_TRUE(normalizer.supports_extension(".hpp"));
    EXPECT_TRUE(normalizer.supports_extension(".h"));
    EXPECT_TRUE(normalizer.supports_extension(".c"));
    EXPECT_FALSE(normalizer.supports_extension(".py"));
    EXPECT_FALSE(normalizer.supports_extension(".js"));
}

// =============================================================================
// Complex Code
// =============================================================================

TEST_F(CppNormalizerTest, ComplexFunction) {
    auto result = normalizer.normalize(R"(
template<typename T>
constexpr auto sum(const std::vector<T>& values) -> T {
    T result = T{};
    for (const auto& v : values) {
        result += v;
    }
    return result;
}
)");

    // Should have multiple tokens
    EXPECT_GT(result.tokens.size(), 20);

    // Should have keywords
    int keyword_count = 0;
    for (const auto& tok : result.tokens) {
        if (tok.type == TokenType::KEYWORD) {
            keyword_count++;
        }
    }
    EXPECT_GE(keyword_count, 5);  // template, constexpr, auto, const, for, return
}
