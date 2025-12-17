# SPDX-License-Identifier: MIT
"""
Tests for L4 Python Static Analysis.

Tests the Python analyzer architecture including:
- PythonQueryHelper
- PythonOwnershipAnalyzer
- PythonDependencyAnalyzer
- PythonLifecycleAnalyzer
- PythonThreadSafetyAnalyzer
- StaticAnalyzer integration for Python
"""

from pathlib import Path
from textwrap import dedent

import pytest

from code_map.contracts.patterns import (
    L4Confidence,
    L4Finding,
    L4FindingType,
    StaticAnalyzer,
)
from code_map.contracts.patterns.analyzers import (
    PythonDependencyAnalyzer,
    PythonLifecycleAnalyzer,
    PythonOwnershipAnalyzer,
    PythonThreadSafetyAnalyzer,
)
from code_map.contracts.patterns.queries.python import PythonQueryHelper

# Try to import tree-sitter
try:
    import tree_sitter_languages

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


def parse_python(source: str):
    """Parse Python source code and return AST root."""
    parser = tree_sitter_languages.get_parser("python")
    tree = parser.parse(source.encode("utf-8"))
    return tree.root_node


# =============================================================================
# PythonQueryHelper Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestPythonQueryHelper:
    """Test Python tree-sitter query helpers."""

    def test_find_class_definitions(self):
        """Test finding class definitions."""
        source = dedent("""
            class Foo:
                pass

            class Bar:
                pass
        """).strip()

        ast = parse_python(source)
        helper = PythonQueryHelper(source)

        classes = list(helper.find_class_definitions(ast))
        assert len(classes) == 2

    def test_find_methods(self):
        """Test finding method definitions in a class."""
        source = dedent("""
            class Service:
                def __init__(self):
                    pass

                def start(self):
                    pass

                def stop(self):
                    pass
        """).strip()

        ast = parse_python(source)
        helper = PythonQueryHelper(source)

        for class_node in helper.find_class_definitions(ast):
            methods = list(helper.find_methods(class_node))
            assert len(methods) == 3
            names = [m.name for m in methods]
            assert "__init__" in names
            assert "start" in names
            assert "stop" in names

    def test_find_constructor_params(self):
        """Test finding constructor parameters with type annotations."""
        source = dedent("""
            class Service:
                def __init__(self, logger: ILogger, config: Config):
                    self._logger = logger
                    self._config = config
        """).strip()

        ast = parse_python(source)
        helper = PythonQueryHelper(source)

        for class_node in helper.find_class_definitions(ast):
            for constructor in helper.find_constructors(class_node):
                params = [p for p in constructor.parameters if not p.is_self]
                assert len(params) == 2

                logger_param = next(p for p in params if p.name == "logger")
                assert logger_param.type_name == "ILogger"

                config_param = next(p for p in params if p.name == "config")
                assert config_param.type_name == "Config"

    def test_find_field_assignments(self):
        """Test finding field assignments in __init__."""
        source = dedent("""
            class Service:
                def __init__(self, logger: ILogger):
                    self._logger = logger
                    self._lock = threading.Lock()
        """).strip()

        ast = parse_python(source)
        helper = PythonQueryHelper(source)

        for class_node in helper.find_class_definitions(ast):
            fields = list(helper.find_field_assignments(class_node))
            assert len(fields) == 2

            names = [f.name for f in fields]
            assert "_logger" in names
            assert "_lock" in names


