# SPDX-License-Identifier: MIT
"""
Tests for L4 TypeScript/JavaScript Static Analysis.

Tests the TypeScript analyzer architecture including:
- TypeScriptQueryHelper
- TypeScriptOwnershipAnalyzer
- TypeScriptDependencyAnalyzer
- TypeScriptLifecycleAnalyzer
- TypeScriptThreadSafetyAnalyzer
- StaticAnalyzer integration for TypeScript
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
    TypeScriptDependencyAnalyzer,
    TypeScriptLifecycleAnalyzer,
    TypeScriptOwnershipAnalyzer,
    TypeScriptThreadSafetyAnalyzer,
)
from code_map.contracts.patterns.queries.typescript import TypeScriptQueryHelper

# Try to import tree-sitter
try:
    import tree_sitter_languages

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


def parse_typescript(source: str):
    """Parse TypeScript source code and return AST root."""
    parser = tree_sitter_languages.get_parser("typescript")
    tree = parser.parse(source.encode("utf-8"))
    return tree.root_node


# =============================================================================
# TypeScriptQueryHelper Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestTypeScriptQueryHelper:
    """Test TypeScript tree-sitter query helpers."""

    def test_find_class_declarations(self):
        """Test finding class declarations."""
        source = dedent("""
            class Foo {
            }

            class Bar {
            }
        """).strip()

        ast = parse_typescript(source)
        helper = TypeScriptQueryHelper(source)

        classes = list(helper.find_class_declarations(ast))
        assert len(classes) == 2

    def test_find_field_definitions(self):
        """Test finding field definitions in a class."""
        source = dedent("""
            class Service {
                private readonly logger: ILogger;
                private config: Config;
            }
        """).strip()

        ast = parse_typescript(source)
        helper = TypeScriptQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            fields = list(helper.find_field_definitions(class_node))
            assert len(fields) == 2

            logger_field = next(f for f in fields if f.name == "logger")
            assert logger_field.is_private
            assert logger_field.is_readonly
            assert logger_field.type_name == "ILogger"

            config_field = next(f for f in fields if f.name == "config")
            assert config_field.is_private
            assert not config_field.is_readonly

    def test_find_methods(self):
        """Test finding method definitions."""
        source = dedent("""
            class Service {
                constructor(logger: ILogger) {}
                start(): void {}
                stop(): void {}
            }
        """).strip()

        ast = parse_typescript(source)
        helper = TypeScriptQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            methods = list(helper.find_methods(class_node))
            assert len(methods) == 3

            names = [m.name for m in methods]
            assert "constructor" in names
            assert "start" in names
            assert "stop" in names

    def test_find_constructor_params(self):
        """Test finding constructor parameters."""
        source = dedent("""
            class Service {
                constructor(
                    private readonly logger: ILogger,
                    private config: Config
                ) {}
            }
        """).strip()

        ast = parse_typescript(source)
        helper = TypeScriptQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            for constructor in helper.find_constructors(class_node):
                params = constructor.parameters
                assert len(params) == 2

                logger_param = next(p for p in params if p.name == "logger")
                assert logger_param.type_name == "ILogger"
                assert logger_param.accessibility == "private"
                assert logger_param.is_readonly


# =============================================================================
# TypeScriptOwnershipAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestTypeScriptOwnershipAnalyzer:
    """Test TypeScript ownership analysis."""

    def test_private_readonly_ownership(self):
        """private readonly field = owns with HIGH confidence."""
        source = dedent("""
            class Service {
                private readonly logger: ILogger;
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptOwnershipAnalyzer()
        findings = analyzer.analyze(ast, source)

        logger_finding = next(
            (f for f in findings if f.member == "logger"),
            None,
        )
        assert logger_finding is not None
        assert logger_finding.confidence == L4Confidence.HIGH
        assert "owns" in logger_finding.value.lower()

    def test_private_field_manages(self):
        """private (non-readonly) field = manages."""
        source = dedent("""
            class Service {
                private config: Config;
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptOwnershipAnalyzer()
        findings = analyzer.analyze(ast, source)

        config_finding = next(
            (f for f in findings if f.member == "config"),
            None,
        )
        assert config_finding is not None
        assert "manages" in config_finding.value.lower()

    def test_constructor_parameter_property(self):
        """Constructor parameter property = ownership."""
        source = dedent("""
            class Service {
                constructor(private readonly logger: ILogger) {}
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptOwnershipAnalyzer()
        findings = analyzer.analyze(ast, source)

        ownership_findings = [f for f in findings if f.type == L4FindingType.OWNERSHIP]
        assert len(ownership_findings) >= 1


# =============================================================================
# TypeScriptDependencyAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestTypeScriptDependencyAnalyzer:
    """Test TypeScript dependency analysis."""

    def test_constructor_dependency(self):
        """Constructor parameter = dependency."""
        source = dedent("""
            class Service {
                constructor(logger: ILogger, store: IStore) {}
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptDependencyAnalyzer()
        findings = analyzer.analyze(ast, source)

        dep_findings = [f for f in findings if f.type == L4FindingType.DEPENDENCY]
        assert len(dep_findings) >= 2

        logger_dep = next(
            (f for f in dep_findings if "ILogger" in f.value),
            None,
        )
        assert logger_dep is not None
        # Interface type = high confidence
        assert logger_dep.confidence == L4Confidence.HIGH

    def test_implements_interface(self):
        """implements clause = dependency on interface."""
        source = dedent("""
            class Service implements IService {
                start(): void {}
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptDependencyAnalyzer()
        findings = analyzer.analyze(ast, source)

        impl_finding = next(
            (f for f in findings if "implements" in f.value.lower()),
            None,
        )
        assert impl_finding is not None
        assert "IService" in impl_finding.value


# =============================================================================
# TypeScriptLifecycleAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestTypeScriptLifecycleAnalyzer:
    """Test TypeScript lifecycle analysis."""

    def test_start_stop_lifecycle(self):
        """start/stop methods should detect lifecycle phases."""
        source = dedent("""
            class Service {
                start(): void {}
                stop(): void {}
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptLifecycleAnalyzer()
        findings = analyzer.analyze(ast, source)

        lifecycle_findings = [f for f in findings if f.type == L4FindingType.LIFECYCLE]
        assert len(lifecycle_findings) >= 1

        phases_finding = next(
            (f for f in lifecycle_findings if "phases" in f.value.lower()),
            None,
        )
        assert phases_finding is not None

    def test_angular_lifecycle_hooks(self):
        """Angular lifecycle hooks should be detected."""
        source = dedent("""
            class MyComponent {
                ngOnInit(): void {}
                ngOnDestroy(): void {}
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptLifecycleAnalyzer()
        findings = analyzer.analyze(ast, source)

        angular_findings = [f for f in findings if "Angular" in f.value]
        assert len(angular_findings) >= 1

    def test_react_lifecycle_hooks(self):
        """React lifecycle methods should be detected."""
        source = dedent("""
            class MyComponent {
                componentDidMount(): void {}
                componentWillUnmount(): void {}
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptLifecycleAnalyzer()
        findings = analyzer.analyze(ast, source)

        react_findings = [f for f in findings if "React" in f.value]
        assert len(react_findings) >= 1

    def test_dispose_method(self):
        """dispose() method should be detected."""
        source = dedent("""
            class Resource {
                dispose(): void {}
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptLifecycleAnalyzer()
        findings = analyzer.analyze(ast, source)

        dispose_finding = next(
            (f for f in findings if "disposed" in f.value.lower()),
            None,
        )
        assert dispose_finding is not None
        assert dispose_finding.confidence == L4Confidence.HIGH


# =============================================================================
# TypeScriptThreadSafetyAnalyzer Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestTypeScriptThreadSafetyAnalyzer:
    """Test TypeScript thread safety analysis."""

    def test_worker_detection(self):
        """Worker type should detect concurrency."""
        source = dedent("""
            class TaskRunner {
                private worker: Worker;
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptThreadSafetyAnalyzer()
        findings = analyzer.analyze(ast, source)

        worker_finding = next(
            (f for f in findings if "Worker" in f.value),
            None,
        )
        assert worker_finding is not None
        assert worker_finding.confidence == L4Confidence.HIGH

    def test_rxjs_subject_detection(self):
        """RxJS Subject types should detect thread safety."""
        source = dedent("""
            class DataService {
                private data$: BehaviorSubject<Data>;
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptThreadSafetyAnalyzer()
        findings = analyzer.analyze(ast, source)

        subject_finding = next(
            (f for f in findings if "Subject" in f.value),
            None,
        )
        assert subject_finding is not None

    def test_lock_name_pattern(self):
        """Field named *lock* should suggest synchronization."""
        source = dedent("""
            class Cache {
                private dataLock: Mutex;
            }
        """).strip()

        ast = parse_typescript(source)
        analyzer = TypeScriptThreadSafetyAnalyzer()
        findings = analyzer.analyze(ast, source)

        safety_findings = [f for f in findings if f.type == L4FindingType.THREAD_SAFETY]
        assert len(safety_findings) >= 1


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not available")
class TestTypeScriptStaticAnalyzerIntegration:
    """Test full StaticAnalyzer integration for TypeScript."""

    TS_SERVICE_SOURCE = dedent("""
        interface ILogger {
            log(msg: string): void;
        }

        interface IService {
            start(): void;
            stop(): void;
        }

        class Service implements IService {
            private readonly logger: ILogger;
            private worker: Worker;
            private running: boolean = false;

            constructor(logger: ILogger) {
                this.logger = logger;
            }

            start(): void {
                this.running = true;
            }

            stop(): void {
                this.running = false;
            }

            dispose(): void {
                this.worker.terminate();
            }
        }
    """).strip()

    def test_typescript_service_analysis(self):
        """Test TypeScript service analysis."""
        analyzer = StaticAnalyzer()
        contract = analyzer.analyze(
            self.TS_SERVICE_SOURCE,
            Path("service.ts"),
        )

        # Should have confidence
        assert contract.confidence > 0

        # Should detect lifecycle
        assert contract.lifecycle is not None

    def test_typescript_service_dependencies(self):
        """TypeScript service should have detected dependencies."""
        analyzer = StaticAnalyzer()
        contract = analyzer.analyze(
            self.TS_SERVICE_SOURCE,
            Path("service.ts"),
        )

        # Should detect dependencies
        assert len(contract.dependencies) >= 1

    def test_typescript_raw_findings(self):
        """Test get_findings() for TypeScript."""
        analyzer = StaticAnalyzer()
        findings = analyzer.get_findings(
            self.TS_SERVICE_SOURCE,
            Path("service.ts"),
        )

        assert len(findings) > 0

        # Check we have different types
        types_found = set(f.type for f in findings)
        assert L4FindingType.OWNERSHIP in types_found
        assert L4FindingType.LIFECYCLE in types_found

    def test_javascript_file_support(self):
        """Test .js files are also analyzed."""
        js_source = dedent("""
            class Service {
                constructor(logger) {
                    this.logger = logger;
                }

                start() {}
                stop() {}
            }
        """).strip()

        analyzer = StaticAnalyzer()
        contract = analyzer.analyze(js_source, Path("service.js"))

        # Should have some lifecycle detection
        assert contract.lifecycle is not None or contract.confidence > 0


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
