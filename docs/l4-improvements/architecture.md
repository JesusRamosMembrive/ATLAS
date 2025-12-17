# L4 Static Analysis Improvements - Architecture Document

**Author**: @architect
**Date**: 2025-12-16
**Stage**: 3 (Production)
**Status**: PENDING APPROVAL

---

## 1. Context & Requirements

### 1.1 Current State

Level 4 analysis (`code_map/contracts/patterns/static.py`) is basic regex-based:

| What it detects | Pattern | Confidence |
|-----------------|---------|------------|
| Preconditions | `assert()`, `if-throw` | 40% |
| Thread Safety | `std::mutex`, `std::atomic` | 40% |
| Errors | `throw Type`, `raise Type` | 40% |

**Limitations**:
- No AST analysis (only regex)
- No ownership inference
- No lifecycle detection
- No dependency extraction
- Fixed 40% confidence (no gradation)

### 1.2 Goals

Improve L4 to extract more contracts from C++ code **without LLM latency**:

1. **Ownership** from smart pointers (`unique_ptr` = owns, `shared_ptr` = shares)
2. **Dependencies** from constructor parameters and setters
3. **Lifecycle** from method names (`start`, `stop`, `init`, `shutdown`)
4. **Thread Safety** improvements (naming patterns like `Safe*`, `*Queue`)
5. **Sub-level confidence** (L4-High: 40%, L4-Med: 30%, L4-Low: 20%)

### 1.3 Non-Goals (Out of Scope)

- Multi-language support (Python/TypeScript) - future work
- Pattern detection (Factory, Observer) - future work
- Call graph analysis - future work
- State machine detection - Phase 2

### 1.4 Success Criteria

1. FilterModule example extracts: ownership, dependencies, lifecycle, thread_safety
2. All existing tests pass
3. New tests for each analyzer
4. Performance: < 100ms per file (no LLM calls)

---

## 2. Stage Assessment

**Current Stage**: 3 (Production)

**Stage 3 Guidelines Applied**:
- Abstractions justified by real patterns in codebase
- Modular design allows future extension (new analyzers)
- No over-engineering (start with 4 analyzers, not 10)
- Each analyzer is independent and testable

---

## 3. Component Structure

### 3.1 Directory Layout

```
code_map/contracts/patterns/
├── static.py                      # Existing - becomes orchestrator
├── analyzers/
│   ├── __init__.py               # Exports all analyzers
│   ├── base.py                   # BaseAnalyzer protocol
│   ├── ownership.py              # Smart pointer analysis
│   ├── dependency.py             # Constructor/setter deps
│   ├── lifecycle.py              # Method name patterns
│   └── thread_safety.py          # Enhanced thread safety
├── queries/
│   └── cpp.py                    # Tree-sitter query helpers
└── models.py                     # L4Confidence, L4Evidence
```

### 3.2 Class Diagram

```
                    ┌─────────────────┐
                    │  StaticAnalyzer │  (orchestrator)
                    │    (static.py)  │
                    └────────┬────────┘
                             │ uses
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐
│OwnershipAnalyzer│ │DependencyAnalyzer│ │LifecycleAnalyzer│
└───────────────┘  └─────────────────┘  └─────────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │ implements
                             ▼
                    ┌─────────────────┐
                    │  BaseAnalyzer   │  (Protocol)
                    │    (base.py)    │
                    └─────────────────┘
```

### 3.3 Data Flow

```
Source Code (str)
       │
       ▼
┌──────────────────┐
│ tree-sitter parse│ ─────► AST (Node)
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  StaticAnalyzer  │
│  .analyze()      │
└────────┬─────────┘
         │ dispatches to
         ▼
┌────────────────────────────────────────┐
│  Analyzers (parallel or sequential)    │
│  - OwnershipAnalyzer.analyze(ast)      │
│  - DependencyAnalyzer.analyze(ast)     │
│  - LifecycleAnalyzer.analyze(ast)      │
│  - ThreadSafetyAnalyzer.analyze(ast)   │
└────────────────────────────────────────┘
         │ returns List[L4Finding]
         ▼
┌──────────────────┐
│  Merge findings  │
│  → ContractData  │
└──────────────────┘
```

