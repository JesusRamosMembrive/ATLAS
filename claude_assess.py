#!/usr/bin/env python3
"""
Generate detailed assessment report for manual review.

This script generates a comprehensive stage assessment report combining:
1. Visual project tree structure
2. Automated stage detection metrics
3. Instructions for Claude Code to perform deep analysis

The output is formatted as Markdown for easy copy-paste into Claude Code
or documentation. It's designed for borderline cases where automated
detection needs human verification.

Usage:
    python claude_assess.py <project-path>

Output:
    Markdown-formatted report to stdout containing:
    - Project structure tree (rendered natively, depth 3)
    - Automated assessment results (using assess_stage module)
    - Analysis instructions for Claude Code
    - Decision criteria for Stage 2 vs Stage 3 borderline cases

Dependencies:
    - assess_stage.py (must be in same directory)

Notes:
    - Ignores common noise (.venv, node_modules, .git, etc.)
    - Focuses on Stage 2/3 distinction (most common ambiguity)
    - Provides specific guidance for human/AI review
    - Output can be piped to file or clipboard
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from assess_stage import assess_stage, print_assessment

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python claude_assess.py <project-path>")
        sys.exit(1)

    project_path = Path(sys.argv[1])

    IGNORE_NAMES = {
        ".venv",
        "node_modules",
        ".git",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
    IGNORE_SUFFIXES = (".pyc", ".egg-info")
    MAX_DEPTH = 3

    def _should_ignore(path: Path) -> bool:
        name = path.name
        if name in IGNORE_NAMES:
            return True
        return any(name.endswith(suffix) for suffix in IGNORE_SUFFIXES)

    def _children(path: Path) -> List[Path]:
        try:
            entries = [child for child in path.iterdir() if not _should_ignore(child)]
        except OSError:
            return []
        return sorted(entries, key=lambda item: (not item.is_dir(), item.name.lower()))

    def _render_branch(root: Path, depth: int, prefix: str, lines: List[str]) -> None:
        if depth > MAX_DEPTH:
            return
        entries = _children(root)
        last_index = len(entries) - 1
        for index, child in enumerate(entries):
            connector = "└── " if index == last_index else "├── "
            display_name = f"{child.name}/" if child.is_dir() else child.name
            lines.append(f"{prefix}{connector}{display_name}")
            if child.is_dir():
                extension = "    " if index == last_index else "│   "
                _render_branch(child, depth + 1, prefix + extension, lines)

    def render_tree(path: Path) -> str:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            return f"(path not found: {resolved})"
        lines = [resolved.name]
        _render_branch(resolved, 1, "", lines)
        return "\n".join(lines)

    tree = render_tree(project_path)

    print(
        """# Stage Assessment - Deep Analysis

## Project Structure
```"""
    )
    print(tree)
    print(
        """```

## Automated Assessment

"""
    )

    # Run assess_stage via module import
    try:
        assessment = assess_stage(project_path)
        print_assessment(assessment)
    except Exception as exc:  # pragma: no cover - diagnostic path
        print(f"Could not run assess_stage.py: {exc}")

    print(
        """

## Instructions for Claude Code

Analyze this project and determine the appropriate development stage:

1. **Review Structure**: Look at directory organization, file names, patterns
2. **Assess Complexity**: Consider LOC, file count, architecture layers
3. **Identify Patterns**: Look for service layers, repositories, factories, etc.
4. **Evaluate Quality**: Are files too large? Is structure appropriate?

### Decision Criteria:

**Stage 2 (Late):**
- 15-20 files, 2000-3000 LOC
- 2-3 architectural layers
- 1-2 simple patterns
- Files might be large but not overly complex
- Good for this stage: keep patterns simple

**Stage 3 (Early):**
- 15-25 files, 3000-6000 LOC
- 3-4 architectural layers
- Multiple patterns emerging
- Might benefit from more splitting
- Good for this stage: patterns are appropriate

### Your Assessment:

Please provide:
- **Recommended Stage**: 2 (Late) or 3 (Early)
- **Confidence**: High/Medium/Low
- **Key Evidence**: What in the structure supports this?
- **Specific Recommendations**: Should files be split? Patterns needed? Any refactoring?
- **Current State**: What's working well? What needs attention?

Consider that Stage 2 → Stage 3 is gradual. If borderline, choose based on:
- **Choose Stage 2 if**: Structure works, no pain points, patterns not needed yet
- **Choose Stage 3 if**: Files are large, would benefit from patterns, architecture needed
"""
    )
