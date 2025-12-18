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

// -----------------------------------------------------------------------------
// Normalize helpers (reduce cyclomatic complexity of normalize)
// -----------------------------------------------------------------------------

void JavaScriptNormalizer::update_line_metrics(TokenizerState& state, LineMetrics& metrics) {
    if (state.line != metrics.current_line) {
        if (metrics.current_line > 0) {
            if (metrics.line_has_code) {
                metrics.code_lines++;
            } else if (metrics.line_has_comment) {
                metrics.comment_lines++;
            } else {
                metrics.blank_lines++;
            }
        }
        metrics.current_line = state.line;
        metrics.line_has_code = false;
        metrics.line_has_comment = false;
    }
}

bool JavaScriptNormalizer::skip_whitespace(TokenizerState& state, char c) {
    if (c == ' ' || c == '\t' || c == '\r') {
        state.advance();
        return true;
    }
    return false;
}

bool JavaScriptNormalizer::process_newline(TokenizerState& state, char c) {
    if (c != '\n') return false;
    state.advance();
    state.may_be_regex = true;
    return true;
}

bool JavaScriptNormalizer::process_single_line_comment(TokenizerState& state, char c, LineMetrics& metrics) const {
    if (c != '/' || state.peek_next() != '/') return false;
    metrics.line_has_comment = true;
    skip_single_line_comment(state);
    return true;
}

bool JavaScriptNormalizer::process_multi_line_comment(TokenizerState& state, char c, LineMetrics& metrics) const {
    if (c != '/' || state.peek_next() != '*') return false;
    metrics.line_has_comment = true;
    skip_multi_line_comment(state);
    return true;
}

bool JavaScriptNormalizer::process_regex(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics) {
    if (c != '/' || !state.may_be_regex) return false;
    metrics.line_has_code = true;
    result.tokens.push_back(parse_regex(state));
    state.may_be_regex = false;
    return true;
}

bool JavaScriptNormalizer::process_string(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics) {
    if (c != '"' && c != '\'') return false;
    metrics.line_has_code = true;
    result.tokens.push_back(parse_string(state));
    state.may_be_regex = false;
    return true;
}

bool JavaScriptNormalizer::process_template_literal(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics) {
    if (c != '`') return false;
    metrics.line_has_code = true;
    result.tokens.push_back(parse_template_literal(state));
    state.may_be_regex = false;
    return true;
}

bool JavaScriptNormalizer::process_number(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics) const {
    if (!is_digit(c) && !(c == '.' && is_digit(state.peek_next()))) return false;
    metrics.line_has_code = true;
    result.tokens.push_back(parse_number(state));
    state.may_be_regex = false;
    return true;
}

bool JavaScriptNormalizer::process_identifier(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics) {
    if (!is_identifier_start(c)) return false;
    metrics.line_has_code = true;
    auto tok = parse_identifier_or_keyword(state);
    // After keywords like 'return', 'case', etc., regex is possible
    state.may_be_regex = (tok.type == TokenType::KEYWORD);
    result.tokens.push_back(std::move(tok));
    return true;
}

bool JavaScriptNormalizer::process_operator(TokenizerState& state, char c, TokenizedFile& result, LineMetrics& metrics) {
    if (!is_operator_char(c)) return false;
    metrics.line_has_code = true;
    auto tok = parse_operator(state);
    // After ( [ { , ; : = += etc., regex is possible
    state.may_be_regex = (tok.type == TokenType::PUNCTUATION || tok.type == TokenType::OPERATOR);
    result.tokens.push_back(std::move(tok));
    return true;
}

void JavaScriptNormalizer::finalize_metrics(const TokenizerState& state, const LineMetrics& metrics,
                                            std::string_view source, TokenizedFile& result) {
    // Handle the final line
    uint32_t final_code_lines = metrics.code_lines;
    uint32_t final_comment_lines = metrics.comment_lines;
    uint32_t final_blank_lines = metrics.blank_lines;

    if (metrics.current_line > 0) {
        if (metrics.line_has_code) final_code_lines++;
        else if (metrics.line_has_comment) final_comment_lines++;
        else final_blank_lines++;
    }

    result.total_lines = source.empty() ? 0 :
        (state.column == 1 && state.line > 1 ? state.line - 1 : state.line);
    result.code_lines = final_code_lines;
    result.blank_lines = final_blank_lines;
    result.comment_lines = final_comment_lines;
}