---

## 4. Detailed Design

### 4.1 New Models (`models.py`)

```python
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

class L4Confidence(Enum):
    """Sub-levels within L4 (40% base)."""
    HIGH = 0.40    # Very reliable patterns
    MEDIUM = 0.30  # Reasonable inferences
    LOW = 0.20     # Speculative heuristics

class L4FindingType(Enum):
    """Types of findings from static analysis."""
    OWNERSHIP = "ownership"
    DEPENDENCY = "dependency"
    LIFECYCLE = "lifecycle"
    THREAD_SAFETY = "thread_safety"
    PRECONDITION = "precondition"
    ERROR = "error"

@dataclass
class L4Finding:
    """A single finding from static analysis."""
    type: L4FindingType
    confidence: L4Confidence
    value: str                    # The contract value
    evidence: str                 # Code evidence (e.g., "unique_ptr<T>")
    line: Optional[int] = None   # Source line if available

    @property
    def confidence_score(self) -> float:
        return self.confidence.value
```

### 4.2 Base Analyzer Protocol (`base.py`)

```python
from typing import Protocol, List
from tree_sitter import Node
from .models import L4Finding

class BaseAnalyzer(Protocol):
    """Protocol for L4 analyzers."""

    @property
    def name(self) -> str:
        """Analyzer identifier."""
        ...

    def analyze(self, ast: Node, source: str) -> List[L4Finding]:
        """
        Analyze AST and return findings.

        Args:
            ast: Tree-sitter AST root node
            source: Original source code

        Returns:
            List of findings with confidence levels
        """
        ...
```

### 4.3 Ownership Analyzer (`ownership.py`)

**Purpose**: Detect ownership relations from smart pointers and raw pointers.

**Patterns**:

| Pattern | Ownership | Confidence |
|---------|-----------|------------|
| `std::unique_ptr<T>` | owns (exclusive) | HIGH |
| `std::shared_ptr<T>` | shares | HIGH |
| `std::weak_ptr<T>` | observes | HIGH |
| `T*` member | uses (no ownership) | MEDIUM |
| `T&` member | borrows | MEDIUM |

**Implementation sketch**:

```python
class OwnershipAnalyzer:
    name = "ownership"

    OWNERSHIP_PATTERNS = {
        "unique_ptr": ("owns", L4Confidence.HIGH),
        "shared_ptr": ("shares", L4Confidence.HIGH),
        "weak_ptr": ("observes", L4Confidence.HIGH),
    }

    def analyze(self, ast: Node, source: str) -> List[L4Finding]:
        findings = []

        # Find field declarations with template types
        for field in self._find_field_declarations(ast):
            template_name = self._get_template_name(field)
            if template_name in self.OWNERSHIP_PATTERNS:
                relation, confidence = self.OWNERSHIP_PATTERNS[template_name]
                member_name = self._get_field_name(field)
                inner_type = self._get_template_arg(field)

                findings.append(L4Finding(
                    type=L4FindingType.OWNERSHIP,
                    confidence=confidence,
                    value=f"{member_name}: {relation} {inner_type}",
                    evidence=f"{template_name}<{inner_type}>",
                    line=field.start_point[0] + 1,
                ))

        # Raw pointers = "uses"
        for field in self._find_raw_pointer_fields(ast):
            findings.append(L4Finding(
                type=L4FindingType.OWNERSHIP,
                confidence=L4Confidence.MEDIUM,
                value=f"{field.name}: uses {field.type}",
                evidence=f"{field.type}*",
                line=field.line,
            ))

        return findings
```

### 4.4 Dependency Analyzer (`dependency.py`)

**Purpose**: Extract dependencies from constructor parameters and setter methods.

**Patterns**:

| Pattern | Dependency Type | Confidence |
|---------|-----------------|------------|
| Constructor param `IFoo* foo` | Injected dependency | HIGH |
| Constructor param `const Config& cfg` | Configuration | HIGH |
| Setter `void setFoo(IFoo* foo)` | Optional dependency | MEDIUM |
| Member `IFoo* foo_` initialized from ctor | Required dependency | HIGH |

