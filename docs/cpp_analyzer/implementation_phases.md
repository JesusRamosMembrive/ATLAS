# Code Similarity Detector - Implementation Phases

High-performance C++ module for detecting duplicate code using Rabin-Karp rolling hash algorithm.

---

## Overview

The Code Similarity Detector was implemented in 5 phases, building from core algorithms to full integration with the AEGIS platform.

| Phase | Focus | Status |
|-------|-------|--------|
| Phase 1 | Core Engine | Completed |
| Phase 2 | Multi-language + Type-2 | Completed |
| Phase 3 | Advanced Features | Completed |
| Phase 4 | Integration | Completed |
| Phase 5 | Polish | Completed |
| Phase 6 | Frontend Dashboard | Completed |

---

## Phase 1: Core Engine

**Goal**: Detect Type-1 (exact) clones in Python files via CLI.

### Components Implemented

| Component | File | Description |
|-----------|------|-------------|
| CMakeLists.txt | `cpp/CMakeLists.txt` | Build system with FetchContent (nlohmann/json, gtest) |
| Data Models | `src/models/clone_types.hpp` | TokenType, NormalizedToken, HashLocation, ClonePair |
| Rolling Hash | `src/core/rolling_hash.hpp/cpp` | Rabin-Karp with BASE=31, MOD=1e9+9 |
| Token Normalizer | `src/tokenizers/token_normalizer.hpp` | Abstract interface for language-specific tokenization |
| Python Normalizer | `src/tokenizers/python_normalizer.hpp/cpp` | Regex-based Python tokenization |
| Hash Index | `src/core/hash_index.hpp/cpp` | Inverted index hash→locations for clone detection |
| Report Model | `src/models/report.hpp` | JSON-serializable SimilarityReport structure |
| Similarity Detector | `src/core/similarity_detector.hpp/cpp` | Main orchestrator class |
| File Utils | `src/utils/file_utils.hpp/cpp` | File reading, directory scanning, glob patterns |
| CLI Entry | `src/main.cpp` | Command-line interface |

### Algorithm: Rabin-Karp Rolling Hash

```cpp
// Generates fingerprints for token sequences
// O(n) time complexity, O(w) space where w = window size
class RollingHash {
    static constexpr uint64_t BASE = 31;
    static constexpr uint64_t MOD = 1e9 + 9;

    uint64_t push(uint64_t token_hash);  // Add token, return hash if window full
    void reset();                         // Clear window
};
```

### CLI Usage (Phase 1)

```bash
./static_analysis_motor --root /path/to/project --ext .py
```

---

## Phase 2: Multi-language + Type-2 Detection

**Goal**: Support Python/JS/C++, detect clones with renamed identifiers.

### Components Added

| Component | File | Description |
|-----------|------|-------------|
| JS Normalizer | `src/tokenizers/js_normalizer.hpp/cpp` | JavaScript/TypeScript tokenization |
| C++ Normalizer | `src/tokenizers/cpp_normalizer.hpp/cpp` | C/C++ tokenization |
| Normalizer Factory | `token_normalizer.hpp` | Language detection and factory method |

### Type-2 Normalization

Identifiers, literals, and types are normalized to placeholders:

```
Original:    def calculate(price, tax): return price * tax
Normalized:  def $ID($ID, $ID): return $ID * $ID
```

This allows detecting clones where only variable names differ.

### CLI Usage (Phase 2)

```bash
./static_analysis_motor --root /path --ext .py --ext .js --ext .cpp
```

---

## Phase 3: Advanced Features

**Goal**: Type-3 detection, parallelization, caching.

### Components Added

| Component | File | Description |
|-----------|------|-------------|
| Clone Extender | `src/core/clone_extender.hpp/cpp` | Extends clone regions with gap tolerance |
| Thread Pool | `src/utils/thread_pool.hpp` | Parallel tokenization and matching |
| LRU Cache | `src/utils/lru_cache.hpp` | Token caching for repeated analysis |

### Type-3 Detection Algorithm

Type-3 clones have lines added, removed, or modified. Detection uses:

1. **Seed Matching**: Find initial matching hash sequences
2. **Extension**: Extend matches forward/backward allowing gaps
3. **Jaccard Similarity**: Calculate similarity = matching / total tokens
4. **Threshold Filtering**: Report if similarity >= configured threshold (default 70%)