// -----------------------------------------------------------------------------
// Main normalize (refactored to use helpers)
// -----------------------------------------------------------------------------

TokenizedFile JavaScriptNormalizer::normalize(std::string_view source) {
    TokenizedFile result;
    result.path = "";

    TokenizerState state;
    state.source = source;

    LineMetrics metrics{};

    while (!state.eof()) {
        update_line_metrics(state, metrics);
        char c = state.peek();

        // Process each token type (early return pattern)
        if (skip_whitespace(state, c)) continue;
        if (process_newline(state, c)) continue;
        if (process_single_line_comment(state, c, metrics)) continue;
        if (process_multi_line_comment(state, c, metrics)) continue;
        if (process_regex(state, c, result, metrics)) continue;
        if (process_string(state, c, result, metrics)) continue;
        if (process_template_literal(state, c, result, metrics)) continue;
        if (process_number(state, c, result, metrics)) continue;
        if (process_identifier(state, c, result, metrics)) continue;
        if (process_operator(state, c, result, metrics)) continue;

        // Unknown - skip
        state.advance();
    }

    finalize_metrics(state, metrics, source, result);
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

// -----------------------------------------------------------------------------
// Number parsing helpers (reduce cyclomatic complexity)
// -----------------------------------------------------------------------------

bool JavaScriptNormalizer::parse_hex_number(TokenizerState& state, std::string& value) {
    if (state.peek() != '0' || state.eof()) return false;
    const char next = state.peek_next();
    if (next != 'x' && next != 'X') return false;

    value += state.advance();  // '0'
    value += state.advance();  // 'x' or 'X'
    while (!state.eof() && (is_hex_digit(state.peek()) || state.peek() == '_')) {
        if (state.peek() != '_') value += state.peek();
        state.advance();
    }
    return true;
}

bool JavaScriptNormalizer::parse_binary_number(TokenizerState& state, std::string& value) {
    if (state.peek() != '0' || state.eof()) return false;
    const char next = state.peek_next();
    if (next != 'b' && next != 'B') return false;

    value += state.advance();  // '0'
    value += state.advance();  // 'b' or 'B'
    while (!state.eof() && (state.peek() == '0' || state.peek() == '1' || state.peek() == '_')) {
        if (state.peek() != '_') value += state.peek();
        state.advance();
    }
    return true;
}

bool JavaScriptNormalizer::parse_octal_number(TokenizerState& state, std::string& value) {
    if (state.peek() != '0' || state.eof()) return false;
    const char next = state.peek_next();
    if (next != 'o' && next != 'O') return false;

    value += state.advance();  // '0'
    value += state.advance();  // 'o' or 'O'
    while (!state.eof() && ((state.peek() >= '0' && state.peek() <= '7') || state.peek() == '_')) {
        if (state.peek() != '_') value += state.peek();
        state.advance();
    }
    return true;
}

void JavaScriptNormalizer::parse_integer_part(TokenizerState& state, std::string& value) {
    // Handle leading zero without special prefix
    if (state.peek() == '0') {
        value += state.advance();
        return;
    }
    // Regular integer digits
    while (!state.eof() && (is_digit(state.peek()) || state.peek() == '_')) {
        if (state.peek() != '_') value += state.peek();
        state.advance();
    }
}

void JavaScriptNormalizer::parse_decimal_part(TokenizerState& state, std::string& value) {
    if (state.peek() != '.' || !is_digit(state.peek_next())) return;

    value += state.advance();  // '.'
    while (!state.eof() && (is_digit(state.peek()) || state.peek() == '_')) {
        if (state.peek() != '_') value += state.peek();
        state.advance();
    }
}

void JavaScriptNormalizer::parse_exponent_part(TokenizerState& state, std::string& value) {
    if (state.peek() != 'e' && state.peek() != 'E') return;

    value += state.advance();  // 'e' or 'E'
    if (state.peek() == '+' || state.peek() == '-') {
        value += state.advance();
    }
    while (!state.eof() && (is_digit(state.peek()) || state.peek() == '_')) {
        if (state.peek() != '_') value += state.peek();
        state.advance();
    }
}

void JavaScriptNormalizer::skip_bigint_suffix(TokenizerState& state, std::string& value) {
    if (state.peek() == 'n') {
        value += state.advance();
    }
}

// -----------------------------------------------------------------------------
// Main parse_number (refactored to use helpers)
// -----------------------------------------------------------------------------

NormalizedToken JavaScriptNormalizer::parse_number(TokenizerState& state) const
{
    NormalizedToken tok{};
    tok.type = TokenType::NUMBER_LITERAL;
    tok.line = state.line;
    tok.column = state.column;
    std::string value;
    const size_t start_pos = state.pos;

    // Try special number formats first (hex, binary, octal)
    const bool is_special = parse_hex_number(state, value) ||
                            parse_binary_number(state, value) ||
                            parse_octal_number(state, value);

    // Regular number if no special format matched
    if (!is_special) {
        parse_integer_part(state, value);
    }

    // Decimal and exponent parts (only for regular numbers)
    if (!is_special) {
        parse_decimal_part(state, value);
        parse_exponent_part(state, value);
    }

    // BigInt suffix (n)
    skip_bigint_suffix(state, value);

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

    // Try to match the longest operator first (4, 3, 2, then 1 character)
    if (!try_match_four_char_operator(state, value) &&
        !try_match_three_char_operator(state, value) &&
        !try_match_two_char_operator(state, value)) {
        // Single character operator
        value = state.advance();
    }

    tok.length = static_cast<uint16_t>(state.pos - start_pos);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = tok.original_hash;
    tok.type = is_punctuation(value) ? TokenType::PUNCTUATION : TokenType::OPERATOR;

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

// Operator parsing helper functions (extracted to reduce cyclomatic complexity)

bool JavaScriptNormalizer::try_match_four_char_operator(TokenizerState& state, std::string& value) {
    if (state.pos + 3 >= state.source.size()) {
        return false;
    }

    const std::string four(state.source.substr(state.pos, 4));
    if (four == ">>>=") {
        value = four;
        for (int i = 0; i < 4; i++) {
            state.advance();
        }
        return true;
    }
    return false;
}

bool JavaScriptNormalizer::try_match_three_char_operator(TokenizerState& state, std::string& value) {
    if (state.pos + 2 >= state.source.size()) {
        return false;
    }

    const std::string three(state.source.substr(state.pos, 3));
    if (three == "===" || three == "!==" || three == ">>>" ||
        three == "..." || three == "<<=" || three == ">>=" ||
        three == "**=" || three == "&&=" || three == "||=" ||
        three == "?\?=") {  // Escaped to avoid trigraph
        value = three;
        for (int i = 0; i < 3; i++) {
            state.advance();
        }
        return true;
    }
    return false;
}

bool JavaScriptNormalizer::try_match_two_char_operator(TokenizerState& state, std::string& value) {
    if (state.pos + 1 >= state.source.size()) {
        return false;
    }

    const std::string two(state.source.substr(state.pos, 2));
    if (two == "==" || two == "!=" || two == "<=" || two == ">=" ||
        two == "+=" || two == "-=" || two == "*=" || two == "/=" ||
        two == "%=" || two == "&=" || two == "|=" || two == "^=" ||
        two == "**" || two == "++" || two == "--" || two == "&&" ||
        two == "||" || two == "??" || two == "?." || two == "=>" ||
        two == "<<" || two == ">>") {
        value = two;
        state.advance();
        state.advance();
        return true;
    }
    return false;
}

bool JavaScriptNormalizer::is_punctuation(const std::string& op) {
    return op == "(" || op == ")" || op == "[" || op == "]" ||
           op == "{" || op == "}" || op == "," || op == ":" ||
           op == ";" || op == ".";
}

}  // namespace aegis::similarity
