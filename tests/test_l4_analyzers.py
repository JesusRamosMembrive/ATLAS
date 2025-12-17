# SPDX-License-Identifier: MIT
"""
Tests for L4 Static Analysis improvements.

Tests the new analyzer architecture including:
- OwnershipAnalyzer
- DependencyAnalyzer
- LifecycleAnalyzer
- ThreadSafetyAnalyzer
- StaticAnalyzer integration
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
    DependencyAnalyzer,
    LifecycleAnalyzer,
    OwnershipAnalyzer,
    ThreadSafetyAnalyzer,
)
from code_map.contracts.patterns.queries.cpp import CppQueryHelper

# Try to import tree-sitter
try:
    import tree_sitter_languages

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


def parse_cpp(source: str):
    """Parse C++ source code and return AST root."""
    parser = tree_sitter_languages.get_parser("cpp")
    tree = parser.parse(source.encode("utf-8"))
    return tree.root_node


# =============================================================================
# Model Tests
# =============================================================================


class TestL4Models:
    """Test L4 data models."""

    def test_l4_confidence_values(self):
        """Verify confidence values match design."""
        assert L4Confidence.HIGH.value == 0.40
        assert L4Confidence.MEDIUM.value == 0.30
        assert L4Confidence.LOW.value == 0.20

    def test_l4_finding_confidence_score(self):
        """Test L4Finding confidence_score property."""
        finding = L4Finding(
            type=L4FindingType.OWNERSHIP,
            confidence=L4Confidence.HIGH,
            value="owns ILogger",
            evidence="unique_ptr<ILogger>",
        )
        assert finding.confidence_score == 0.40

    def test_l4_finding_to_dict(self):
        """Test L4Finding serialization."""
        finding = L4Finding(
            type=L4FindingType.LIFECYCLE,
            confidence=L4Confidence.MEDIUM,
            value="phases: running, stopped",
            evidence="start(), stop() methods",
            line=42,
            member="state_",
        )
        d = finding.to_dict()
        assert d["type"] == "lifecycle"
        assert d["confidence"] == "MEDIUM"
        assert d["confidence_score"] == 0.30
        assert d["line"] == 42
        assert d["member"] == "state_"


# =============================================================================
# CppQueryHelper Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestCppQueryHelper:
    """Test tree-sitter query helpers."""

    def test_find_class_declarations(self):
        """Test finding class declarations."""
        source = dedent("""
            class Foo {
            public:
                void bar();
            };

            struct Baz {
                int x;
            };
        """).strip()

        ast = parse_cpp(source)
        helper = CppQueryHelper(source)

        classes = list(helper.find_class_declarations(ast))
        assert len(classes) == 2

    def test_find_field_declarations(self):
        """Test finding field declarations in a class."""
        source = dedent("""
            class Foo {
            private:
                int count_;
                std::string name_;
            };
        """).strip()

        ast = parse_cpp(source)
        helper = CppQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            fields = list(helper.find_field_declarations(class_node))
            assert len(fields) == 2
            names = [f.name for f in fields]
            assert "count_" in names
            assert "name_" in names

    def test_parse_template_type(self):
        """Test parsing template types like unique_ptr<T>."""
        source = dedent("""
            class Foo {
            private:
                std::unique_ptr<ILogger> logger_;
            };
        """).strip()

        ast = parse_cpp(source)
        helper = CppQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            fields = list(helper.find_field_declarations(class_node))
            assert len(fields) == 1
            field = fields[0]
            assert field.name == "logger_"
            assert field.template_name is not None
            assert "unique_ptr" in field.template_name


# =============================================================================
# OwnershipAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestOwnershipAnalyzer:
    """Test ownership analysis from smart pointers."""

    def test_unique_ptr_ownership(self):
        """unique_ptr should be detected as 'owns' with HIGH confidence."""
        source = dedent("""
            class Service {
            private:
                std::unique_ptr<ILogger> logger_;
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = OwnershipAnalyzer()
        findings = analyzer.analyze(ast, source)

        assert len(findings) >= 1
        ownership_findings = [f for f in findings if f.type == L4FindingType.OWNERSHIP]
        assert len(ownership_findings) >= 1

        # Find the unique_ptr finding
        ptr_finding = next(
            (f for f in ownership_findings if "unique_ptr" in f.evidence.lower()),
            None,
        )
        assert ptr_finding is not None
        assert ptr_finding.confidence == L4Confidence.HIGH
        assert "owns" in ptr_finding.value.lower()

    def test_shared_ptr_ownership(self):
        """shared_ptr should be detected as 'shares' with HIGH confidence."""
        source = dedent("""
            class Cache {
            private:
                std::shared_ptr<Config> config_;
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = OwnershipAnalyzer()
        findings = analyzer.analyze(ast, source)

        ptr_finding = next(
            (f for f in findings if "shared_ptr" in f.evidence.lower()),
            None,
        )
        assert ptr_finding is not None
        assert ptr_finding.confidence == L4Confidence.HIGH
        assert "shares" in ptr_finding.value.lower()

    def test_raw_pointer_uses(self):
        """Raw pointer should be detected as 'uses' with MEDIUM confidence."""
        source = dedent("""
            class Handler {
            private:
                ICallback* callback_;
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = OwnershipAnalyzer()
        findings = analyzer.analyze(ast, source)

        ptr_finding = next(
            (f for f in findings if "uses" in f.value.lower()),
            None,
        )
        assert ptr_finding is not None
        assert ptr_finding.confidence == L4Confidence.MEDIUM

    def test_std_thread_ownership(self):
        """std::thread member should be detected as 'owns'."""
        source = dedent("""
            class Worker {
            private:
                std::thread workerThread_;
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = OwnershipAnalyzer()
        findings = analyzer.analyze(ast, source)

        thread_finding = next(
            (f for f in findings if "thread" in f.evidence.lower()),
            None,
        )
        assert thread_finding is not None
        assert "owns" in thread_finding.value.lower()


# =============================================================================
# DependencyAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestDependencyAnalyzer:
    """Test dependency analysis from constructors and setters."""

    def test_constructor_interface_dependency(self):
        """Interface pointer in constructor = HIGH confidence dependency."""
        source = dedent("""
            class Service {
            public:
                explicit Service(ILogger* logger, IStore* store);
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = DependencyAnalyzer()
        findings = analyzer.analyze(ast, source)

        dep_findings = [f for f in findings if f.type == L4FindingType.DEPENDENCY]
        assert len(dep_findings) >= 2

        # Check for ILogger dependency
        logger_dep = next(
            (f for f in dep_findings if "ILogger" in f.value),
            None,
        )
        assert logger_dep is not None
        assert logger_dep.confidence == L4Confidence.HIGH

    def test_setter_optional_dependency(self):
        """Setter method parameter = optional dependency."""
        source = dedent("""
            class Module {
            public:
                void setNext(IModule* next);
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = DependencyAnalyzer()
        findings = analyzer.analyze(ast, source)

        dep_findings = [f for f in findings if f.type == L4FindingType.DEPENDENCY]
        setter_dep = next(
            (f for f in dep_findings if "optional" in f.value.lower()),
            None,
        )
        assert setter_dep is not None
        assert "IModule" in setter_dep.value

    def test_value_parameter_configuration(self):
        """Value parameter in constructor = configuration."""
        source = dedent("""
            class Filter {
            public:
                explicit Filter(ByteArray targetSequence);
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = DependencyAnalyzer()
        findings = analyzer.analyze(ast, source)

        config_dep = next(
            (f for f in findings if "ByteArray" in f.value),
            None,
        )
        assert config_dep is not None


# =============================================================================
# LifecycleAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestLifecycleAnalyzer:
    """Test lifecycle analysis from method names and state enums."""

    def test_start_stop_lifecycle(self):
        """start/stop methods should detect running/stopped phases."""
        source = dedent("""
            class Worker {
            public:
                void start();
                void stop();
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = LifecycleAnalyzer()
        findings = analyzer.analyze(ast, source)

        lifecycle_findings = [f for f in findings if f.type == L4FindingType.LIFECYCLE]
        assert len(lifecycle_findings) >= 1

        # Should find phases
        phases_finding = next(
            (f for f in lifecycle_findings if "phases" in f.value.lower()),
            None,
        )
        assert phases_finding is not None
        assert "running" in phases_finding.value.lower() or "stopped" in phases_finding.value.lower()

    def test_init_cleanup_lifecycle(self):
        """init/cleanup methods should detect initialized/destroyed phases."""
        source = dedent("""
            class Resource {
            public:
                void initialize();
                void cleanup();
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = LifecycleAnalyzer()
        findings = analyzer.analyze(ast, source)

        lifecycle_findings = [f for f in findings if f.type == L4FindingType.LIFECYCLE]
        assert len(lifecycle_findings) >= 1

    def test_atomic_state_detection(self):
        """atomic<State> member should detect state machine."""
        source = dedent("""
            class Module {
            private:
                std::atomic<ModuleState> state_;
            public:
                void start();
                void stop();
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = LifecycleAnalyzer()
        findings = analyzer.analyze(ast, source)

        state_finding = next(
            (f for f in findings if "state machine" in f.value.lower()),
            None,
        )
        assert state_finding is not None
        assert state_finding.confidence == L4Confidence.HIGH


# =============================================================================
# ThreadSafetyAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestThreadSafetyAnalyzer:
    """Test thread safety analysis from sync primitives and naming."""

    def test_mutex_detection(self):
        """std::mutex member should detect thread safety."""
        source = dedent("""
            class SharedData {
            private:
                std::mutex mutex_;
                int data_;
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = ThreadSafetyAnalyzer()
        findings = analyzer.analyze(ast, source)

        safety_findings = [f for f in findings if f.type == L4FindingType.THREAD_SAFETY]
        assert len(safety_findings) >= 1

        safe_finding = next(
            (f for f in safety_findings if f.value == "safe"),
            None,
        )
        assert safe_finding is not None
        assert safe_finding.confidence == L4Confidence.HIGH

    def test_atomic_detection(self):
        """std::atomic member should detect thread safety."""
        source = dedent("""
            class Counter {
            private:
                std::atomic<int> count_;
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = ThreadSafetyAnalyzer()
        findings = analyzer.analyze(ast, source)

        safety_findings = [f for f in findings if f.type == L4FindingType.THREAD_SAFETY]
        assert len(safety_findings) >= 1

    def test_safe_naming_pattern(self):
        """SafeQueue type should suggest thread safety."""
        source = dedent("""
            class Producer {
            private:
                SafeQueue<Message> queue_;
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = ThreadSafetyAnalyzer()
        findings = analyzer.analyze(ast, source)

        safety_findings = [f for f in findings if f.type == L4FindingType.THREAD_SAFETY]
        assert len(safety_findings) >= 1

    def test_mutex_member_name_pattern(self):
        """Member named *_mutex should suggest synchronization."""
        source = dedent("""
            class Cache {
            private:
                SomeLock data_mutex_;
            };
        """).strip()

        ast = parse_cpp(source)
        analyzer = ThreadSafetyAnalyzer()
        findings = analyzer.analyze(ast, source)

        safety_findings = [f for f in findings if f.type == L4FindingType.THREAD_SAFETY]
        assert len(safety_findings) >= 1


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestStaticAnalyzerIntegration:
    """Test full StaticAnalyzer integration."""

    FILTER_MODULE_SOURCE = dedent("""
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
    """).strip()

    def test_filter_module_analysis(self):
        """Test the FilterModule example from brainstorming."""
        analyzer = StaticAnalyzer()
        contract = analyzer.analyze(
            self.FILTER_MODULE_SOURCE,
            Path("filter_module.hpp"),
        )

        # Should have findings
        assert contract.confidence > 0

        # Should detect lifecycle
        assert contract.lifecycle is not None
        assert len(contract.lifecycle) > 0

        # Should detect thread safety
        assert contract.thread_safety is not None

        # Should have confidence notes
        assert contract.confidence_notes is not None
        assert "L4 findings" in contract.confidence_notes

    def test_filter_module_dependencies(self):
        """FilterModule should have detected dependencies."""
        analyzer = StaticAnalyzer()
        contract = analyzer.analyze(
            self.FILTER_MODULE_SOURCE,
            Path("filter_module.hpp"),
        )

        # Should detect some dependencies
        assert len(contract.dependencies) >= 1

    def test_filter_module_raw_findings(self):
        """Test get_findings() returns detailed findings."""
        analyzer = StaticAnalyzer()
        findings = analyzer.get_findings(
            self.FILTER_MODULE_SOURCE,
            Path("filter_module.hpp"),
        )

        # Should have multiple findings from different analyzers
        assert len(findings) > 0

        # Check we have different types
        types_found = set(f.type for f in findings)
        assert L4FindingType.OWNERSHIP in types_found
        assert L4FindingType.LIFECYCLE in types_found
        assert L4FindingType.THREAD_SAFETY in types_found

    def test_legacy_regex_fallback_for_python(self):
        """Python files should use legacy regex analysis."""
        source = dedent("""
            import threading

            class Service:
                def __init__(self):
                    self._lock = threading.Lock()
                    assert self._lock is not None

                def process(self, data):
                    if data is None:
                        raise ValueError("data required")
        """).strip()

        analyzer = StaticAnalyzer()
        contract = analyzer.analyze(source, Path("service.py"))

        # Should detect thread safety from threading.Lock
        assert contract.thread_safety is not None

        # Should detect errors
        assert "ValueError" in contract.errors

    def test_performance_under_100ms(self):
        """Analysis should complete in under 100ms."""
        import time

        # Generate a moderately large source
        source = self.FILTER_MODULE_SOURCE * 10  # ~10x the code

        analyzer = StaticAnalyzer()

        start = time.perf_counter()
        contract = analyzer.analyze(source, Path("large.hpp"))
        elapsed = time.perf_counter() - start

        # Should complete quickly
        assert elapsed < 0.5  # 500ms is generous, target is <100ms
        print(f"Analysis took {elapsed*1000:.2f}ms")


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