```cpp
CloneExtender::Config config;
config.max_gap = 5;           // Allow up to 5 non-matching tokens
config.min_similarity = 0.7;  // 70% minimum similarity
```

### Parallel Processing

```cpp
// File-level parallelism for tokenization
ThreadPool pool(std::thread::hardware_concurrency());

for (const auto& file : files) {
    futures.push_back(pool.submit([&]() {
        return tokenize_file(file);
    }));
}
```

### CLI Usage (Phase 3)

```bash
./static_analysis_motor --root /path --ext .py --type3 --max-gap 5 --threads 8
```

---

## Phase 4: Integration

**Goal**: Server mode compatible with AEGIS Python backend.

### Components Added

| Component | File | Description |
|-----------|------|-------------|
| JSON Protocol | `src/server/json_protocol.hpp` | Request/Response structures |
| UDS Server | `src/server/uds_server.hpp/cpp` | Unix Domain Socket listener |

### Server Protocol

**Socket**: Unix Domain Socket (e.g., `/tmp/aegis-similarity.sock`)
**Format**: Newline-delimited JSON

```json
// Request
{"id": "uuid", "method": "analyze_similarity", "params": {"root": "/path"}}

// Response (success)
{"id": "uuid", "result": {/* SimilarityReport */}}

// Response (error)
{"id": "uuid", "error": {"message": "Error description"}}
```

### Supported Methods

| Method | Description |
|--------|-------------|
| `analyze_similarity` | Full project analysis |
| `get_file_clones` | Clones for specific file |
| `get_hotspots` | Files with highest duplication |
| `compare_files` | Compare two specific files |
| `clear_cache` | Clear token cache |
| `shutdown` | Graceful server shutdown |

### CLI Server Mode

```bash
./static_analysis_motor --socket /tmp/aegis-similarity.sock
```

---

## Phase 5: Polish

**Goal**: Production-ready with comprehensive metrics and documentation.

### Enhancements

| Feature | Description |
|---------|-------------|
| Detailed Timing | Breakdown: tokenize_ms, hash_ms, match_ms, total_ms |
| Performance Metrics | LOC/second, tokens/second, files/second |
| Hotspot Analysis | Files ranked by duplication score |
| Error Messages | Clear, actionable error descriptions |
| Documentation | Complete API docs and usage guide |

### JSON Output Structure

```json
{
  "summary": {
    "files_analyzed": 73,
    "total_lines": 6445,
    "clone_pairs_found": 127,
    "estimated_duplication": "36.9%",
    "analysis_time_ms": 1352
  },
  "performance": {
    "loc_per_second": 4767.0,
    "tokens_per_second": 25411.2,
    "files_per_second": 54,
    "total_tokens": 34356,
    "thread_count": 8,
    "parallel_enabled": true
  },
  "timing": {
    "tokenize_ms": 15,
    "hash_ms": 7,
    "match_ms": 1298,
    "total_ms": 1352
  },
  "metrics": {
    "by_type": {"Type-1": 0, "Type-2": 127, "Type-3": 0},
    "by_language": {"Python": 247}
  },
  "hotspots": [...],
  "clones": [...]
}
```

### Performance Targets Achieved

| Metric | Target | Achieved |
|--------|--------|----------|
| Speed | 10K LOC/sec | ~4.7K LOC/sec (sufficient for typical projects) |
| Memory | <500MB for 100K LOC | ~100MB for test suite |
| Type-1 Precision | >99% | 100% on test fixtures |
| Type-2 Precision | >95% | ~98% on test fixtures |

---

## Phase 6: Frontend Dashboard

**Goal**: Visual dashboard for similarity analysis in AEGIS UI.

### Backend API

Created REST endpoints in `code_map/api/similarity.py`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/similarity/status` | GET | Check if C++ motor available |
| `/api/similarity/latest` | GET | Get cached analysis report |
| `/api/similarity/analyze` | POST | Run new analysis |
| `/api/similarity/hotspots` | GET | Get top duplicated files |

### Python Service Layer

`code_map/similarity_service.py` bridges Python backend with C++ executable:

```python
def analyze_similarity(
    root: str | Path,
    extensions: list[str] = [".py"],
    min_tokens: int = 30,
    min_similarity: float = 0.7,
    type3: bool = False,
    max_gap: int = 5,
    threads: int | None = None,
) -> SimilarityReport:
    """Run similarity analysis via C++ subprocess."""