**Implementation sketch**:

```python
class DependencyAnalyzer:
    name = "dependency"

    def analyze(self, ast: Node, source: str) -> List[L4Finding]:
        findings = []

        # Find constructors
        for ctor in self._find_constructors(ast):
            for param in self._get_parameters(ctor):
                # Interface pointer = injected dependency
                if self._is_interface_pointer(param):
                    findings.append(L4Finding(
                        type=L4FindingType.DEPENDENCY,
                        confidence=L4Confidence.HIGH,
                        value=f"requires {param.type}",
                        evidence=f"constructor({param.type} {param.name})",
                        line=ctor.start_point[0] + 1,
                    ))

        # Find setters (setXxx, setXXX patterns)
        for method in self._find_setter_methods(ast):
            for param in self._get_parameters(method):
                if self._is_interface_pointer(param):
                    findings.append(L4Finding(
                        type=L4FindingType.DEPENDENCY,
                        confidence=L4Confidence.MEDIUM,
                        value=f"optional {param.type}",
                        evidence=f"{method.name}({param.type})",
                        line=method.start_point[0] + 1,
                    ))

        return findings
```

### 4.5 Lifecycle Analyzer (`lifecycle.py`)

**Purpose**: Detect lifecycle phases from method names and state enums.

**Patterns**:

| Pattern | Phase | Confidence |
|---------|-------|------------|
| `start()`, `begin()`, `run()` | Transition to "running" | MEDIUM |
| `stop()`, `shutdown()`, `close()` | Transition to "stopped" | MEDIUM |
| `init()`, `initialize()`, `setup()` | Initialization phase | MEDIUM |
| `destroy()`, `cleanup()`, `dispose()` | Cleanup phase | MEDIUM |
| `pause()`, `suspend()` | Transition to "paused" | MEDIUM |
| `resume()`, `wake()` | Transition from "paused" | MEDIUM |
| `std::atomic<State> state_` | Has state machine | HIGH |

**Implementation sketch**:

```python
class LifecycleAnalyzer:
    name = "lifecycle"

    LIFECYCLE_METHODS = {
        # Start methods
        ("start", "begin", "run", "activate"): ("running", "start"),
        # Stop methods
        ("stop", "shutdown", "close", "terminate", "finish"): ("stopped", "stop"),
        # Init methods
        ("init", "initialize", "setup", "configure"): ("initialized", "init"),
        # Cleanup methods
        ("destroy", "cleanup", "dispose", "release"): ("destroyed", "cleanup"),
        # Pause/resume
        ("pause", "suspend"): ("paused", "pause"),
        ("resume", "wake", "unpause"): ("running", "resume"),
    }

    def analyze(self, ast: Node, source: str) -> List[L4Finding]:
        findings = []
        phases_found = set()
        transitions = []

        # Find lifecycle methods
        for method in self._find_methods(ast):
            method_name = method.name.lower()
            for patterns, (phase, transition) in self.LIFECYCLE_METHODS.items():
                if method_name in patterns or any(method_name.startswith(p) for p in patterns):
                    phases_found.add(phase)
                    transitions.append(transition)
                    break

        # If we found lifecycle methods, create lifecycle finding
        if phases_found:
            findings.append(L4Finding(
                type=L4FindingType.LIFECYCLE,
                confidence=L4Confidence.MEDIUM,
                value=f"phases: {', '.join(sorted(phases_found))}",
                evidence=f"methods: {', '.join(transitions)}",
            ))

        # Check for atomic state member
        for field in self._find_atomic_state_fields(ast):
            findings.append(L4Finding(
                type=L4FindingType.LIFECYCLE,
                confidence=L4Confidence.HIGH,
                value="has state machine",
                evidence=f"atomic<{field.type}> {field.name}",
                line=field.line,
            ))

        return findings
```

### 4.6 Thread Safety Analyzer (`thread_safety.py`)

