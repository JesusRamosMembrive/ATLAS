# AEGIS C++ Similarity Detector

High-performance code similarity detection module using Rabin-Karp rolling hash algorithm.

## Features

- **Type-1 Detection**: Exact code clones (identical code)
- **Type-2 Detection**: Renamed clones (same structure, different identifiers)
- **Type-3 Detection**: Modified clones (similar code with additions/deletions)
- **Multi-language**: Python support (JS/TS/C++ planned)
- **Parallel Processing**: Multi-threaded analysis for large codebases
- **UDS Server**: Unix Domain Socket server for IPC with Python/Node backends
- **Performance Metrics**: LOC/sec, tokens/sec, timing breakdown

## Building

```bash
# Create build directory
mkdir -p build && cd build

# Configure with CMake
cmake ..

# Build
cmake --build . -j$(nproc)

# Run tests
./similarity_tests
```

## Usage

### CLI Mode

```bash
# Analyze a directory
./static_analysis_motor --root /path/to/project --ext .py

# Multiple extensions
./static_analysis_motor --root /path/to/project --ext .py --ext .js

# Compare two files
./static_analysis_motor --compare file1.py file2.py

# Enable Type-3 detection
./static_analysis_motor --root ./src --ext .py --type3

# Pretty print JSON output
./static_analysis_motor --root ./src --ext .py --pretty
```

### Server Mode (UDS)

```bash
# Start server
./static_analysis_motor --socket /tmp/aegis-cpp.sock

# Server listens for JSON-RPC style requests
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--root <path>` | Root directory to analyze | Required |
| `--ext <ext>` | File extension to include (repeatable) | `.py` |
| `--exclude <pattern>` | Glob pattern to exclude (repeatable) | `**/node_modules/**`, etc. |
| `--window <n>` | Rolling hash window size | 10 |
| `--min-tokens <n>` | Minimum tokens for clone | 30 |
| `--threshold <f>` | Similarity threshold (0.0-1.0) | 0.7 |
| `--type3` | Enable Type-3 detection | false |
| `--max-gap <n>` | Maximum gap for Type-3 | 5 |
| `--compare <f1> <f2>` | Compare two specific files | - |
| `--socket <path>` | Run as UDS server | - |
| `--pretty` | Pretty-print JSON output | false |

## Protocol (Server Mode)

### Request Format
```json
{"id": "uuid", "method": "method_name", "params": {...}}
```

### Response Format
```json
{"id": "uuid", "result": {...}}
```
or on error:
```json
{"id": "uuid", "error": {"code": -1, "message": "Error description"}}
```

### Available Methods

#### `analyze`
Run full similarity analysis on a directory.

```json
{
  "method": "analyze",
  "params": {
    "root": "/path/to/project",
    "extensions": [".py", ".js"],
    "min_tokens": 30,
    "min_similarity": 0.7,
    "type3": false,
    "threads": 4
  }
}
```

#### `compare_files`
Compare two specific files for similarity.

```json
{
  "method": "compare_files",
  "params": {
    "file1": "/path/to/file1.py",
    "file2": "/path/to/file2.py",
    "min_similarity": 0.7
  }
}
```

#### `get_hotspots`
Get files with highest duplication scores.

```json
{
  "method": "get_hotspots",
  "params": {
    "root": "/path/to/project",
    "extensions": [".py"],
    "limit": 10
  }
}
```

#### `get_file_clones`
Get all clones involving a specific file.

```json
{
  "method": "get_file_clones",
  "params": {
    "root": "/path/to/project",
    "file": "target_file.py",
    "extensions": [".py"]
  }
}
```

#### `file_tree`
Get list of files matching criteria.

```json
{
  "method": "file_tree",
  "params": {
    "root": "/path/to/project",
    "extensions": [".py"]
  }
}
```

#### `shutdown`
Gracefully stop the server.

```json
{
  "method": "shutdown",
  "params": {}
}
```

## Output Format

### Summary
```json
{
  "summary": {
    "files_analyzed": 73,
    "total_lines": 5420,
    "clone_pairs_found": 206,
    "estimated_duplication": "12.5%",
    "analysis_time_ms": 1092
  }
}
```

