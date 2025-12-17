# SPDX-License-Identifier: MIT
"""
Tests for the contract discovery, parsing, and rewriting system.
"""

import pytest
from pathlib import Path
from textwrap import dedent

from code_map.contracts import (
    ContractData,
    ContractDiscovery,
    ContractRewriter,
    EvidenceItem,
    EvidencePolicy,
    ThreadSafety,
)
from code_map.contracts.languages.registry import LanguageRegistry
from code_map.contracts.languages.cpp import CppLanguageStrategy
from code_map.contracts.languages.python import PythonLanguageStrategy


# ─────────────────────────────────────────────────────────────
# ContractData Tests
# ─────────────────────────────────────────────────────────────


class TestContractData:
    """Tests for ContractData schema."""

    def test_empty_contract(self):
        """Empty contract should report is_empty=True."""
        contract = ContractData()
        assert contract.is_empty()
        assert contract.confidence == 1.0
        assert contract.source_level == 0

    def test_contract_with_data_not_empty(self):
        """Contract with any data should not be empty."""
        contract = ContractData(thread_safety=ThreadSafety.SAFE)
        assert not contract.is_empty()

        contract2 = ContractData(preconditions=["x > 0"])
        assert not contract2.is_empty()

    def test_to_yaml_and_back(self):
        """Contract should serialize to YAML and back."""
        contract = ContractData(
            thread_safety=ThreadSafety.SAFE,
            lifecycle="singleton",
            invariants=["count >= 0"],
            preconditions=["input is not None"],
            postconditions=["returns valid result"],
            errors=["ValueError: invalid input"],
        )

        yaml_str = contract.to_yaml()
        assert "thread_safety: safe" in yaml_str
        assert "lifecycle: singleton" in yaml_str
        assert "count >= 0" in yaml_str

        restored = ContractData.from_yaml(yaml_str)
        assert restored.thread_safety == ThreadSafety.SAFE
        assert restored.lifecycle == "singleton"
        assert "count >= 0" in restored.invariants

    def test_to_dict_and_back(self):
        """Contract should convert to dict and back."""
        contract = ContractData(
            thread_safety=ThreadSafety.IMMUTABLE,
            preconditions=["a > b"],
            evidence=[
                EvidenceItem(
                    type="test",
                    reference="tests/test_foo.py::test_bar",
                    policy=EvidencePolicy.REQUIRED,
                )
            ],
        )

        data = contract.to_dict()
        assert data["thread_safety"] == "immutable"
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["policy"] == "required"

        restored = ContractData.from_dict(data)
        assert restored.thread_safety == ThreadSafety.IMMUTABLE
        assert len(restored.evidence) == 1
        assert restored.evidence[0].policy == EvidencePolicy.REQUIRED

    def test_has_required_evidence(self):
        """Should detect if required evidence is passing."""
        contract = ContractData()
        # No required evidence = all (empty) are passing = True
        assert contract.has_required_evidence()

        # Add optional evidence - still True (no required)
        contract.evidence.append(
            EvidenceItem(type="test", reference="test.py", policy=EvidencePolicy.OPTIONAL)
        )
        assert contract.has_required_evidence()

        # Add required evidence (not yet run) - False
        required_item = EvidenceItem(
            type="test", reference="test2.py", policy=EvidencePolicy.REQUIRED
        )
        contract.evidence.append(required_item)
        assert not contract.has_required_evidence()

        # Mark as passing
        required_item.last_result = True
        assert contract.has_required_evidence()


# ─────────────────────────────────────────────────────────────
# Language Registry Tests
# ─────────────────────────────────────────────────────────────