**Purpose**: Enhanced thread safety detection with naming patterns.

**Patterns**:

| Pattern | Thread Safety | Confidence |
|---------|---------------|------------|
| `std::mutex` member | SAFE | HIGH |
| `std::atomic<T>` member | SAFE | HIGH |
| `std::lock_guard` usage | SAFE | HIGH |
| `Safe*` class name | SAFE | MEDIUM |
| `*Queue`, `*Pool` suffix | SAFE | MEDIUM |
| `ThreadSafe*` prefix | SAFE | MEDIUM |
| `*_mutex` member name | SAFE | HIGH |

**Implementation sketch**:

```python
class ThreadSafetyAnalyzer:
    name = "thread_safety"

    SAFE_TYPES = {
        "mutex", "shared_mutex", "recursive_mutex",
        "atomic", "lock_guard", "unique_lock", "shared_lock",
        "scoped_lock", "condition_variable",
    }

    SAFE_NAME_PATTERNS = [
        (re.compile(r"^Safe\w+"), L4Confidence.MEDIUM),
        (re.compile(r"^ThreadSafe\w+"), L4Confidence.MEDIUM),
        (re.compile(r"\w+Queue$"), L4Confidence.MEDIUM),
        (re.compile(r"\w+Pool$"), L4Confidence.MEDIUM),
        (re.compile(r"\w+Cache$"), L4Confidence.LOW),
    ]

    def analyze(self, ast: Node, source: str) -> List[L4Finding]:
        findings = []
        mechanisms = []

        # Check field types
        for field in self._find_fields(ast):
            type_name = self._get_base_type(field)
            if type_name in self.SAFE_TYPES:
                mechanisms.append(f"std::{type_name}")
                findings.append(L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=L4Confidence.HIGH,
                    value="safe",
                    evidence=f"std::{type_name} {field.name}",
                    line=field.line,
                ))

        # Check field type names (SafeQueue, ThreadSafeMap, etc.)
        for field in self._find_fields(ast):
            type_name = self._get_type_name(field)
            for pattern, confidence in self.SAFE_NAME_PATTERNS:
                if pattern.match(type_name):
                    mechanisms.append(type_name)
                    findings.append(L4Finding(
                        type=L4FindingType.THREAD_SAFETY,
                        confidence=confidence,
                        value="safe",
                        evidence=f"{type_name} {field.name}",
                        line=field.line,
                    ))
                    break

        return findings
```

### 4.7 Updated StaticAnalyzer (`static.py`)

**Changes**:
1. Import and use new analyzers
2. Merge findings into ContractData
3. Keep backward compatibility with existing regex patterns

