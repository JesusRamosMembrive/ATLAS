# Architecture: Enhanced Code Metrics

## 1. Context and Problem
The current analysis engine (`code_map`) focuses on detecting symbols (functions, classes) and file-level metadata (total LOC). The "Stage Detection" logic (`stage_config.py`) aggregates this to guide project evolution.

However, granular quality metrics are missing:
*   **LOC per Function**: We know where a function starts, but not its size.
*   **Cyclomatic Complexity**: We don't measure the complexity of the control flow.

This feature aims to calculate and expose these metrics for supported languages (starting with Python and C/C++).

## 2. Data Model Changes

### 2.1 `SymbolInfo` Update
We will extend `SymbolInfo` in `code_map/models.py` to support an extensible metrics dictionary. This avoids adding specific fields for every potential future metric.

```python
@dataclass(slots=True)
class SymbolInfo:
    # ... existing fields ...
    metrics: Dict[str, Union[int, float]] = field(default_factory=dict)
```

**Standard Metrics Keys:**
*   `"loc"`: Lines of Code (physical lines).
*   `"complexity"`: Cyclomatic Complexity Number (CCN).

## 3. Analyzer Implementation

### 3.1 Python (`code_map/analyzer.py`)
Utilize the existing AST parsing.

*   **LOC Calculation**: Use `node.end_lineno - node.lineno + 1` (available in Python 3.8+).
*   **Complexity Calculation**: Implement a `ComplexityVisitor(ast.NodeVisitor)` that traverses the function body.
    *   Base complexity: 1
    *   Increments (+1) for: `If`, `While`, `For`, `AsyncFor`, `ExceptHandler`, `With` (optional, usually not counted in McCabe but checking style), `Assert`, `And/Or` boolean operators (if strict).
    *   *Decision*: We will start with standard McCabe (Control Flow): `If`, `While`, `For`, `Except`, `Case` (Match).

### 3.2 C/C++ (`code_map/c_analyzer.py`)
Utilize the existing Tree-sitter parsing.

*   **LOC Calculation**: `node.end_point[0] - node.start_point[0] + 1`.
*   **Complexity Calculation**: Recursive traversal of the `function_definition` node.
    *   Count distinct node types: `if_statement`, `while_statement`, `for_statement`, `case_statement`, `catch_clause`, `conditional_expression` (ternary).

## 4. API & Frontend Impact
*   **API**: Since `FileSummary` embeds `SymbolInfo`, the existing endpoints (`/api/files/{path}` and `/api/tree`) will automatically serialize the new `metrics` field. No API schema changes are strictly required, but clients need to expect this field.
*   **Frontend**: The UI components (`SymbolTree`, `FileViewer`) can be updated to display these badges (e.g., "Complexity: 5" next to function name).

## 5. Testing Strategy
*   **Unit Tests**: Create specific test files with known complexity.
    *   e.g., `def complex_func(): if A: return 1 else: return 2` -> Complexity 2.
*   **Integration**: Run `scanner.py` on the AEGIS codebase itself and inspect generic output.

## 6. Build Order
1.  **Models**: Update `SymbolInfo` in `code_map/models.py`.
2.  **Python**: Implement logic in `code_map/analyzer.py`.
3.  **C/C++**: Implement logic in `code_map/c_analyzer.py`.
4.  **Verification**: Run tests.