class TestLanguageRegistry:
    """Tests for language strategy registry."""

    def test_cpp_strategy_registered(self):
        """C++ strategy should be registered for .cpp files."""
        strategy = LanguageRegistry.get_for_file(Path("test.cpp"))
        assert strategy is not None
        assert isinstance(strategy, CppLanguageStrategy)

    def test_python_strategy_registered(self):
        """Python strategy should be registered for .py files."""
        strategy = LanguageRegistry.get_for_file(Path("test.py"))
        assert strategy is not None
        assert isinstance(strategy, PythonLanguageStrategy)

    def test_header_files_use_cpp(self):
        """Header files should use C++ strategy."""
        for ext in [".h", ".hpp", ".hxx"]:
            strategy = LanguageRegistry.get_for_file(Path(f"test{ext}"))
            assert isinstance(strategy, CppLanguageStrategy)

    def test_unknown_extension_returns_none(self):
        """Unknown extensions should return None."""
        strategy = LanguageRegistry.get_for_file(Path("test.unknown"))
        assert strategy is None

    def test_supported_languages(self):
        """Should list supported languages."""
        languages = LanguageRegistry.supported_languages()
        assert "cpp" in languages
        assert "python" in languages

    def test_supported_extensions(self):
        """Should list supported extensions."""
        extensions = LanguageRegistry.supported_extensions()
        assert ".py" in extensions
        assert ".cpp" in extensions
        assert ".hpp" in extensions


# ─────────────────────────────────────────────────────────────
# C++ Strategy Tests
# ─────────────────────────────────────────────────────────────


class TestCppStrategy:
    """Tests for C++ language strategy."""

    def test_find_contract_block_level1(self):
        """Should find @aegis-contract block in C++."""
        source = dedent("""
            // @aegis-contract-begin
            // thread_safety: safe
            // preconditions:
            //   - input != nullptr
            // @aegis-contract-end
            void process(void* input) {
                // implementation
            }
        """).strip()

        strategy = CppLanguageStrategy()
        block = strategy.find_contract_block(source, symbol_line=7)

        assert block is not None
        assert block.start_line == 1
        assert block.end_line == 5
        assert "thread_safety: safe" in block.content

    def test_parse_doxygen_patterns(self):
        """Should extract contracts from Doxygen comments."""
        source = dedent("""
            /**
             * Process the input data.
             *
             * @pre input must not be null
             * @post result is valid
             * @throws std::invalid_argument if input is invalid
             * @note Safe after start
             */
            void process(Data* input);
        """).strip()

        strategy = CppLanguageStrategy()
        comment = strategy.find_comment_block(source, symbol_line=9)

        assert comment is not None
        contract = strategy.parse_known_patterns(comment)

        assert "input must not be null" in contract.preconditions
        assert "result is valid" in contract.postconditions
        assert any("invalid_argument" in e for e in contract.errors)
        assert contract.thread_safety == ThreadSafety.SAFE_AFTER_START

    def test_detect_thread_safety_patterns(self):
        """Should detect various thread safety patterns."""
        test_cases = [
            ("// Thread-safe implementation", ThreadSafety.SAFE),
            ("// Not thread-safe", ThreadSafety.NOT_SAFE),
            ("// Safe after start", ThreadSafety.SAFE_AFTER_START),
            ("// Immutable object", ThreadSafety.IMMUTABLE),
        ]

        strategy = CppLanguageStrategy()
        for comment_text, expected_safety in test_cases:
            source = f"{comment_text}\nvoid func();"
            comment = strategy.find_comment_block(source, symbol_line=2)
            if comment:
                contract = strategy.parse_known_patterns(comment)
                assert contract.thread_safety == expected_safety, f"Failed for: {comment_text}"


# ─────────────────────────────────────────────────────────────
# Python Strategy Tests
# ─────────────────────────────────────────────────────────────


