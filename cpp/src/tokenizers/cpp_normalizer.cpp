#include "tokenizers/cpp_normalizer.hpp"
#include <cctype>
#include <algorithm>

namespace aegis::similarity {

CppNormalizer::CppNormalizer() {
    // C/C++ keywords
    keywords_ = {
        // Control flow
        "break", "case", "continue", "default", "do", "else", "for", "goto",
        "if", "return", "switch", "while",
        // Types and declarations
        "auto", "char", "const", "double", "enum", "extern", "float", "inline",
        "int", "long", "register", "short", "signed", "sizeof", "static",
        "struct", "typedef", "union", "unsigned", "void", "volatile",
        // C++ specific
        "alignas", "alignof", "and", "and_eq", "asm", "bitand", "bitor",
        "bool", "catch", "class", "compl", "const_cast", "delete",
        "dynamic_cast", "explicit", "export", "false", "friend", "mutable",
        "namespace", "new", "not", "not_eq", "operator", "or", "or_eq",
        "private", "protected", "public", "reinterpret_cast", "static_cast",
        "template", "this", "throw", "true", "try", "typeid", "typename",
        "using", "virtual", "wchar_t", "xor", "xor_eq"
    };

    // C++11/14/17/20 keywords
    modern_keywords_ = {
        "alignas", "alignof", "char8_t", "char16_t", "char32_t", "concept",
        "consteval", "constexpr", "constinit", "co_await", "co_return",
        "co_yield", "decltype", "final", "noexcept", "nullptr", "override",
        "requires", "static_assert", "thread_local"
    };

    // Built-in types
    builtin_types_ = {
        "int8_t", "int16_t", "int32_t", "int64_t",
        "uint8_t", "uint16_t", "uint32_t", "uint64_t",
        "size_t", "ptrdiff_t", "intptr_t", "uintptr_t",
        "string", "wstring", "string_view",
        "vector", "array", "list", "deque", "forward_list",
        "set", "map", "multiset", "multimap",
        "unordered_set", "unordered_map", "unordered_multiset", "unordered_multimap",
        "stack", "queue", "priority_queue",
        "pair", "tuple", "optional", "variant", "any",
        "unique_ptr", "shared_ptr", "weak_ptr",
        "function", "bind", "reference_wrapper",
        "thread", "mutex", "condition_variable", "future", "promise",
        "atomic", "atomic_flag"
    };

    // Preprocessor directives
    preprocessor_ = {
        "include", "define", "undef", "ifdef", "ifndef", "if", "else",
        "elif", "endif", "error", "warning", "pragma", "line"
    };
}

TokenizedFile CppNormalizer::normalize(std::string_view source) {
    TokenizedFile result;
    result.path = "";

    TokenizerState state;
    state.source = source;

    size_t code_lines = 0;
    size_t blank_lines = 0;
    size_t comment_lines = 0;
    uint32_t current_line = 0;
    bool line_has_code = false;
    bool line_has_comment = false;

    while (!state.eof()) {
        handle_line_metrics(state, current_line, code_lines, comment_lines, blank_lines, 
                          line_has_code, line_has_comment);

        if (skip_whitespace_and_newline(state)) continue;

        if (process_preprocessor(state, line_has_code, result)) continue;
        
        if (process_comment(state, line_has_comment)) continue;

        if (process_string_literal(state, result, line_has_code)) continue;

        if (process_number(state, result, line_has_code)) continue;

        if (process_identifier(state, result, line_has_code)) continue;

        if (process_operator(state, result, line_has_code)) continue;

        // Unknown - skip
        state.advance();
    }

    // Handle final line
    if (current_line > 0) {
        if (line_has_code) code_lines++;
        else if (line_has_comment) comment_lines++;
        else blank_lines++;
    }

    result.total_lines = source.empty() ? 0 :
        (state.column == 1 && state.line > 1 ? state.line - 1 : state.line);
    result.code_lines = code_lines;
    result.blank_lines = blank_lines;
    result.comment_lines = comment_lines;

    return result;
}

NormalizedToken CppNormalizer::parse_string(TokenizerState& state) {
    NormalizedToken tok{};
    tok.type = TokenType::STRING_LITERAL;
    tok.line = state.line;
    tok.column = state.column;

    const size_t start_pos = state.pos;

    // Skip prefix (L, u, U, u8)
    if (state.peek() == 'L' || state.peek() == 'U') {
        state.advance();
    } else if (state.peek() == 'u') {
        state.advance();
        if (state.peek() == '8') {
            state.advance();
        }
    }

    state.advance();  // Skip "

    std::string value;
    while (!state.eof()) {
        char c = state.peek();

        if (c == '"') {
            state.advance();
            break;
        }

        if (c == '\n') {
            // Unterminated string
            break;
        }

        // Handle escape sequences
        if (c == '\\' && !state.eof()) {
            state.advance();
            if (!state.eof()) {
                state.advance();
            }
            continue;
        }

        value += c;
        state.advance();
    }

    tok.length = static_cast<uint16_t>(state.pos - start_pos);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = hash_placeholder(TokenType::STRING_LITERAL);

    return tok;
}

NormalizedToken CppNormalizer::parse_raw_string(TokenizerState& state) {
    NormalizedToken tok{};
    tok.type = TokenType::STRING_LITERAL;
    tok.line = state.line;
    tok.column = state.column;

    size_t start_pos = state.pos;

    state.advance();  // Skip R
    state.advance();  // Skip "

    // Get delimiter
    std::string delimiter;
    while (!state.eof() && state.peek() != '(') {
        delimiter += state.advance();
    }
    if (!state.eof()) state.advance();  // Skip (

    // Build end marker
    const std::string end_marker = ")" + delimiter + "\"";

    std::string value;
    while (!state.eof()) {
        // Check for end marker
        bool found_end = true;
        for (size_t i = 0; i < end_marker.size() && found_end; i++) {
            if (state.peek_at(i) != end_marker[i]) {
                found_end = false;
            }
        }

        if (found_end) {
            for (size_t i = 0; i < end_marker.size(); i++) {
                state.advance();
            }
            break;
        }

        value += state.advance();
    }

    tok.length = static_cast<uint16_t>(state.pos - start_pos);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = hash_placeholder(TokenType::STRING_LITERAL);

    return tok;
}

NormalizedToken CppNormalizer::parse_char(TokenizerState& state) {
    NormalizedToken tok{};
    tok.type = TokenType::STRING_LITERAL;  // Treat char like string
    tok.line = state.line;
    tok.column = state.column;

    const size_t start_pos = state.pos;

    // Skip prefix
    if (state.peek() == 'L' || state.peek() == 'U') {
        state.advance();
    } else if (state.peek() == 'u') {
        state.advance();
        if (state.peek() == '8') {
            state.advance();
        }
    }

    state.advance();  // Skip '

    std::string value;
    while (!state.eof() && state.peek() != '\'') {
        char c = state.peek();

        if (c == '\n') break;

        if (c == '\\' && !state.eof()) {
            state.advance();
            if (!state.eof()) {
                value += state.advance();
            }
            continue;
        }

        value += state.advance();
    }

    if (!state.eof()) state.advance();  // Skip '

    tok.length = static_cast<uint16_t>(state.pos - start_pos);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = hash_placeholder(TokenType::STRING_LITERAL);

    return tok;
}

NormalizedToken CppNormalizer::parse_number(TokenizerState& state) const
{
    NormalizedToken tok{};
    tok.type = TokenType::NUMBER_LITERAL;
    tok.line = state.line;
    tok.column = state.column;

    std::string value;
    size_t start_pos = state.pos;

    // Check for hex, binary, octal
    if (state.peek() == '0' && !state.eof()) {
        char next = state.peek_next();
        if (next == 'x' || next == 'X') {
            // Hex
            value += state.advance();
            value += state.advance();
            while (!state.eof() && (is_hex_digit(state.peek()) || state.peek() == '\'')) {
                if (state.peek() != '\'') value += state.peek();
                state.advance();
            }
        } else if (next == 'b' || next == 'B') {
            // Binary (C++14)
            value += state.advance();
            value += state.advance();
            while (!state.eof() && (state.peek() == '0' || state.peek() == '1' || state.peek() == '\'')) {
                if (state.peek() != '\'') value += state.peek();
                state.advance();
            }
        } else if (next >= '0' && next <= '7') {
            // Octal
            value += state.advance();
            while (!state.eof() && ((state.peek() >= '0' && state.peek() <= '7') || state.peek() == '\'')) {
                if (state.peek() != '\'') value += state.peek();
                state.advance();
            }
        } else {
            value += state.advance();
        }
    }

    // Integer or float part
    if (value.empty()) {
        while (!state.eof() && (is_digit(state.peek()) || state.peek() == '\'')) {
            if (state.peek() != '\'') value += state.peek();
            state.advance();
        }
    }

    // Decimal part
    if (state.peek() == '.' && (is_digit(state.peek_next()) || state.peek_next() == 'e' || state.peek_next() == 'E')) {
        value += state.advance();
        while (!state.eof() && (is_digit(state.peek()) || state.peek() == '\'')) {
            if (state.peek() != '\'') value += state.peek();
            state.advance();
        }
    }

    // Exponent part
    if (state.peek() == 'e' || state.peek() == 'E') {
        value += state.advance();
        if (state.peek() == '+' || state.peek() == '-') {
            value += state.advance();
        }
        while (!state.eof() && (is_digit(state.peek()) || state.peek() == '\'')) {
            if (state.peek() != '\'') value += state.peek();
            state.advance();
        }
    }

    // Suffixes (u, l, ll, ul, ull, f, etc.)
    while (!state.eof() && (state.peek() == 'u' || state.peek() == 'U' ||
           state.peek() == 'l' || state.peek() == 'L' ||
           state.peek() == 'f' || state.peek() == 'F')) {
        state.advance();
    }

    tok.length = static_cast<uint16_t>(state.pos - start_pos);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = hash_placeholder(TokenType::NUMBER_LITERAL);

    return tok;
}

NormalizedToken CppNormalizer::parse_identifier_or_keyword(TokenizerState& state) const
{
    NormalizedToken tok{};
    tok.line = state.line;
    tok.column = state.column;

    std::string value;
    const size_t start_pos = state.pos;

    while (!state.eof() && is_identifier_char(state.peek())) {
        value += state.advance();
    }

    tok.length = static_cast<uint16_t>(state.pos - start_pos);
    tok.original_hash = hash_string(value);

    // Check if it's a keyword
    if (keywords_.contains(value) || modern_keywords_.contains(value)) {
        tok.type = TokenType::KEYWORD;
        tok.normalized_hash = tok.original_hash;
    }
    // Check if it's a built-in type
    else if (builtin_types_.contains(value)) {
        tok.type = TokenType::TYPE;
        tok.normalized_hash = hash_placeholder(TokenType::TYPE);
    }
    // Regular identifier
    else {
        tok.type = TokenType::IDENTIFIER;
        tok.normalized_hash = hash_placeholder(TokenType::IDENTIFIER);
    }

    return tok;
}

NormalizedToken CppNormalizer::parse_operator(TokenizerState& state) {
    NormalizedToken tok{};
    tok.line = state.line;
    tok.column = state.column;

    std::string value;
    size_t start_pos = state.pos;

    // Check 4-character operators
    if (state.pos + 3 < state.source.size()) {
        if (std::string four(state.source.substr(state.pos, 4)); four == ">>>=") {
            value = four;
            for (int i = 0; i < 4; i++) state.advance();
        }
    }

    // Check 3-character operators
    if (value.empty() && state.pos + 2 < state.source.size()) {
        std::string three(state.source.substr(state.pos, 3));
        if (three == "<<=" || three == ">>=" || three == "<=>" ||
            three == "->*" || three == "...") {
            value = three;
            state.advance();
            state.advance();
            state.advance();
        }
    }

    // Check 2-character operators
    if (value.empty() && state.pos + 1 < state.source.size()) {
        if (std::string two(state.source.substr(state.pos, 2)); two == "==" || two == "!=" || two == "<=" || two == ">=" ||
            two == "+=" || two == "-=" || two == "*=" || two == "/=" ||
            two == "%=" || two == "&=" || two == "|=" || two == "^=" ||
            two == "++" || two == "--" || two == "&&" || two == "||" ||
            two == "<<" || two == ">>" || two == "->" || two == "::" ||
            two == ".*" || two == "##") {
            value = two;
            state.advance();
            state.advance();
        }
    }

    // Single character operator
    if (value.empty()) {
        value = state.advance();
    }

    tok.length = static_cast<uint16_t>(state.pos - start_pos);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = tok.original_hash;

    // Classify
    if (value == "(" || value == ")" || value == "[" || value == "]" ||
        value == "{" || value == "}" || value == "," || value == ":" ||
        value == ";" || value == ".") {
        tok.type = TokenType::PUNCTUATION;
    } else {
        tok.type = TokenType::OPERATOR;
    }

    return tok;
}

void CppNormalizer::skip_preprocessor(TokenizerState& state) {
    // Skip the # character
    state.advance();

    // Skip rest of line (handling line continuations with backslash)
    while (!state.eof()) {
        char c = state.peek();

        if (c == '\n') {
            // Don't consume the newline - let the main loop handle it
            return;
        }

        // Handle line continuation
        if (c == '\\') {
            state.advance();
            if (!state.eof() && state.peek() == '\n') {
                state.advance();  // Skip the newline after backslash
                continue;  // Continue reading the next line
            }
            continue;
        }

        state.advance();
    }
}

void CppNormalizer::skip_single_line_comment(TokenizerState& state) {
    while (!state.eof() && state.peek() != '\n') {
        state.advance();
    }
}

void CppNormalizer::skip_multi_line_comment(TokenizerState& state) {
    state.advance();  // Skip /
    state.advance();  // Skip *

    while (!state.eof()) {
        if (state.peek() == '*' && state.peek_next() == '/') {
            state.advance();
            state.advance();
            break;
        }
        state.advance();
    }
}

bool CppNormalizer::is_identifier_start(char c) {
    return std::isalpha(static_cast<unsigned char>(c)) || c == '_';
}

bool CppNormalizer::is_identifier_char(char c) {
    return std::isalnum(static_cast<unsigned char>(c)) || c == '_';
}

bool CppNormalizer::is_digit(char c) {
    return c >= '0' && c <= '9';
}

bool CppNormalizer::is_hex_digit(char c) {
    return is_digit(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}

bool CppNormalizer::is_operator_char(char c) {
    return c == '+' || c == '-' || c == '*' || c == '/' || c == '%' ||
           c == '=' || c == '<' || c == '>' || c == '!' || c == '&' ||
           c == '|' || c == '^' || c == '~' || c == '?' || c == ':' ||
           c == '(' || c == ')' || c == '[' || c == ']' || c == '{' ||
           c == '}' || c == ',' || c == ';' || c == '.' || c == '#';
}

}  // namespace aegis::similarity

// Helper implementations
namespace aegis::similarity {

void CppNormalizer::handle_line_metrics(TokenizerState& state, uint32_t& current_line,
                         size_t& code_lines, size_t& comment_lines, size_t& blank_lines,
                         bool& line_has_code, bool& line_has_comment) const {
    if (state.line != current_line) {
        if (current_line > 0) {
            if (line_has_code) code_lines++;
            else if (line_has_comment) comment_lines++;
            else blank_lines++;
        }
        current_line = state.line;
        line_has_code = false;
        line_has_comment = false;
    }
}

bool CppNormalizer::skip_whitespace_and_newline(TokenizerState& state) {
    char c = state.peek();
    
    // Whitespace
    if (c == ' ' || c == '\t' || c == '\r') {
        state.advance();
        return true;
    }

    // Newline
    if (c == '\n') {
        state.advance();
        return true;
    }
    
    return false;
}

bool CppNormalizer::process_preprocessor(TokenizerState& state, bool& line_has_code, TokenizedFile& result) {
    char c = state.peek();
    
    // Preprocessor directive - skip entirely (structural, not logic)
    // This prevents false positives from common #include, #define patterns
    if (c == '#' && state.at_line_start) {
        skip_preprocessor(state);
        line_has_code = true;  // Count as code line but don't emit tokens
        return true;
    }
    return false;
}

bool CppNormalizer::process_comment(TokenizerState& state, bool& line_has_comment) {
    char c = state.peek();
    
    // Single-line comment
    if (c == '/' && state.peek_next() == '/') {
        line_has_comment = true;
        skip_single_line_comment(state);
        return true;
    }

    // Multi-line comment
    if (c == '/' && state.peek_next() == '*') {
        line_has_comment = true;
        skip_multi_line_comment(state);
        return true;
    }
    
    return false;
}

bool CppNormalizer::process_string_literal(TokenizerState& state, TokenizedFile& result, bool& line_has_code) {
    char c = state.peek();

    // Raw string literal (R"delimiter(...)delimiter")
    if (c == 'R' && state.peek_next() == '"') {
        line_has_code = true;
        result.tokens.push_back(parse_raw_string(state));
        return true;
    }

    // String literals (including wide/u8/u16/u32 prefixes)
    if (c == '"' ||
        ((c == 'L' || c == 'u' || c == 'U') && state.peek_next() == '"') ||
        (c == 'u' && state.peek_next() == '8' && state.peek_at(2) == '"')) {
        line_has_code = true;
        result.tokens.push_back(parse_string(state));
        return true;
    }

    // Character literals
    if (c == '\'' ||
        ((c == 'L' || c == 'u' || c == 'U') && state.peek_next() == '\'') ||
        (c == 'u' && state.peek_next() == '8' && state.peek_at(2) == '\'')) {
        line_has_code = true;
        result.tokens.push_back(parse_char(state));
        return true;
    }
    
    return false;
}

bool CppNormalizer::process_number(TokenizerState& state, TokenizedFile& result, bool& line_has_code) const {
    char c = state.peek();
    
    if (is_digit(c) || (c == '.' && is_digit(state.peek_next()))) {
        line_has_code = true;
        result.tokens.push_back(parse_number(state));
        return true;
    }
    
    return false;
}

bool CppNormalizer::process_identifier(TokenizerState& state, TokenizedFile& result, bool& line_has_code) const {
    char c = state.peek();
    
    if (is_identifier_start(c)) {
        line_has_code = true;
        result.tokens.push_back(parse_identifier_or_keyword(state));
        return true;
    }
    
    return false;
}

bool CppNormalizer::process_operator(TokenizerState& state, TokenizedFile& result, bool& line_has_code) {
    char c = state.peek();
    
    if (is_operator_char(c)) {
        line_has_code = true;
        result.tokens.push_back(parse_operator(state));
        return true;
    }
    
    return false;
}



} // namespace aegis::similarity
