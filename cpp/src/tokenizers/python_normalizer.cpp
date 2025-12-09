#include "tokenizers/python_normalizer.hpp"
#include "tokenizers/js_normalizer.hpp"
#include "tokenizers/cpp_normalizer.hpp"
#include <cctype>
#include <algorithm>

namespace aegis::similarity {

PythonNormalizer::PythonNormalizer() {
    // Python 3 keywords
    keywords_ = {
        "False", "None", "True", "and", "as", "assert", "async", "await",
        "break", "class", "continue", "def", "del", "elif", "else", "except",
        "finally", "for", "from", "global", "if", "import", "in", "is",
        "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
        "while", "with", "yield"
    };

    // Built-in types (normalized differently for better Type-2 detection)
    builtin_types_ = {
        "int", "float", "str", "bool", "list", "dict", "set", "tuple",
        "bytes", "bytearray", "complex", "frozenset", "object", "type",
        "range", "slice", "memoryview", "property", "classmethod",
        "staticmethod", "super"
    };

    // Operators and punctuation
    operators_ = {
        "+", "-", "*", "/", "//", "%", "**", "@",
        "==", "!=", "<", ">", "<=", ">=",
        "&", "|", "^", "~", "<<", ">>",
        "=", "+=", "-=", "*=", "/=", "//=", "%=", "**=", "@=",
        "&=", "|=", "^=", "<<=", ">>=",
        "(", ")", "[", "]", "{", "}",
        ",", ":", ";", ".", "->", "...",
        "\\",  // Line continuation
    };
}

TokenizedFile PythonNormalizer::normalize(std::string_view source) {
    TokenizedFile result;
    result.path = "";  // Will be set by caller

    TokenizerState state;
    state.source = source;

    uint32_t code_lines = 0;
    uint32_t blank_lines = 0;
    uint32_t comment_lines = 0;
    uint32_t current_line = 0;
    bool line_has_code = false;
    bool line_has_comment = false;

    while (!state.eof()) {
        // Track line changes for metrics
        if (state.line != current_line) {
            if (current_line > 0) {
                if (line_has_code) {
                    code_lines++;
                } else if (line_has_comment) {
                    comment_lines++;
                } else {
                    blank_lines++;
                }
            }
            current_line = state.line;
            line_has_code = false;
            line_has_comment = false;
        }

        char c = state.peek();

        // Handle indentation at line start
        if (state.at_line_start && c != '\n' && c != '#') {
            size_t indent = 0;
            size_t start_pos = state.pos;
            while (!state.eof() && (state.peek() == ' ' || state.peek() == '\t')) {
                if (state.peek() == '\t') {
                    indent += 8 - (indent % 8);  // Tab stops at 8
                } else {
                    indent++;
                }
                state.advance();
            }

            // Don't emit indent tokens for blank lines or comment-only lines
            if (!state.eof() && state.peek() != '\n' && state.peek() != '#') {
                auto indent_tokens = handle_indentation(state, indent);
                for (auto& tok : indent_tokens) {
                    result.tokens.push_back(std::move(tok));
                }
            }
            state.at_line_start = false;

            if (state.eof()) break;
            c = state.peek();
        }

        // Skip whitespace (not at line start)
        if (c == ' ' || c == '\t') {
            state.advance();
            continue;
        }

        // Newline
        if (c == '\n') {
            // Emit newline token for significant line breaks
            if (!result.tokens.empty() &&
                result.tokens.back().type != TokenType::NEWLINE) {
                NormalizedToken tok;
                tok.type = TokenType::NEWLINE;
                tok.original_hash = hash_string("\n");
                tok.normalized_hash = tok.original_hash;
                tok.line = state.line;
                tok.column = state.column;
                tok.length = 1;
                result.tokens.push_back(tok);
            }
            state.advance();
            continue;
        }

        // Comments
        if (c == '#') {
            line_has_comment = true;
            skip_comment(state);
            continue;
        }

        // String literals
        if (c == '"' || c == '\'') {
            line_has_code = true;
            result.tokens.push_back(parse_string(state));
            continue;
        }

        // f-strings, r-strings, b-strings
        if ((c == 'f' || c == 'F' || c == 'r' || c == 'R' || c == 'b' || c == 'B') &&
            (state.peek_next() == '"' || state.peek_next() == '\'')) {
            line_has_code = true;
            state.advance();  // Skip prefix
            result.tokens.push_back(parse_string(state));
            continue;
        }

        // fr"" or rf"" strings
        if ((c == 'f' || c == 'F' || c == 'r' || c == 'R') &&
            (state.peek_next() == 'r' || state.peek_next() == 'R' ||
             state.peek_next() == 'f' || state.peek_next() == 'F')) {
            size_t pos = state.pos + 2;
            if (pos < state.source.size() &&
                (state.source[pos] == '"' || state.source[pos] == '\'')) {
                line_has_code = true;
                state.advance();  // Skip first prefix
                state.advance();  // Skip second prefix
                result.tokens.push_back(parse_string(state));
                continue;
            }
        }

        // Numbers
        if (is_digit(c) || (c == '.' && is_digit(state.peek_next()))) {
            line_has_code = true;
            result.tokens.push_back(parse_number(state));
            continue;
        }

        // Identifiers and keywords
        if (is_identifier_start(c)) {
            line_has_code = true;
            result.tokens.push_back(parse_identifier_or_keyword(state));
            continue;
        }

        // Operators and punctuation
        if (is_operator_char(c)) {
            line_has_code = true;
            result.tokens.push_back(parse_operator(state));
            continue;
        }

        // Unknown character - skip
        state.advance();
    }

    // Handle final line
    if (current_line > 0) {
        if (line_has_code) {
            code_lines++;
        } else if (line_has_comment) {
            comment_lines++;
        } else {
            blank_lines++;
        }
    }

    // Handle remaining dedents at end of file
    while (state.indent_stack.size() > 1) {
        state.indent_stack.pop_back();
        NormalizedToken tok;
        tok.type = TokenType::DEDENT;
        tok.original_hash = hash_string("DEDENT");
        tok.normalized_hash = tok.original_hash;
        tok.line = state.line;
        tok.column = 1;
        tok.length = 0;
        result.tokens.push_back(tok);
    }

    // Calculate total lines: if file ends with newline, don't count the empty line after it
    // If the source is empty, total_lines is 0
    // If the source has content but no newline, line will be 1
    // If source ends with \n, the line counter has already incremented past the last actual line
    result.total_lines = source.empty() ? 0 : (state.column == 1 && state.line > 1 ? state.line - 1 : state.line);
    result.code_lines = code_lines;
    result.blank_lines = blank_lines;
    result.comment_lines = comment_lines;

    return result;
}

NormalizedToken PythonNormalizer::parse_string(TokenizerState& state) {
    NormalizedToken tok;
    tok.type = TokenType::STRING_LITERAL;
    tok.line = state.line;
    tok.column = state.column;

    char quote = state.advance();
    bool triple = false;

    // Check for triple-quoted string
    if (state.peek() == quote && state.peek_next() == quote) {
        state.advance();
        state.advance();
        triple = true;
    }

    std::string value;
    size_t start_pos = state.pos;

    while (!state.eof()) {
        char c = state.peek();

        if (triple) {
            // Triple-quoted: look for three quotes
            if (c == quote && state.peek_next() == quote) {
                size_t pos = state.pos + 2;
                if (pos < state.source.size() && state.source[pos] == quote) {
                    state.advance();
                    state.advance();
                    state.advance();
                    break;
                }
            }
        } else {
            // Single-quoted: end at matching quote (not escaped)
            if (c == quote) {
                state.advance();
                break;
            }
            if (c == '\n') {
                // Unterminated string
                break;
            }
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

    tok.length = static_cast<uint16_t>(state.pos - start_pos + (triple ? 3 : 1));
    tok.original_hash = hash_string(value);
    tok.normalized_hash = hash_placeholder(TokenType::STRING_LITERAL);

    return tok;
}

NormalizedToken PythonNormalizer::parse_number(TokenizerState& state) {
    NormalizedToken tok;
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
            // Regular number starting with 0
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

    // Complex number suffix
    if (state.peek() == 'j' || state.peek() == 'J') {
        value += state.advance();
    }

    tok.length = static_cast<uint16_t>(state.pos - start_pos);
    tok.original_hash = hash_string(value);
    tok.normalized_hash = hash_placeholder(TokenType::NUMBER_LITERAL);

    return tok;
}

NormalizedToken PythonNormalizer::parse_identifier_or_keyword(TokenizerState& state) {
    NormalizedToken tok;
    tok.line = state.line;
    tok.column = state.column;

    std::string value;
    size_t start_pos = state.pos;

    while (!state.eof() && is_identifier_char(state.peek())) {
        value += state.advance();
    }

    tok.length = static_cast<uint16_t>(state.pos - start_pos);
    tok.original_hash = hash_string(value);

    // Check if it's a keyword
    if (keywords_.count(value)) {
        tok.type = TokenType::KEYWORD;
        tok.normalized_hash = tok.original_hash;  // Keywords keep their hash
    }
    // Check if it's a built-in type
    else if (builtin_types_.count(value)) {
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

NormalizedToken PythonNormalizer::parse_operator(TokenizerState& state) {
    NormalizedToken tok;
    tok.line = state.line;
    tok.column = state.column;

    std::string value;
    size_t start_pos = state.pos;

    // Try to match longest operator first
    // Check 3-character operators
    if (state.pos + 2 < state.source.size()) {
        std::string three(state.source.substr(state.pos, 3));
        if (three == "..." || three == "<<=" || three == ">>=" ||
            three == "**=" || three == "//=") {
            value = three;
            state.advance();
            state.advance();
            state.advance();
        }
    }

    // Check 2-character operators
    if (value.empty() && state.pos + 1 < state.source.size()) {
        std::string two(state.source.substr(state.pos, 2));
        if (two == "==" || two == "!=" || two == "<=" || two == ">=" ||
            two == "+=" || two == "-=" || two == "*=" || two == "/=" ||
            two == "%=" || two == "&=" || two == "|=" || two == "^=" ||
            two == "**" || two == "//" || two == "<<" || two == ">>" ||
            two == "->" || two == "@=") {
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
    tok.normalized_hash = tok.original_hash;  // Operators keep their hash

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

void PythonNormalizer::skip_comment(TokenizerState& state) {
    while (!state.eof() && state.peek() != '\n') {
        state.advance();
    }
}

std::vector<NormalizedToken> PythonNormalizer::handle_indentation(
    TokenizerState& state,
    size_t current_indent
) {
    std::vector<NormalizedToken> tokens;
    size_t prev_indent = state.indent_stack.back();

    if (current_indent > prev_indent) {
        state.indent_stack.push_back(current_indent);
        NormalizedToken tok;
        tok.type = TokenType::INDENT;
        tok.original_hash = hash_string("INDENT");
        tok.normalized_hash = tok.original_hash;
        tok.line = state.line;
        tok.column = 1;
        tok.length = static_cast<uint16_t>(current_indent);
        tokens.push_back(tok);
    } else if (current_indent < prev_indent) {
        while (!state.indent_stack.empty() &&
               state.indent_stack.back() > current_indent) {
            state.indent_stack.pop_back();
            NormalizedToken tok;
            tok.type = TokenType::DEDENT;
            tok.original_hash = hash_string("DEDENT");
            tok.normalized_hash = tok.original_hash;
            tok.line = state.line;
            tok.column = 1;
            tok.length = 0;
            tokens.push_back(tok);
        }
    }

    return tokens;
}

bool PythonNormalizer::is_identifier_start(char c) const {
    return std::isalpha(static_cast<unsigned char>(c)) || c == '_';
}

bool PythonNormalizer::is_identifier_char(char c) const {
    return std::isalnum(static_cast<unsigned char>(c)) || c == '_';
}

bool PythonNormalizer::is_digit(char c) const {
    return c >= '0' && c <= '9';
}

bool PythonNormalizer::is_hex_digit(char c) const {
    return is_digit(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}

bool PythonNormalizer::is_operator_char(char c) const {
    return c == '+' || c == '-' || c == '*' || c == '/' || c == '%' ||
           c == '=' || c == '<' || c == '>' || c == '!' || c == '&' ||
           c == '|' || c == '^' || c == '~' || c == '@' || c == '(' ||
           c == ')' || c == '[' || c == ']' || c == '{' || c == '}' ||
           c == ',' || c == ':' || c == ';' || c == '.';
}

// Factory function implementations
std::unique_ptr<TokenNormalizer> create_normalizer(Language language) {
    switch (language) {
        case Language::PYTHON:
            return std::make_unique<PythonNormalizer>();
        case Language::JAVASCRIPT:
        case Language::TYPESCRIPT:
            return std::make_unique<JavaScriptNormalizer>();
        case Language::CPP:
        case Language::C:
            return std::make_unique<CppNormalizer>();
        default:
            return nullptr;
    }
}

std::unique_ptr<TokenNormalizer> create_normalizer_for_file(std::string_view extension) {
    return create_normalizer(detect_language(extension));
}

}  // namespace aegis::similarity