class TestPythonStrategy:
    """Tests for Python language strategy."""

    def test_find_contract_in_docstring(self):
        """Should find @aegis-contract inside docstring."""
        source = dedent('''
            def process(data):
                """
                @aegis-contract-begin
                thread_safety: safe
                preconditions:
                  - data is not None
                @aegis-contract-end

                Process the input data.
                """
                return data
        ''').strip()

        strategy = PythonLanguageStrategy()
        block = strategy.find_contract_block(source, symbol_line=1)

        assert block is not None
        assert "thread_safety: safe" in block.content

    def test_parse_google_style_docstring(self):
        """Should extract contracts from Google-style docstrings."""
        source = dedent('''
            def calculate(x, y):
                """Calculate the result.

                Args:
                    x: First value. Must be positive.
                    y: Second value. Must not be None.

                Returns:
                    The calculated result.

                Raises:
                    ValueError: If x is negative.
                    TypeError: If y is None.

                Note:
                    This function is thread-safe.
                """
                pass
        ''').strip()

        strategy = PythonLanguageStrategy()
        comment = strategy.find_comment_block(source, symbol_line=1)

        assert comment is not None
        contract = strategy.parse_known_patterns(comment)

        assert any("ValueError" in e or "negative" in e for e in contract.errors)
        assert contract.thread_safety == ThreadSafety.SAFE

    def test_single_line_docstring(self):
        """Should handle single-line docstrings."""
        source = dedent('''
            def simple():
                """Simple function."""
                pass
        ''').strip()

        strategy = PythonLanguageStrategy()
        comment = strategy.find_comment_block(source, symbol_line=1)

        assert comment is not None
        assert "Simple function" in comment.content


# ─────────────────────────────────────────────────────────────
# Contract Discovery Tests
# ─────────────────────────────────────────────────────────────


class TestContractDiscovery:
    """Tests for contract discovery pipeline."""

    def test_discover_level1_contract(self, tmp_path):
        """Should discover Level 1 @aegis-contract."""
        test_file = tmp_path / "test.py"
        test_file.write_text(dedent('''
            def process(data):
                """
                @aegis-contract-begin
                thread_safety: safe
                preconditions:
                  - data is not None
                postconditions:
                  - returns valid result
                @aegis-contract-end
                """
                return data
        ''').strip())

        discovery = ContractDiscovery(enable_llm=False)
        contract = discovery.discover(test_file, symbol_line=1)

        assert contract.source_level == 1
        assert contract.confidence == 1.0
        assert contract.thread_safety == ThreadSafety.SAFE
        assert "data is not None" in contract.preconditions

    def test_discover_level2_patterns(self, tmp_path):
        """Should discover Level 2 from known patterns."""
        test_file = tmp_path / "test.cpp"
        test_file.write_text(dedent("""
            /**
             * @pre buffer != nullptr
             * @post result >= 0
             * @throws std::runtime_error on failure
             */
            int process(char* buffer);
        """).strip())

        discovery = ContractDiscovery(enable_llm=False)
        contract = discovery.discover(test_file, symbol_line=6)

        assert contract.source_level == 2
        assert contract.confidence == 0.8
        assert any("buffer" in p for p in contract.preconditions)

    def test_discover_unsupported_language(self, tmp_path):
        """Should return empty contract for unsupported languages."""
        test_file = tmp_path / "test.rs"
        test_file.write_text("fn main() {}")

        discovery = ContractDiscovery(enable_llm=False)
        contract = discovery.discover(test_file, symbol_line=1)

        assert contract.is_empty()

    def test_discover_with_specific_levels(self, tmp_path):
        """Should only run specified levels."""
        test_file = tmp_path / "test.py"
        test_file.write_text(dedent('''
            def func():
                """Thread-safe function."""
                pass
        ''').strip())

        discovery = ContractDiscovery(enable_llm=False)

        # Only Level 1 - should not find pattern-based contracts
        contract = discovery.discover(test_file, symbol_line=1, levels=[1])
        assert contract.is_empty() or contract.source_level == 1


# ─────────────────────────────────────────────────────────────
# Contract Rewriter Tests
# ─────────────────────────────────────────────────────────────