```python
class StaticAnalyzer:
    """Orchestrator for L4 static analysis."""

    def __init__(self):
        self.analyzers = [
            OwnershipAnalyzer(),
            DependencyAnalyzer(),
            LifecycleAnalyzer(),
            ThreadSafetyAnalyzer(),
        ]
        # Keep legacy regex patterns for backward compat
        self._legacy_patterns = LegacyPatterns()

    def analyze(self, source: str, file_path: Path) -> ContractData:
        """Analyze source code for implied contracts."""
        contract = ContractData(
            confidence=0.0,  # Will be set based on findings
            source_level=4,
            inferred=True,
            file_path=file_path,
        )

        # Determine language
        ext = file_path.suffix.lower()
        if ext not in (".cpp", ".hpp", ".h", ".cc", ".c", ".cxx", ".hxx"):
            # Fall back to legacy for non-C++
            return self._legacy_analyze(source, file_path)

        # Parse with tree-sitter
        ast = self._parse(source, "cpp")
        if ast is None:
            return self._legacy_analyze(source, file_path)

        # Run all analyzers
        all_findings: List[L4Finding] = []
        for analyzer in self.analyzers:
            try:
                findings = analyzer.analyze(ast, source)
                all_findings.extend(findings)
            except Exception:
                pass  # Individual analyzer failure shouldn't stop others

        # Also run legacy patterns (preconditions, errors)
        legacy_contract = self._legacy_analyze(source, file_path)

        # Merge findings into contract
        contract = self._merge_findings(all_findings, legacy_contract)

        return contract

    def _merge_findings(
        self,
        findings: List[L4Finding],
        legacy: ContractData
    ) -> ContractData:
        """Merge findings into ContractData."""
        contract = ContractData(
            source_level=4,
            inferred=True,
            file_path=legacy.file_path,
        )

        # Start with legacy data
        contract.preconditions = legacy.preconditions
        contract.errors = legacy.errors

        # Process findings by type
        ownership_items = []
        dependency_items = []
        lifecycle_phases = []
        thread_safety_evidence = []
        max_confidence = 0.0

        for finding in findings:
            max_confidence = max(max_confidence, finding.confidence_score)

            if finding.type == L4FindingType.OWNERSHIP:
                ownership_items.append(finding.value)
            elif finding.type == L4FindingType.DEPENDENCY:
                dependency_items.append(finding.value)
            elif finding.type == L4FindingType.LIFECYCLE:
                lifecycle_phases.append(finding.value)
            elif finding.type == L4FindingType.THREAD_SAFETY:
                if finding.value == "safe":
                    contract.thread_safety = ThreadSafety.SAFE
                thread_safety_evidence.append(finding.evidence)

        # Populate contract
        if dependency_items:
            contract.dependencies = dependency_items
        if lifecycle_phases:
            contract.lifecycle = "; ".join(lifecycle_phases)

        # Set confidence (max of all findings, or legacy)
        contract.confidence = max(max_confidence, legacy.confidence)

        # Add notes about what was found
        sources = []
        if ownership_items:
            sources.append(f"ownership({len(ownership_items)})")
        if dependency_items:
            sources.append(f"dependencies({len(dependency_items)})")
        if lifecycle_phases:
            sources.append(f"lifecycle")
        if thread_safety_evidence:
            sources.append(f"thread_safety({len(thread_safety_evidence)})")

        if sources:
            contract.confidence_notes = f"L4 findings: {', '.join(sources)}"

        return contract
```

---

## 5. Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| AST Parsing | tree-sitter + tree-sitter-cpp | Already used in project, fast, accurate |
| Language | Python 3.10+ | Match existing codebase |
| Testing | pytest | Match existing tests |
| Types | dataclasses, Enum, Protocol | Simple, stdlib |

**Dependencies** (already in project):
- `tree_sitter`
- `tree_sitter_languages` (includes cpp grammar)

---

## 6. Build Order

### Phase 1: Foundation (Day 1)

1. **Create `models.py`**
   - L4Confidence enum
   - L4FindingType enum
   - L4Finding dataclass
   - Tests: test_l4_models.py

2. **Create `base.py`**
   - BaseAnalyzer Protocol
   - No tests needed (Protocol)

### Phase 2: Analyzers (Days 2-4)

3. **Create `ownership.py`** (Day 2)
   - OwnershipAnalyzer class
   - Tree-sitter queries for smart pointers
   - Tests: test_ownership_analyzer.py

4. **Create `dependency.py`** (Day 2)
   - DependencyAnalyzer class
   - Tree-sitter queries for constructors/setters
   - Tests: test_dependency_analyzer.py

5. **Create `lifecycle.py`** (Day 3)
   - LifecycleAnalyzer class
   - Method name pattern matching
   - Tests: test_lifecycle_analyzer.py

6. **Create `thread_safety.py`** (Day 3)
   - ThreadSafetyAnalyzer class
   - Enhanced patterns
   - Tests: test_thread_safety_analyzer.py

### Phase 3: Integration (Day 4)

7. **Update `static.py`**
   - Integrate new analyzers
   - Keep legacy patterns
   - Merge findings logic
   - Tests: update existing tests

8. **Create `queries/cpp.py`**
   - Tree-sitter query helpers
   - Shared between analyzers

### Phase 4: Validation (Day 5)

9. **Integration testing**
   - FilterModule example
   - Real C++ files from test projects
   - Performance benchmarks

---

## 7. Testing Strategy

### 7.1 Unit Tests (per analyzer)