# =============================================================================
# PythonOwnershipAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestPythonOwnershipAnalyzer:
    """Test Python ownership analysis."""

    def test_threading_lock_ownership(self):
        """threading.Lock() should be detected as 'owns' with HIGH confidence."""
        source = dedent("""
            class Service:
                def __init__(self):
                    self._lock = threading.Lock()
        """).strip()

        ast = parse_python(source)
        analyzer = PythonOwnershipAnalyzer()
        findings = analyzer.analyze(ast, source)

        lock_finding = next(
            (f for f in findings if "Lock" in f.evidence),
            None,
        )
        assert lock_finding is not None
        assert lock_finding.confidence == L4Confidence.HIGH
        assert "owns" in lock_finding.value.lower()

    def test_parameter_storage(self):
        """Storing a typed parameter should be detected as 'stores'."""
        source = dedent("""
            class Service:
                def __init__(self, logger: ILogger):
                    self._logger = logger
        """).strip()

        ast = parse_python(source)
        analyzer = PythonOwnershipAnalyzer()
        findings = analyzer.analyze(ast, source)

        logger_finding = next(
            (f for f in findings if "_logger" in f.member),
            None,
        )
        assert logger_finding is not None
        assert "stores" in logger_finding.value.lower() or "ILogger" in logger_finding.value


# =============================================================================
# PythonDependencyAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestPythonDependencyAnalyzer:
    """Test Python dependency analysis."""

    def test_constructor_typed_dependency(self):
        """Constructor parameter with type annotation = dependency."""
        source = dedent("""
            class Service:
                def __init__(self, logger: ILogger, store: IStore):
                    self._logger = logger
                    self._store = store
        """).strip()

        ast = parse_python(source)
        analyzer = PythonDependencyAnalyzer()
        findings = analyzer.analyze(ast, source)

        dep_findings = [f for f in findings if f.type == L4FindingType.DEPENDENCY]
        assert len(dep_findings) >= 2

        # Check for ILogger dependency
        logger_dep = next(
            (f for f in dep_findings if "ILogger" in f.value),
            None,
        )
        assert logger_dep is not None
        # ILogger is an interface (starts with I)
        assert logger_dep.confidence == L4Confidence.HIGH

    def test_setter_optional_dependency(self):
        """Setter method = optional dependency."""
        source = dedent("""
            class Module:
                def set_next(self, next: IModule):
                    self._next = next
        """).strip()

        ast = parse_python(source)
        analyzer = PythonDependencyAnalyzer()
        findings = analyzer.analyze(ast, source)

        setter_dep = next(
            (f for f in findings if "optional" in f.value.lower()),
            None,
        )
        assert setter_dep is not None
        assert "IModule" in setter_dep.value


# =============================================================================
# PythonLifecycleAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestPythonLifecycleAnalyzer:
    """Test Python lifecycle analysis."""

    def test_start_stop_lifecycle(self):
        """start/stop methods should detect running/stopped phases."""
        source = dedent("""
            class Worker:
                def start(self):
                    pass

                def stop(self):
                    pass
        """).strip()

        ast = parse_python(source)
        analyzer = PythonLifecycleAnalyzer()
        findings = analyzer.analyze(ast, source)

        lifecycle_findings = [f for f in findings if f.type == L4FindingType.LIFECYCLE]
        assert len(lifecycle_findings) >= 1

        phases_finding = next(
            (f for f in lifecycle_findings if "phases" in f.value.lower()),
            None,
        )
        assert phases_finding is not None
        assert "running" in phases_finding.value.lower() or "stopped" in phases_finding.value.lower()

    def test_context_manager(self):
        """__enter__/__exit__ should detect context manager pattern."""
        source = dedent("""
            class Resource:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
        """).strip()

        ast = parse_python(source)
        analyzer = PythonLifecycleAnalyzer()
        findings = analyzer.analyze(ast, source)

        cm_finding = next(
            (f for f in findings if "context manager" in f.value.lower()),
            None,
        )
        assert cm_finding is not None
        assert cm_finding.confidence == L4Confidence.HIGH

    def test_async_context_manager(self):
        """__aenter__/__aexit__ should detect async context manager."""
        source = dedent("""
            class AsyncResource:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
        """).strip()

        ast = parse_python(source)
        analyzer = PythonLifecycleAnalyzer()
        findings = analyzer.analyze(ast, source)

        cm_finding = next(
            (f for f in findings if "async context manager" in f.value.lower()),
            None,
        )
        assert cm_finding is not None