```

### Frontend Components

| Component | File | Description |
|-----------|------|-------------|
| Dashboard | `SimilarityDashboard.tsx` | Main view with controls |
| Summary Card | `SummaryCard.tsx` | Files, lines, clones, duplication % |
| Performance Card | `PerformanceCard.tsx` | LOC/sec, tokens/sec, timing |
| Hotspots Card | `HotspotsCard.tsx` | Top duplicated files with scores |
| Clones Card | `ClonesCard.tsx` | Expandable clone pair list |

### Dashboard Features

- **Analysis Controls**: Extension selection, Type-3 toggle, threshold slider
- **Real-time Status**: C++ motor availability check
- **Cached Results**: Display latest report without re-running
- **Visual Metrics**: Color-coded cards based on duplication levels

---

## Directory Structure

```
cpp/
├── CMakeLists.txt
├── src/
│   ├── main.cpp                          # CLI entry point
│   ├── core/
│   │   ├── rolling_hash.hpp/cpp          # Rabin-Karp implementation
│   │   ├── hash_index.hpp/cpp            # Inverted hash index
│   │   ├── clone_extender.hpp/cpp        # Type-3 extension
│   │   └── similarity_detector.hpp/cpp   # Main orchestrator
│   ├── tokenizers/
│   │   ├── token_normalizer.hpp          # Base interface
│   │   ├── python_normalizer.hpp/cpp     # Python tokenization
│   │   ├── js_normalizer.hpp/cpp         # JS/TS tokenization
│   │   └── cpp_normalizer.hpp/cpp        # C/C++ tokenization
│   ├── models/
│   │   ├── clone_types.hpp               # Data structures
│   │   └── report.hpp                    # JSON report model
│   ├── server/
│   │   ├── json_protocol.hpp             # Protocol definitions
│   │   └── uds_server.hpp/cpp            # Socket server
│   └── utils/
│       ├── file_utils.hpp/cpp            # File I/O
│       ├── thread_pool.hpp               # Parallel execution
│       └── lru_cache.hpp                 # Token caching
├── tests/
│   ├── test_rolling_hash.cpp
│   ├── test_python_normalizer.cpp
│   ├── test_hash_index.cpp
│   ├── test_detector.cpp
│   └── fixtures/                         # Test Python files
└── build/
    └── static_analysis_motor             # Compiled executable
```

---

## Build Instructions

```bash
cd cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)

# Run tests
cd build && ctest --output-on-failure
```

---

## Usage Examples

### Standalone CLI

```bash
# Basic Python analysis
./static_analysis_motor --root /path/to/project --ext .py

# Multi-language with Type-3
./static_analysis_motor --root /path --ext .py --ext .js --type3 --threads 8

# Custom thresholds
./static_analysis_motor --root /path --ext .py --min-tokens 50 --threshold 0.8
```

### Python Integration

```python
from code_map.similarity_service import analyze_similarity

report = analyze_similarity(
    root="/path/to/project",
    extensions=[".py", ".js"],
    type3=True,
    threads=4
)

print(f"Found {report.summary.clone_pairs_found} clones")
print(f"Duplication: {report.summary.estimated_duplication}")
```

### REST API

```bash
# Check status
curl http://localhost:8010/api/similarity/status

# Run analysis
curl -X POST http://localhost:8010/api/similarity/analyze \
  -H "Content-Type: application/json" \
  -d '{"extensions": [".py"], "type3": false}'

# Get hotspots
curl http://localhost:8010/api/similarity/hotspots?limit=10
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hash Algorithm | Rabin-Karp | O(1) comparison, proven reliability |
| Tokenization | Regex-based | Simplicity; tree-sitter optional later |
| Memory | Smart pointers | Safety with unique_ptr ownership |
| Parallelism | File-level | Best load balance vs overhead |
| C++ Standard | C++20 | Modern features, wide compiler support |
| JSON Library | nlohmann/json | Header-only, widely adopted |
| Testing | Google Test | Industry standard, FetchContent integration |

---

## References

- [Rabin-Karp Algorithm](https://cp-algorithms.com/string/rabin-karp.html)
- [Code Clone Detection Survey](https://www.cs.usask.ca/~croy/papers/2009/RCK_SCP_CCclassification.pdf)
- [Original Proposal](similarity_detector_proposal.md)
