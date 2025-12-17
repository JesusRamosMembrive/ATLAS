# SPDX-License-Identifier: MIT
"""
Python language strategy for contract parsing and rewriting.

Supports:
- @aegis-contract blocks in docstrings
- Google style docstrings (Args, Returns, Raises)
- NumPy style docstrings
"""

import re
from typing import Dict, List, Optional, Tuple

from ..schema import ContractData, ThreadSafety
from .base import CommentBlock, ContractBlock, LanguageStrategy
from .registry import LanguageRegistry


@LanguageRegistry.register
class PythonLanguageStrategy(LanguageStrategy):
    """Strategy for Python files."""

    @property
    def language_id(self) -> str:
        return "python"

    @property
    def file_extensions(self) -> Tuple[str, ...]:
        return (".py", ".pyi")

    @property
    def comment_styles(self) -> dict:
        return {
            "line": "#",
            "docstring_single": "'''",
            "docstring_double": '"""',
        }

    # ─────────────────────────────────────────────────────────────
    # Google Style patterns
    # ─────────────────────────────────────────────────────────────

    GOOGLE_STYLE_SECTIONS = {
        "Args": "args",
        "Arguments": "args",
        "Returns": "returns",
        "Yields": "yields",
        "Raises": "errors",
        "Attributes": "attributes",
        "Note": "notes",
        "Notes": "notes",
        "Example": "examples",
        "Examples": "examples",
    }

    # ─────────────────────────────────────────────────────────────
    # Parsing: Level 1 - AEGIS contract blocks
    # ─────────────────────────────────────────────────────────────

    def find_contract_block(
        self, source: str, symbol_line: int
    ) -> Optional[ContractBlock]:
        """Find @aegis-contract inside the docstring of the symbol."""
        lines = source.splitlines()

        # In Python, contract is INSIDE the docstring, not before
        # Find docstring start after the symbol
        docstring_start = None
        docstring_end = None
        quote_style = None

        for i in range(symbol_line - 1, min(symbol_line + 5, len(lines))):
            if i >= len(lines):
                break
            line = lines[i].strip()

            # Check for docstring
            for quote in ['"""', "'''"]:
                if quote in line:
                    quote_style = quote
                    docstring_start = i

                    # Single-line docstring?
                    if line.count(quote) >= 2:
                        docstring_end = i
                        break

                    # Find closing quote
                    for j in range(i + 1, len(lines)):
                        if quote in lines[j]:
                            docstring_end = j
                            break
                    break
            if docstring_start is not None:
                break

        if docstring_start is None or docstring_end is None:
            return None

        # Find @aegis-contract inside the docstring
        start_marker = "@aegis-contract-begin"
        end_marker = "@aegis-contract-end"

        contract_start = None
        contract_end = None

        for i in range(docstring_start, docstring_end + 1):
            line = lines[i]
            if start_marker in line:
                contract_start = i
            if end_marker in line:
                contract_end = i
                break

        if contract_start is not None and contract_end is not None:
            content_lines = []
            for i in range(contract_start + 1, contract_end):
                content_lines.append(lines[i].strip())

            return ContractBlock(
                start_line=contract_start + 1,
                end_line=contract_end + 1,
                content="\n".join(content_lines),
                raw_text="\n".join(lines[contract_start : contract_end + 1]),
            )

        return None

    # ─────────────────────────────────────────────────────────────
    # Parsing: Level 2 - Google style patterns
    # ─────────────────────────────────────────────────────────────

    def find_comment_block(
        self, source: str, symbol_line: int
    ) -> Optional[CommentBlock]:
        """Find the docstring of a function/class."""
        lines = source.splitlines()

        # Find docstring after the symbol (def/class)
        for i in range(symbol_line - 1, min(symbol_line + 3, len(lines))):
            if i >= len(lines):
                break
            line = lines[i].strip()

            for quote in ['"""', "'''"]:
                if quote in line:
                    start_idx = i

                    # Single-line docstring
                    if line.count(quote) >= 2:
                        # Extract content between quotes
                        content = line.split(quote)[1] if len(line.split(quote)) > 1 else ""
                        return CommentBlock(
                            start_line=i + 1,
                            end_line=i + 1,
                            content=content,
                            style="docstring",
                        )

                    # Multi-line docstring
                    content_lines = [line.replace(quote, "").strip()]
                    for j in range(i + 1, len(lines)):
                        end_line_content = lines[j]
                        if quote in end_line_content:
                            content_lines.append(
                                end_line_content.replace(quote, "").strip()
                            )
                            return CommentBlock(
                                start_line=i + 1,
                                end_line=j + 1,
                                content="\n".join(content_lines),
                                style="docstring",
                            )
                        content_lines.append(end_line_content.strip())

        return None

    def parse_known_patterns(self, comment: CommentBlock) -> ContractData:
        """Extract contract from Google style docstring."""
        content = comment.content
        contract = ContractData(confidence=0.8, source_level=2)

        # Parse sections
        sections = self._parse_google_sections(content)

        # Raises -> errors
        if "Raises" in sections:
            for line in sections["Raises"]:
                line = line.strip()
                if line and not line.startswith("Raises"):
                    contract.errors.append(line)

        # Note/Notes -> thread safety and other info
        if "Note" in sections or "Notes" in sections:
            notes_content = " ".join(sections.get("Note", []) + sections.get("Notes", []))
            notes_lower = notes_content.lower()

            if "thread-safe" in notes_lower or "threadsafe" in notes_lower:
                if "not thread" in notes_lower:
                    contract.thread_safety = ThreadSafety.NOT_SAFE
                elif "after start" in notes_lower:
                    contract.thread_safety = ThreadSafety.SAFE_AFTER_START
                else:
                    contract.thread_safety = ThreadSafety.SAFE

        # Args -> preconditions (look for "Must" patterns)
        if "Args" in sections or "Arguments" in sections:
            args_content = " ".join(
                sections.get("Args", []) + sections.get("Arguments", [])
            )
            args_lower = args_content.lower()

            if "must not be none" in args_lower:
                contract.preconditions.append("input is not None")
            if "must be" in args_lower:
                must_match = re.search(r"must be ([^.]+)", args_content, re.I)
                if must_match:
                    contract.preconditions.append(f"input must be {must_match.group(1)}")

        # Returns -> postconditions
        if "Returns" in sections:
            returns_content = " ".join(sections["Returns"])
            if returns_content.strip():
                contract.postconditions.append(f"returns: {returns_content.strip()}")

        return contract

    def _parse_google_sections(self, content: str) -> Dict[str, List[str]]:
        """Parse Google-style docstring into sections."""
        sections: Dict[str, List[str]] = {}
        current_section = None
        current_lines: List[str] = []

        for line in content.splitlines():
            # Check if this starts a new section
            stripped = line.strip()
            section_match = None

            for section_name in self.GOOGLE_STYLE_SECTIONS:
                if stripped.startswith(f"{section_name}:"):
                    section_match = section_name
                    break

            if section_match:
                # Save previous section
                if current_section:
                    sections[current_section] = current_lines

                current_section = section_match
                current_lines = []
            else:
                current_lines.append(line)

        # Save last section
        if current_section:
            sections[current_section] = current_lines

        return sections

    # ─────────────────────────────────────────────────────────────
    # Rewriting
    # ─────────────────────────────────────────────────────────────

    def insert_contract_block(
        self, source: str, symbol_line: int, contract: ContractData
    ) -> str:
        """Insert @aegis-contract at the start of docstring."""
        lines = source.splitlines()

        # Find existing docstring
        docstring_info = self._find_docstring_location(lines, symbol_line)

        if docstring_info:
            # Insert inside existing docstring
            return self._insert_into_existing_docstring(lines, docstring_info, contract)
        else:
            # Create new docstring
            return self._create_new_docstring(lines, symbol_line, contract)

    def _find_docstring_location(
        self, lines: List[str], symbol_line: int
    ) -> Optional[dict]:
        """Find docstring location if it exists."""
        for i in range(symbol_line - 1, min(symbol_line + 3, len(lines))):
            if i >= len(lines):
                break
            line = lines[i].strip()

            for quote in ['"""', "'''"]:
                if quote in line:
                    # Find end of docstring
                    if line.count(quote) >= 2:
                        return {
                            "start": i,
                            "end": i,
                            "quote": quote,
                            "single_line": True,
                        }
                    for j in range(i + 1, len(lines)):
                        if quote in lines[j]:
                            return {
                                "start": i,
                                "end": j,
                                "quote": quote,
                                "single_line": False,
                            }
        return None

    def _insert_into_existing_docstring(
        self, lines: List[str], docstring_info: dict, contract: ContractData
    ) -> str:
        """Insert contract block into existing docstring."""
        start = docstring_info["start"]
        quote = docstring_info["quote"]
        indent = self.detect_indentation("\n".join(lines), start + 1)
        inner_indent = indent + "    "

        # Generate contract block
        contract_block = [
            f"{inner_indent}@aegis-contract-begin",
        ]
        yaml_content = self.format_contract_yaml(contract, indent=inner_indent)
        contract_block.extend(yaml_content.splitlines())
        contract_block.append(f"{inner_indent}@aegis-contract-end")
        contract_block.append("")  # Empty line before rest of docstring

        if docstring_info["single_line"]:
            # Convert to multiline
            original_content = lines[start].strip().strip(quote).strip()
            new_lines = lines[:start]
            new_lines.append(f"{indent}{quote}")
            new_lines.extend(contract_block)
            if original_content:
                new_lines.append(f"{inner_indent}{original_content}")
            new_lines.append(f"{indent}{quote}")
            new_lines.extend(lines[start + 1 :])
        else:
            # Insert after opening quote line
            new_lines = lines[: start + 1]
            new_lines.extend(contract_block)
            new_lines.extend(lines[start + 1 :])

        return "\n".join(new_lines)

    def _create_new_docstring(
        self, lines: List[str], symbol_line: int, contract: ContractData
    ) -> str:
        """Create new docstring with contract."""
        # Find line after def/class
        insert_idx = symbol_line  # After the symbol
        indent = self.detect_indentation("\n".join(lines), symbol_line)
        inner_indent = indent + "    "

        docstring_lines = [
            f'{inner_indent}"""',
            f"{inner_indent}@aegis-contract-begin",
        ]
        yaml_content = self.format_contract_yaml(contract, indent=inner_indent)
        docstring_lines.extend(yaml_content.splitlines())
        docstring_lines.append(f"{inner_indent}@aegis-contract-end")
        docstring_lines.append(f'{inner_indent}"""')

        new_lines = lines[:insert_idx] + docstring_lines + lines[insert_idx:]
        return "\n".join(new_lines)

    def update_contract_block(
        self, source: str, block: ContractBlock, contract: ContractData
    ) -> str:
        """Update existing block inside docstring."""
        lines = source.splitlines()

        # Detect indentation
        first_line = lines[block.start_line - 1]
        indent = first_line[: len(first_line) - len(first_line.lstrip())]

        # Generate new content
        new_block_lines = [
            f"{indent}@aegis-contract-begin",
        ]
        yaml_content = self.format_contract_yaml(contract, indent=indent)
        new_block_lines.extend(yaml_content.splitlines())
        new_block_lines.append(f"{indent}@aegis-contract-end")

        # Replace
        start_idx = block.start_line - 1
        end_idx = block.end_line

        new_lines = lines[:start_idx] + new_block_lines + lines[end_idx:]
        return "\n".join(new_lines)