# =============================================================================
# PythonThreadSafetyAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestPythonThreadSafetyAnalyzer:
    """Test Python thread safety analysis."""

    def test_threading_lock_detection(self):
        """threading.Lock should detect thread safety."""
        source = dedent("""
            class SharedData:
                def __init__(self):
                    self._lock = threading.Lock()
        """).strip()

        ast = parse_python(source)
        analyzer = PythonThreadSafetyAnalyzer()
        findings = analyzer.analyze(ast, source)

        safety_findings = [f for f in findings if f.type == L4FindingType.THREAD_SAFETY]
        assert len(safety_findings) >= 1

        safe_finding = next(
            (f for f in safety_findings if f.value == "safe"),
            None,
        )
        assert safe_finding is not None
        assert safe_finding.confidence == L4Confidence.HIGH

    def test_queue_detection(self):
        """queue.Queue should detect thread-safe queue."""
        source = dedent("""
            class Producer:
                def __init__(self):
                    self._queue = queue.Queue()
        """).strip()

        ast = parse_python(source)
        analyzer = PythonThreadSafetyAnalyzer()
        findings = analyzer.analyze(ast, source)

        queue_finding = next(
            (f for f in findings if "Queue" in f.value),
            None,
        )
        assert queue_finding is not None

    def test_lock_name_pattern(self):
        """Field named *_lock should suggest synchronization."""
        source = dedent("""
            class Cache:
                def __init__(self):
                    self.data_lock = SomeLock()
        """).strip()

        ast = parse_python(source)
        analyzer = PythonThreadSafetyAnalyzer()
        findings = analyzer.analyze(ast, source)

        safety_findings = [f for f in findings if f.type == L4FindingType.THREAD_SAFETY]
        assert len(safety_findings) >= 1


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestPythonStaticAnalyzerIntegration:
    """Test full StaticAnalyzer integration for Python."""

    PYTHON_SERVICE_SOURCE = dedent("""
        import threading
        from typing import Protocol

        class ILogger(Protocol):
            def log(self, msg: str) -> None: ...

        class Service:
            def __init__(self, logger: ILogger, config: Config):
                self._logger = logger
                self._config = config
                self._lock = threading.Lock()
                self._running = False

            def start(self):
                with self._lock:
                    self._running = True

            def stop(self):
                with self._lock:
                    self._running = False

            def set_callback(self, callback: ICallback):
                self._callback = callback
    """).strip()

    def test_python_service_analysis(self):
        """Test Python service analysis."""
        analyzer = StaticAnalyzer()
        contract = analyzer.analyze(
            self.PYTHON_SERVICE_SOURCE,
            Path("service.py"),
        )

        # Should have confidence
        assert contract.confidence > 0

        # Should detect lifecycle
        assert contract.lifecycle is not None

        # Should detect thread safety
        assert contract.thread_safety is not None

    def test_python_service_dependencies(self):
        """Python service should have detected dependencies."""
        analyzer = StaticAnalyzer()
        contract = analyzer.analyze(
            self.PYTHON_SERVICE_SOURCE,
            Path("service.py"),
        )

        # Should detect dependencies from constructor
        assert len(contract.dependencies) >= 1

    def test_python_raw_findings(self):
        """Test get_findings() for Python."""
        analyzer = StaticAnalyzer()
        findings = analyzer.get_findings(
            self.PYTHON_SERVICE_SOURCE,
            Path("service.py"),
        )

        assert len(findings) > 0

        # Check we have different types
        types_found = set(f.type for f in findings)
        assert L4FindingType.OWNERSHIP in types_found
        assert L4FindingType.LIFECYCLE in types_found
        assert L4FindingType.THREAD_SAFETY in types_found


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
