# Refactoring Plan: CppNormalizer::normalize

## Context & Requirements
The `CppNormalizer::normalize` function in `cpp_normalizer.cpp` has high cyclomatic complexity. It handles tokenization logic for C/C++ code, including preprocessor directives, comments, strings (including raw and prefixed), numbers, identifiers, and operators in a single large loop (~130 lines).
The goal is to refactor this function into smaller, focused helper functions to improve readability and maintainability, adhering to Clean Code principles.

## Stage Assessment
- **Stage**: 2 (Structuring/Refactoring)
- **Goal**: Reduce complexity without changing behavior.
- **Pain Point**: High cyclomatic complexity makes the code hard to read and maintain.

## Component Structure
The `normalize` function will be broken down. The `CppNormalizer` class will gain private helper methods.

### Existing Class
`aegis::similarity::CppNormalizer`

### New Private Methods
We will extract logic into these methods (names tentative):

1.  `handle_line_metrics(TokenizerState& state, uint32_t& current_line, ...)`: Updates line counts.
2.  `skip_whitespace_and_newline(TokenizerState& state)`: Handles spaces, tabs, and newlines.
3.  `process_preprocessor(TokenizerState& state, bool& line_has_code)`: Handles `#` directives.
4.  `process_comment(TokenizerState& state, bool& line_has_comment)`: Handles `//` and `/* */` comments.
5.  `process_string_literal(TokenizerState& state, TokenizedFile& result, bool& line_has_code)`: Handles regular strings, char literals, and raw strings.
6.  `process_number(TokenizerState& state, TokenizedFile& result, bool& line_has_code)`: Handles numbers.
7.  `process_identifier(TokenizerState& state, TokenizedFile& result, bool& line_has_code)`: Handles identifiers/keywords.
8.  `process_operator(TokenizerState& state, TokenizedFile& result, bool& line_has_code)`: Handles operators.

## Technology Stack
- C++17 (existing project standard)
- GTest for verification

## Build Order
1.  **Modify Header**: Add new private method declarations to `cpp_normalizer.hpp`.
2.  **Implement Helpers**: Move logic from `normalize` to new methods in `cpp_normalizer.cpp`.
3.  **Update Normalize**: Replace inline logic with method calls.

## Testing Strategy
1.  **Baseline**: Run existing tests (`similarity_tests`) to ensure they pass before changes.
2.  **Verification**: All existing tests in `test_cpp_normalizer.cpp` MUST pass.
    - Command: `cd build && make similarity_tests && ./similarity_tests` (or equivalent via cmake)