### Clone Entry
```json
{
  "clones": [
    {
      "id": "clone_1",
      "type": "Type-1",
      "similarity": 1.0,
      "locations": [
        {
          "file": "/path/to/file_a.py",
          "start_line": 10,
          "end_line": 25,
          "snippet_preview": "def process_data(items):\n    result = []\n    for item in items:"
        },
        {
          "file": "/path/to/file_b.py",
          "start_line": 45,
          "end_line": 60,
          "snippet_preview": "def process_data(items):\n    result = []\n    for item in items:"
        }
      ],
      "recommendation": "Exact duplicate found - consider extracting to shared function"
    }
  ]
}
```

### Hotspots
```json
{
  "hotspots": [
    {
      "file": "/path/to/file.py",
      "duplication_score": 0.25,
      "clone_count": 5,
      "duplicated_lines": 50,
      "total_lines": 200
    }
  ]
}
```

### Performance Metrics
```json
{
  "performance": {
    "loc_per_second": 4965.2,
    "tokens_per_second": 12500.0,
    "files_per_second": 67,
    "total_tokens": 13500,
    "thread_count": 4,
    "parallel_enabled": true
  },
  "timing": {
    "tokenize_ms": 450,
    "hash_ms": 200,
    "match_ms": 442,
    "total_ms": 1092
  }
}
```

## Architecture

```
cpp/
├── src/
│   ├── main.cpp                 # CLI entry point
│   ├── core/
│   │   ├── rolling_hash.hpp/cpp # Rabin-Karp implementation
│   │   ├── hash_index.hpp/cpp   # Inverted index for matches
│   │   ├── clone_extender.hpp/cpp # Type-3 detection
│   │   └── similarity_detector.hpp/cpp # Main orchestrator
│   ├── tokenizers/
│   │   ├── token_normalizer.hpp # Base class
│   │   └── python_normalizer.hpp/cpp # Python tokenizer
│   ├── models/
│   │   ├── clone_types.hpp      # Data structures
│   │   └── report.hpp           # JSON-serializable report
│   ├── server/
│   │   ├── json_protocol.hpp    # Request/Response handling
│   │   └── uds_server.hpp/cpp   # Unix socket server
│   └── utils/
│       ├── file_utils.hpp/cpp   # File I/O utilities
│       ├── thread_pool.hpp      # Parallel processing
│       └── lru_cache.hpp        # Token caching
├── tests/
│   ├── test_*.cpp               # Google Test unit tests
│   ├── test_uds_integration.py  # Python integration test
│   └── fixtures/                # Test files
└── build/
```

## Algorithm

1. **Tokenization**: Convert source code to normalized tokens
2. **Rolling Hash**: Compute Rabin-Karp hashes over sliding windows
3. **Index Building**: Store hash → location mappings
4. **Match Finding**: Identify locations with same hash
5. **Clone Extension**: Extend matches and calculate similarity
6. **Classification**: Determine clone type (1/2/3)

### Clone Types

| Type | Description | Detection |
|------|-------------|-----------|
| Type-1 | Exact clones | Identical normalized tokens |
| Type-2 | Renamed clones | Same structure, different identifiers |
| Type-3 | Modified clones | Similar with gaps (≥70% similarity) |

## Integration with AEGIS

The C++ module integrates with the AEGIS Python backend via:

1. **CLI**: Direct JSON output to stdout
2. **UDS Server**: Persistent server for multiple requests
3. **cpp_bridge.py**: Python client for UDS communication

Example Python integration:
```python
import socket
import json

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("/tmp/aegis-cpp.sock")

request = {
    "id": "1",
    "method": "analyze",
    "params": {"root": "./src", "extensions": [".py"]}
}
sock.sendall((json.dumps(request) + "\n").encode())

response = json.loads(sock.recv(65536).decode())
print(f"Found {len(response['result']['clones'])} clones")
```

## Performance

Typical performance on modern hardware:
- **Throughput**: 5,000-15,000 LOC/second
- **Memory**: ~500MB for 100K LOC
- **Parallelization**: Linear speedup up to 4-8 cores

## License

Part of the AEGIS project. See main repository for license details.
