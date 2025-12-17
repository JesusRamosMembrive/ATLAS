# Call Flow v2 - Implementation Progress

## Overview

Call Flow v2 provides function call chain visualization for Python projects. Given an entry point function, it extracts all reachable calls and displays them as an interactive React Flow graph.

## Completed Features

### Backend (Python)

#### 1. Data Models (`code_map/v2/call_flow/models.py`)
- **ResolutionStatus enum**: Tracks how each call was resolved
  - `RESOLVED_PROJECT`: Symbol found in project code
  - `IGNORED_BUILTIN`: Python builtin (print, len, etc.)
  - `IGNORED_STDLIB`: Standard library (os, json, etc.)
  - `IGNORED_THIRD_PARTY`: External package
  - `UNRESOLVED`: Could not determine target
  - `AMBIGUOUS`: Multiple possible targets

- **CallNode**: Represents a function/method in the graph
  - Stable symbol ID format: `{rel_path}:{line}:{col}:{kind}:{name}`
  - Includes resolution status and optional reasons

- **CallEdge**: Represents a call from source to target
  - Includes call expression and resolution status

- **CallGraph**: Complete graph structure
  - `ignored_calls: List[IgnoredCall]` - External calls not expanded
  - `unresolved_calls: List[str]` - Calls that couldn't be resolved
  - `diagnostics: Dict` - Metadata (cycles, truncation, etc.)

- **IgnoredCall**: Details about ignored external calls
  - Expression, status, line number, module hint

#### 2. Constants (`code_map/v2/call_flow/constants.py`)
- `PYTHON_BUILTINS`: Set of Python builtin names
- `is_stdlib()`: Function to detect standard library modules

#### 3. Extractor (`code_map/v2/call_flow/extractor.py`)
- **tree-sitter based** Python parsing
- **Resolution features**:
  - `_classify_external()`: Categorizes external calls
  - `_make_symbol_id()`: Generates stable, deterministic IDs
  - `_resolve_call_v2()`: Full resolution with status tracking
- **Per-branch cycle detection**: Uses call stack instead of global visited set
- **Multi-file support**: Resolves imports within project

#### 4. API Endpoints (`code_map/api/call_flow.py`)
- `GET /api/call-flow/entry-points/{file_path}`: List functions/methods in a file
- `GET /api/call-flow/{file_path}?function=name&max_depth=5`: Extract call graph

#### 5. File Browser Endpoint (`code_map/api/settings.py`)
- `GET /api/settings/list-files?path=/some/path&extensions=.py`: List directories and files

### Frontend (React/TypeScript)

#### 1. FileBrowserModal (`frontend/src/components/settings/FileBrowserModal.tsx`)
- Browse directories and select Python files
- Shows file sizes
- Uses emoji icons for visual clarity

#### 2. CallFlowView (`frontend/src/components/CallFlowView.tsx`)
- Updated to use FileBrowserModal for file selection
- Entry points sidebar grouped by class
- Depth control slider
- Stats panel showing node/edge counts

#### 3. API Client (`frontend/src/api/client.ts`)
- `listFiles()`: Fetches directory contents with file filtering

## Architecture

```
User selects file → FileBrowserModal
       ↓
Load entry points → GET /api/call-flow/entry-points/{file}
       ↓
User selects function
       ↓
Extract call flow → GET /api/call-flow/{file}?function=name
       ↓
Display graph → CallFlowGraph (React Flow)
```

## MVP Scope (What's Implemented)

1. Direct function calls: `func()`
2. Import resolution: `import foo`, `from foo import bar`
3. `self.method()` within class
4. Constructor calls: `ClassName()` → `__init__`
5. Multi-file resolution within project
6. **NEW: Type inference for `obj.method()` resolution**

## Type Inference (NEW)

### TypeResolver Module (`code_map/v2/call_flow/type_resolver.py`)

Resolves `obj.method()` calls by inferring the type of `obj` through:

1. **Constructor assignments**: `loader = FileLoader()` → `loader` is `FileLoader`
2. **Type annotations**: `loader: FileLoader = ...` → `loader` is `FileLoader`
3. **Return types**: `result = get_loader()` where `def get_loader() -> FileLoader` → `result` is `FileLoader`

### Key Classes

- **TypeInfo**: Stores inferred type information (name, module, confidence, source)
- **ScopeInfo**: Holds variables and parameters type mappings for a function
- **TypeResolver**: Main resolver that analyzes function scopes

### Priority Order

When multiple type sources exist:
1. Parameters (highest) - from function signature
2. Annotations - explicit type hints
3. Constructor assignments - PascalCase calls
4. Return types (lowest) - from called functions

### Features

- Handles `Optional[T]`, `Union[T, None]`, `T | None` extracting base type
- Resolves imported function return types across files
- Caches return types per file for performance
- Filters out Python builtins (dict, list, str, etc.)

### Tests

```bash
# Run type resolver tests
pytest tests/test_type_resolver.py -v
```

## Not Yet Implemented (Future Work)

- Inheritance/MRO resolution
- `self.attr.method()` chained calls (multi-level attribute access)

## Testing

```bash
# Start backend
python -m code_map.cli run --root /path/to/project

# Test entry points
curl "http://localhost:8010/api/call-flow/entry-points/path/to/file.py"

# Test call flow extraction
curl "http://localhost:8010/api/call-flow/path/to/file.py?function=main&max_depth=5"
```

## Files Modified/Created

| File | Status |
|------|--------|
| `code_map/v2/call_flow/models.py` | Modified |
| `code_map/v2/call_flow/extractor.py` | Modified |
| `code_map/v2/call_flow/constants.py` | Created |
| `code_map/v2/call_flow/type_resolver.py` | **Created** (NEW) |
| `code_map/v2/call_flow/__init__.py` | Modified |
| `code_map/api/call_flow.py` | Modified |
| `code_map/api/schemas.py` | Modified |
| `code_map/api/settings.py` | Modified |
| `frontend/src/api/client.ts` | Modified |
| `frontend/src/components/CallFlowView.tsx` | Modified |
| `frontend/src/components/settings/FileBrowserModal.tsx` | Created |
| `tests/test_type_resolver.py` | **Created** (NEW) |
