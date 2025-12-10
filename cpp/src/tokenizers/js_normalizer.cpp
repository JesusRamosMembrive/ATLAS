#include "tokenizers/js_normalizer.hpp"
#include <cctype>
#include <algorithm>

namespace aegis::similarity {

JavaScriptNormalizer::JavaScriptNormalizer() {
    // JavaScript/ES6+ keywords
    keywords_ = {
        // Control flow
        "break", "case", "catch", "continue", "debugger", "default", "do",
        "else", "finally", "for", "if", "return", "switch", "throw", "try",
        "while", "with",
        // Declarations
        "class", "const", "function", "let", "var",
        // Expressions
        "delete", "in", "instanceof", "new", "of", "this", "typeof", "void",
        // Values
        "false", "null", "true", "undefined",
        // Async
        "async", "await", "yield",
        // Module
        "export", "import", "from", "as",
        // Class
        "extends", "static", "super", "get", "set",
        // Reserved
        "enum", "implements", "interface", "package", "private", "protected",
        "public"
    };

    // TypeScript-specific keywords
    ts_keywords_ = {
        "abstract", "any", "asserts", "bigint", "boolean", "declare",
        "infer", "is", "keyof", "module", "namespace", "never",
        "number", "object", "readonly", "require", "string", "symbol",
        "type", "unique", "unknown"
    };

    // Built-in types
    builtin_types_ = {
        "Array", "Boolean", "Date", "Error", "Function", "JSON", "Map",
        "Math", "Number", "Object", "Promise", "RegExp", "Set", "String",
        "Symbol", "WeakMap", "WeakSet", "BigInt", "ArrayBuffer",
        "DataView", "Float32Array", "Float64Array", "Int8Array",
        "Int16Array", "Int32Array", "Uint8Array", "Uint16Array",
        "Uint32Array", "Uint8ClampedArray"
    };

    // Operators
    operators_ = {
        "+", "-", "*", "/", "%", "**",
        "=", "+=", "-=", "*=", "/=", "%=", "**=",
        "==", "!=", "===", "!==", "<", ">", "<=", ">=",
        "&&", "||", "!", "??", "?.", "?:",
        "&", "|", "^", "~", "<<", ">>", ">>>",
        "&=", "|=", "^=", "<<=", ">>=", ">>>=",
        "&&=", "||=", "?", "?=",  // Split to avoid trigraph warning
        "++", "--",
        "(", ")", "[", "]", "{", "}",
        ",", ";", ":", ".", "...", "=>", "?"
    };
}

TokenizedFile JavaScriptNormalizer::normalize(std::string_view source) {
    TokenizedFile result;
    result.path = "";

    TokenizerState state;
    state.source = source;

    uint32_t code_lines = 0;
    uint32_t blank_lines = 0;
    uint32_t comment_lines = 0;
    uint32_t current_line = 0;
    bool line_has_code = false;
    bool line_has_comment = false;

    while (!state.eof()) {
        // Track line changes
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

        char c = state.peek();

        // Whitespace
        if (c == ' ' || c == '\t' || c == '\r') {
            state.advance();
            continue;
        }

        // Newline
        if (c == '\n') {
            state.advance();
            state.may_be_regex = true;
            continue;
        }

        // Single-line comment
        if (c == '/' && state.peek_next() == '/') {
            line_has_comment = true;
            skip_single_line_comment(state);
            continue;
        }

        // Multi-line comment
        if (c == '/' && state.peek_next() == '*') {
            line_has_comment = true;
            skip_multi_line_comment(state);
            continue;
        }

        // Regex literal (must check before division operator)
        if (c == '/' && state.may_be_regex) {
            // Could be regex - try to parse it
            line_has_code = true;
            result.tokens.push_back(parse_regex(state));
            state.may_be_regex = false;
            continue;
        }

        // String literals
        if (c == '"' || c == '\'') {
            line_has_code = true;
            result.tokens.push_back(parse_string(state));
            state.may_be_regex = false;
            continue;
        }

        // Template literal
        if (c == '`') {
            line_has_code = true;
            result.tokens.push_back(parse_template_literal(state));
            state.may_be_regex = false;
            continue;
        }

        // Numbers
        if (is_digit(c) || (c == '.' && is_digit(state.peek_next()))) {
            line_has_code = true;
            result.tokens.push_back(parse_number(state));
            state.may_be_regex = false;
            continue;
        }

        // Identifiers and keywords
        if (is_identifier_start(c)) {
            line_has_code = true;
            auto tok = parse_identifier_or_keyword(state);

            // Update regex expectation based on token
            if (tok.type == TokenType::KEYWORD) {
                // After keywords like 'return', 'case', etc., regex is possible
                state.may_be_regex = true;
            } else {
                state.may_be_regex = false;
            }

            result.tokens.push_back(std::move(tok));
            continue;
        }

        // Operators and punctuation
        if (is_operator_char(c)) {
            line_has_code = true;
            auto tok = parse_operator(state);

            // Update regex expectation
            // After ( [ { , ; : = += etc., regex is possible
            if (tok.type == TokenType::PUNCTUATION ||
                tok.type == TokenType::OPERATOR) {
                state.may_be_regex = true;
            }

            result.tokens.push_back(std::move(tok));
            continue;
        }

        // Unknown - skip
        state.advance();
    }

    // Handle the final line
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

NormalizedToken JavaScriptNormalizer::parse_string(TokenizerState& state) {
    NormalizedToken tok{};
    tok.type = TokenType::STRING_LITERAL;
    tok.line = state.line;
    tok.column = state.column;

    const char quote = state.advance();
    std::string value;
    const size_t start_pos = state.pos;

    while (!state.eof()) {
        char c = state.peek();

        if (c == quote) {
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

    tok.length = static_cast<uint16_t>(state.pos - start_pos + 1);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = hash_placeholder(TokenType::STRING_LITERAL);

    return tok;
}

NormalizedToken JavaScriptNormalizer::parse_template_literal(TokenizerState& state) {
    NormalizedToken tok{};
    tok.type = TokenType::STRING_LITERAL;
    tok.line = state.line;
    tok.column = state.column;

    state.advance();  // Skip `
    std::string value;
    const size_t start_pos = state.pos;
    int brace_depth = 0;

    while (!state.eof()) {
        const char c = state.peek();

        if (c == '`' && brace_depth == 0) {
            state.advance();
            break;
        }

        // Handle ${...} interpolations
        if (c == '$' && state.peek_next() == '{') {
            state.advance();  // $
            state.advance();  // {
            brace_depth++;
            continue;
        }

        if (c == '{' && brace_depth > 0) {
            brace_depth++;
            state.advance();
            continue;
        }

        if (c == '}' && brace_depth > 0) {
            brace_depth--;
            state.advance();
            continue;
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

    tok.length = static_cast<uint16_t>(state.pos - start_pos + 1);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = hash_placeholder(TokenType::STRING_LITERAL);

    return tok;
}

NormalizedToken JavaScriptNormalizer::parse_number(TokenizerState& state) const
{
    NormalizedToken tok{};
    tok.type = TokenType::NUMBER_LITERAL;
    tok.line = state.line;
    tok.column = state.column;

    std::string value;
    const size_t start_pos = state.pos;

    // Check for hex, binary, octal
    if (state.peek() == '0' && !state.eof()) {
        if (const char next = state.peek_next(); next == 'x' || next == 'X') {
            // Hex
            value += state.advance();
            value += state.advance();
            while (!state.eof() && (is_hex_digit(state.peek()) || state.peek() == '_')) {
                if (state.peek() != '_') value += state.peek();
                state.advance();
            }
        } else if (next == 'b' || next == 'B') {
            // Binary
            value += state.advance();
            value += state.advance();
            while (!state.eof() && (state.peek() == '0' || state.peek() == '1' || state.peek() == '_')) {
                if (state.peek() != '_') value += state.peek();
                state.advance();
            }
        } else if (next == 'o' || next == 'O') {
            // Octal
            value += state.advance();
            value += state.advance();
            while (!state.eof() && ((state.peek() >= '0' && state.peek() <= '7') || state.peek() == '_')) {
                if (state.peek() != '_') value += state.peek();
                state.advance();
            }
        } else {
            value += state.advance();
        }
    }

    // Integer or float part
    if (value.empty()) {
        while (!state.eof() && (is_digit(state.peek()) || state.peek() == '_')) {
            if (state.peek() != '_') value += state.peek();
            state.advance();
        }
    }

    // Decimal part
    if (state.peek() == '.' && is_digit(state.peek_next())) {
        value += state.advance();
        while (!state.eof() && (is_digit(state.peek()) || state.peek() == '_')) {
            if (state.peek() != '_') value += state.peek();
            state.advance();
        }
    }

    // Exponent part
    if (state.peek() == 'e' || state.peek() == 'E') {
        value += state.advance();
        if (state.peek() == '+' || state.peek() == '-') {
            value += state.advance();
        }
        while (!state.eof() && (is_digit(state.peek()) || state.peek() == '_')) {
            if (state.peek() != '_') value += state.peek();
            state.advance();
        }
    }

    // BigInt suffix
    if (state.peek() == 'n') {
        value += state.advance();
    }

    tok.length = static_cast<uint16_t>(state.pos - start_pos);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = hash_placeholder(TokenType::NUMBER_LITERAL);

    return tok;
}

NormalizedToken JavaScriptNormalizer::parse_identifier_or_keyword(TokenizerState& state) const
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
    if (keywords_.contains(value) || ts_keywords_.contains(value)) {
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

NormalizedToken JavaScriptNormalizer::parse_operator(TokenizerState& state) {
    NormalizedToken tok{};
    tok.line = state.line;
    tok.column = state.column;

    std::string value;
    const size_t start_pos = state.pos;

    // Try to match the longest operator first
    // Check 4-character operators
    if (state.pos + 3 < state.source.size()) {
        if (std::string four(state.source.substr(state.pos, 4)); four == ">>>=") {
            value = four;
            for (int i = 0; i < 4; i++) state.advance();
        }
    }

    // Check 3-character operators
    if (value.empty() && state.pos + 2 < state.source.size()) {
        if (const std::string three(state.source.substr(state.pos, 3)); three == "===" || three == "!==" || three == ">>>" ||
            three == "..." || three == "<<=" || three == ">>=" ||
            three == "**=" || three == "&&=" || three == "||=" ||
            three == "?" "?=") {  // Split to avoid trigraph warning
            value = three;
            state.advance();
            state.advance();
            state.advance();
        }
    }

    // Check 2-character operators
    if (value.empty() && state.pos + 1 < state.source.size()) {
        if (const std::string two(state.source.substr(state.pos, 2)); two == "==" || two == "!=" || two == "<=" || two == ">=" ||
            two == "+=" || two == "-=" || two == "*=" || two == "/=" ||
            two == "%=" || two == "&=" || two == "|=" || two == "^=" ||
            two == "**" || two == "++" || two == "--" || two == "&&" ||
            two == "||" || two == "??" || two == "?." || two == "=>" ||
            two == "<<" || two == ">>") {
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

    // Classify as operator or punctuation
    if (value == "(" || value == ")" || value == "[" || value == "]" ||
        value == "{" || value == "}" || value == "," || value == ":" ||
        value == ";" || value == ".") {
        tok.type = TokenType::PUNCTUATION;
    } else {
        tok.type = TokenType::OPERATOR;
    }

    return tok;
}

NormalizedToken JavaScriptNormalizer::parse_regex(TokenizerState& state) const
{
    NormalizedToken tok{};
    tok.type = TokenType::STRING_LITERAL;  // Treat regex like string for normalization
    tok.line = state.line;
    tok.column = state.column;

    state.advance();  // Skip /
    std::string value;
    const size_t start_pos = state.pos;
    bool in_char_class = false;

    while (!state.eof()) {
        const char c = state.peek();

        if (c == '\n') {
            // Not a regex after all, it was a division
            // Return as operator
            tok.type = TokenType::OPERATOR;
            tok.length = 1;
            tok.original_hash = hash_string("/");
            tok.normalized_hash = tok.original_hash;
            return tok;
        }

        if (c == '\\' && !state.eof()) {
            value += state.advance();
            if (!state.eof()) {
                value += state.advance();
            }
            continue;
        }

        if (c == '[') {
            in_char_class = true;
        } else if (c == ']') {
            in_char_class = false;
        }

        if (c == '/' && !in_char_class) {
            state.advance();
            break;
        }

        value += c;
        state.advance();
    }

    // Parse flags
    while (!state.eof() && is_identifier_char(state.peek())) {
        state.advance();
    }

    tok.length = static_cast<uint16_t>(state.pos - start_pos + 1);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = hash_placeholder(TokenType::STRING_LITERAL);

    return tok;
}

void JavaScriptNormalizer::skip_single_line_comment(TokenizerState& state) {
    while (!state.eof() && state.peek() != '\n') {
        state.advance();
    }
}

void JavaScriptNormalizer::skip_multi_line_comment(TokenizerState& state) {
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

bool JavaScriptNormalizer::is_identifier_start(char c)
{
    return std::isalpha(static_cast<unsigned char>(c)) || c == '_' || c == '$';
}

bool JavaScriptNormalizer::is_identifier_char(char c)
{
    return std::isalnum(static_cast<unsigned char>(c)) || c == '_' || c == '$';
}

bool JavaScriptNormalizer::is_digit(char c)
{
    return c >= '0' && c <= '9';
}

bool JavaScriptNormalizer::is_hex_digit(char c) {
    return is_digit(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}

bool JavaScriptNormalizer::is_operator_char(char c) {
    return c == '+' || c == '-' || c == '*' || c == '/' || c == '%' ||
           c == '=' || c == '<' || c == '>' || c == '!' || c == '&' ||
           c == '|' || c == '^' || c == '~' || c == '?' || c == ':' ||
           c == '(' || c == ')' || c == '[' || c == ']' || c == '{' ||
           c == '}' || c == ',' || c == ';' || c == '.';
}

bool JavaScriptNormalizer::could_be_regex(const TokenType last_type) {
    // After these token types, / could start a regex
    return last_type == TokenType::OPERATOR ||
           last_type == TokenType::PUNCTUATION ||
           last_type == TokenType::KEYWORD;
}

}  // namespace aegis::similarity