class TestContractRewriter:
    """Tests for contract rewriter."""

    def test_write_contract_to_cpp(self, tmp_path):
        """Should write contract block to C++ file."""
        test_file = tmp_path / "test.cpp"
        test_file.write_text(dedent("""
            void process(int x) {
                // implementation
            }
        """).strip())

        contract = ContractData(
            thread_safety=ThreadSafety.SAFE,
            preconditions=["x > 0"],
        )

        rewriter = ContractRewriter()
        # write_contract returns (modified_source, diff)
        modified_source, diff = rewriter.write_contract(test_file, symbol_line=1, contract=contract)

        assert "@aegis-contract-begin" in diff
        assert "thread_safety: safe" in diff
        assert "@aegis-contract-begin" in modified_source

    def test_preview_without_writing(self, tmp_path):
        """Preview should return diff without modifying file."""
        test_file = tmp_path / "test.py"
        original = dedent('''
            def func():
                pass
        ''').strip()
        test_file.write_text(original)

        contract = ContractData(preconditions=["input valid"])

        rewriter = ContractRewriter()
        diff = rewriter.preview_contract(test_file, symbol_line=1, contract=contract)

        assert "@aegis-contract-begin" in diff
        # File should not be modified
        assert test_file.read_text() == original

    def test_update_existing_contract(self, tmp_path):
        """Should update existing contract block."""
        test_file = tmp_path / "test.cpp"
        test_file.write_text(dedent("""
            // @aegis-contract-begin
            // thread_safety: not_safe
            // @aegis-contract-end
            void process();
        """).strip())

        contract = ContractData(
            thread_safety=ThreadSafety.SAFE,
            preconditions=["new precondition"],
        )

        rewriter = ContractRewriter()
        modified_source, diff = rewriter.write_contract(test_file, symbol_line=4, contract=contract)

        assert "thread_safety: safe" in modified_source
        assert "new precondition" in modified_source
        assert "not_safe" not in modified_source


# ─────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────


class TestContractIntegration:
    """Integration tests for contract system."""

    def test_discover_write_discover_roundtrip(self, tmp_path):
        """Write a contract, then discover it again."""
        test_file = tmp_path / "test.py"
        test_file.write_text(dedent('''
            def calculate(x, y):
                """Calculate sum."""
                return x + y
        ''').strip())

        # Write contract
        contract = ContractData(
            thread_safety=ThreadSafety.IMMUTABLE,
            preconditions=["x >= 0", "y >= 0"],
            postconditions=["result >= 0"],
        )

        rewriter = ContractRewriter()
        # apply_contract writes to file and returns diff
        diff = rewriter.apply_contract(test_file, symbol_line=1, contract=contract)
        assert "@aegis-contract-begin" in diff

        # Discover it back
        discovery = ContractDiscovery(enable_llm=False)
        discovered = discovery.discover(test_file, symbol_line=1)

        assert discovered.source_level == 1
        assert discovered.thread_safety == ThreadSafety.IMMUTABLE
        assert "x >= 0" in discovered.preconditions
        assert "y >= 0" in discovered.preconditions

    def test_full_workflow_cpp(self, tmp_path):
        """Full workflow test for C++ file."""
        test_file = tmp_path / "processor.hpp"
        test_file.write_text(dedent("""
            #pragma once

            /**
             * @brief Process data buffer
             * @pre buffer != nullptr
             * @pre size > 0
             * @post result is valid
             * @throws std::invalid_argument if buffer is null
             * @note Thread-safe
             */
            int process(const char* buffer, size_t size);
        """).strip())

        # Discover from Doxygen
        discovery = ContractDiscovery(enable_llm=False)
        contract = discovery.discover(test_file, symbol_line=11)

        assert contract.source_level == 2
        assert contract.thread_safety == ThreadSafety.SAFE
        assert len(contract.preconditions) >= 1
        assert len(contract.errors) >= 1

        # Upgrade to Level 1 - apply_contract writes to file
        rewriter = ContractRewriter()
        diff = rewriter.apply_contract(test_file, symbol_line=11, contract=contract)
        assert "@aegis-contract-begin" in diff

        # Verify content was written
        content = test_file.read_text()
        assert "@aegis-contract-begin" in content
