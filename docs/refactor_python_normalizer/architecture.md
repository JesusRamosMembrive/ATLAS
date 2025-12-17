# Refactoring Plan: PythonNormalizer::normalize

## Context & Requirements
The `PythonNormalizer::normalize` function in `python_normalizer.cpp` has high cyclomatic complexity (likely > 50). It handles tokenization logic for Python code, including indentation, comments, strings, numbers, identifiers, and operators in a single large loop.
The goal is to refactor this function into smaller, focused helper functions to improve readability and maintainability, adhering to Clean Code principles.

## Stage Assessment
- **Stage**: 2 (Structuring/Refactoring)
- **Goal**: Reduce complexity without changing behavior.
- **Pain Point**: High cyclomatic complexity makes the code hard to read, test, and maintain.

## Component Structure
The `normalize` function will be broken down. The `PythonNormalizer` class will gain private helper methods.

### Existing Class
`aegis::similarity::PythonNormalizer`

### New Private Methods
We will extract logic into these methods (names are tentative):

1.  `handle_line_metrics(TokenizerState& state, uint32_t& current_line, ...)`: Updates line counts.
2.  `process_indentation(TokenizerState& state, TokenizedFile& result)`: Handles line start indentation.
3.  `skip_whitespace(TokenizerState& state)`: Skips spaces and tabs.
4.  `process_newline(TokenizerState& state, TokenizedFile& result)`: Handles newlines.
5.  `process_comment(TokenizerState& state, bool& line_has_comment)`: Handles comments.
6.  `process_import(TokenizerState& state, bool& line_has_code)`: Detects and skips imports.
7.  `process_string_literal(TokenizerState& state, TokenizedFile& result, bool& line_has_code, bool& line_has_comment)`: Handles strings, docstrings, and prefixes (f, r, b).
8.  `process_number(TokenizerState& state, TokenizedFile& result, bool& line_has_code)`: Handles numbers.
9.  `process_identifier(TokenizerState& state, TokenizedFile& result, bool& line_has_code)`: Handles identifiers/keywords.
10. `process_operator(TokenizerState& state, TokenizedFile& result, bool& line_has_code)`: Handles operators.

## Technology Stack
- C++17 (existing project standard)
- GTest for verification

## Build Order
1.  **Modify Header**: Add new private method declarations to `python_normalizer.hpp`.
2.  **Implement Helpers**: Move logic from `normalize` to new methods in `python_normalizer.cpp` one by one or in groups.
3.  **Update Normalize**: Replace inline logic with method calls.

## Testing Strategy
1.  **Baseline**: Run existing tests (`similarity_tests`) to ensure they pass before changes.
2.  **Incremental**: Run tests after extracting each logical block (if possible) or after the full refactor.
3.  **Verification**: All existing tests in `test_python_normalizer.cpp` MUST pass. No new tests are strictly needed as we are not adding features, but regression testing is critical.

## Evolution Triggers
- N/A (this is a cleanup task)