```python
# tests/test_l4_analyzers/test_ownership.py
class TestOwnershipAnalyzer:
    def test_unique_ptr_ownership(self):
        source = """
        class Foo {
            std::unique_ptr<ILogger> logger_;
        };
        """
        analyzer = OwnershipAnalyzer()
        findings = analyzer.analyze(parse(source), source)

        assert len(findings) == 1
        assert findings[0].type == L4FindingType.OWNERSHIP
        assert findings[0].confidence == L4Confidence.HIGH
        assert "owns" in findings[0].value

    def test_raw_pointer_uses(self):
        source = """
        class Foo {
            IModule* next_;
        };
        """
        # ...
```

### 7.2 Integration Tests

```python
# tests/test_l4_analyzers/test_integration.py
class TestL4Integration:
    def test_filter_module_example(self):
        """Test the FilterModule example from brainstorming."""
        source = FILTER_MODULE_SOURCE

        analyzer = StaticAnalyzer()
        contract = analyzer.analyze(source, Path("filter.hpp"))

        # Should find lifecycle
        assert contract.lifecycle is not None
        assert "running" in contract.lifecycle or "stopped" in contract.lifecycle

        # Should find thread safety
        assert contract.thread_safety == ThreadSafety.SAFE

        # Should find dependencies
        assert len(contract.dependencies) >= 1

        # Confidence should be reasonable
        assert contract.confidence >= 0.30
```

### 7.3 Performance Tests

```python
def test_performance_under_100ms():
    """L4 analysis should complete in < 100ms per file."""
    large_source = load_test_file("large_cpp_file.cpp")  # ~1000 lines

    start = time.perf_counter()
    analyzer = StaticAnalyzer()
    contract = analyzer.analyze(large_source, Path("large.cpp"))
    elapsed = time.perf_counter() - start

    assert elapsed < 0.1  # 100ms
```

---

## 8. Evolution Triggers

When to evolve this design:

| Trigger | Action |
|---------|--------|
| Need Python/TypeScript support | Add language-specific analyzers |
| Need state machine detection | Add StateMachineAnalyzer |
| Need pattern detection (Factory) | Add PatternAnalyzer |
| Performance issues with tree-sitter | Consider caching parsed ASTs |
| False positive rate > 30% | Tune confidence levels |

---

## 9. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Tree-sitter parsing errors | Low | Medium | Fallback to legacy regex |
| False positives from naming heuristics | Medium | Low | Conservative confidence (MEDIUM/LOW) |
| Performance regression | Low | Medium | Benchmark before/after |
| Breaking existing tests | Medium | High | Run full test suite |

---

## 10. Appendix: FilterModule Expected Output

Input:
```cpp
class FilterModule final : public IModule {
private:
    IModule *next_ = nullptr;
    std::thread workerThread_;
    SafeQueue inputQueue_{100};
    ByteArray targetSequence_;
    std::atomic<ModuleState> state_{ModuleState::Stopped};

public:
    explicit FilterModule(ByteArray targetSequence);
    void setNext(IModule *next) override;
    void receive(const ByteArray &data) override;
    void start() override;
    void stop() override;
};
```

Expected L4 Output:
```yaml
thread_safety: safe
lifecycle: "phases: running, stopped; has state machine"
dependencies:
  - "requires ByteArray (constructor)"
  - "optional IModule* (setNext)"
# ownership (in confidence_notes):
#   - next_: uses IModule
#   - workerThread_: owns std::thread
#   - inputQueue_: owns SafeQueue
#   - targetSequence_: owns ByteArray
#   - state_: owns atomic<ModuleState>
confidence: 0.40
confidence_notes: "L4 findings: ownership(5), dependencies(2), lifecycle, thread_safety(2)"
```

---

## Approval Checklist

- [ ] Architecture is stage-appropriate (Stage 3)
- [ ] Build order is clear and dependency-aware
- [ ] Testing strategy covers unit, integration, and performance
- [ ] Risks are identified and mitigated
- [ ] Evolution triggers are defined

**Ready for implementation upon approval.**
