#!/usr/bin/env python3
"""
Agent Template with Audit Integration

Copy this template and adapt it for your Claude Code agent workflows.
This demonstrates best practices for integrating with the ATLAS audit system.

Usage:
    1. Copy this file to your agent script
    2. Customize the workflow phases
    3. Add your actual implementation logic
    4. Run and view results in the dashboard
"""

import os
import sys
import traceback
from pathlib import Path

# Add ATLAS to Python path (adjust if needed)
ATLAS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ATLAS_ROOT))

from .claude.hooks.audit_bridge import (
    start_audit_session,
    end_audit_session,
    log_phase_start,
    log_phase_end,
    log_thought,
    log_command,
    log_file_change,
    log_git_operation,
    log_error,
    audit_context,
    get_current_run_id,
)


def main():
    """
    Main agent workflow with audit integration.
    """
    # ==================================================================
    # PHASE 0: Initialize Audit Session
    # ==================================================================
    run_id = start_audit_session(
        name="Example Agent Workflow",  # <- Customize this
        notes="Template demonstrating audit integration"  # <- Customize this
    )

    if run_id is None:
        print("⚠️  Audit system unavailable, continuing without logging")
        # Your workflow can still run, just without audit
        return

    # Store in environment for easy access across functions
    os.environ["ATLAS_AUDIT_RUN_ID"] = str(run_id)

    print(f"📋 Started audit session {run_id}")
    print(f"🌐 View at: http://localhost:8010")

    try:
        # ==============================================================
        # PHASE 1: PLAN - Analysis and Design
        # ==============================================================
        log_phase_start(run_id, "plan", "Analyzing requirements and codebase")

        with audit_context(run_id, "Analyze codebase structure", phase="plan"):
            log_thought(
                run_id,
                "Examining project structure and dependencies",
                phase="plan"
            )
            # Your analysis logic here
            # Example:
            # - Read files
            # - Analyze code
            # - Identify issues
            # - Plan approach

            log_thought(
                run_id,
                "Identified 3 files that need updates: auth.py, config.py, tests.py",
                phase="plan"
            )

        log_phase_end(
            run_id,
            "plan",
            success=True,
            summary="Analysis complete, ready to implement"
        )

        # ==============================================================
        # PHASE 2: APPLY - Implementation
        # ==============================================================
        log_phase_start(run_id, "apply", "Implementing planned changes")

        # Example: Create a new file
        with audit_context(run_id, "Create configuration file", phase="apply"):
            # Your file creation logic here
            # Example:
            # with open("config.yaml", "w") as f:
            #     f.write("...")

            log_file_change(
                run_id,
                "config.yaml",
                "Created configuration file with default settings",
                change_type="create",
                phase="apply"
            )

        # Example: Modify existing file
        with audit_context(run_id, "Update authentication logic", phase="apply"):
            # Your modification logic here
            # Example:
            # with open("auth.py", "r+") as f:
            #     content = f.read()
            #     new_content = content.replace("old", "new")
            #     f.seek(0)
            #     f.write(new_content)

            log_file_change(
                run_id,
                "src/auth.py",
                "Fixed token validation race condition",
                change_type="modify",
                phase="apply"
            )

        # Example: Git commit
        log_git_operation(
            run_id,
            operation="commit",
            description="Add configuration and fix auth bug",
            phase="apply",
            payload={"files_changed": 2, "lines_added": 45, "lines_removed": 12}
        )

        log_phase_end(
            run_id,
            "apply",
            success=True,
            summary="All changes implemented successfully"
        )

        # ==============================================================
        # PHASE 3: VALIDATE - Testing and Verification
        # ==============================================================
        log_phase_start(run_id, "validate", "Running tests and validation")

        # Example: Run tests
        with audit_context(run_id, "Run test suite", phase="validate"):
            result = log_command(
                run_id,
                "pytest tests/ -v",  # <- Customize this
                phase="validate",
                timeout=60
            )

            if result and result.returncode == 0:
                log_thought(
                    run_id,
                    "✅ All tests passed successfully",
                    phase="validate"
                )
            else:
                log_thought(
                    run_id,
                    "❌ Some tests failed, investigating...",
                    phase="validate"
                )

        # Example: Run linters
        with audit_context(run_id, "Run code quality checks", phase="validate"):
            log_command(run_id, "ruff check .", phase="validate")
            log_command(run_id, "mypy src/", phase="validate")

        log_phase_end(
            run_id,
            "validate",
            success=True,
            summary="All tests and quality checks passed"
        )

        # ==============================================================
        # PHASE 4: SUCCESS - Wrap Up
        # ==============================================================
        end_audit_session(
            run_id,
            success=True,
            summary="Workflow completed successfully: configured, implemented, and validated"
        )

        print(f"✅ Workflow completed successfully!")
        print(f"📊 View full audit trail at: http://localhost:8010")

    except Exception as e:
        # ==============================================================
        # ERROR HANDLING
        # ==============================================================
        print(f"❌ Error occurred: {e}")

        log_error(
            run_id,
            error_message=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc()
        )

        end_audit_session(
            run_id,
            success=False,
            summary=f"Workflow failed with error: {type(e).__name__}: {e}"
        )

        raise  # Re-raise to preserve stack trace


# ==================================================================
# Helper Functions (Optional)
# ==================================================================

def analyze_codebase(run_id: int):
    """
    Example helper function with audit integration.
    """
    with audit_context(run_id, "Deep codebase analysis", phase="plan"):
        log_thought(run_id, "Starting deep analysis...", phase="plan")

        # Your analysis logic here
        result = {"files": 42, "functions": 156, "classes": 23}

        log_thought(
            run_id,
            f"Analysis complete: {result['files']} files, {result['functions']} functions",
            phase="plan"
        )

        return result


def run_implementation(run_id: int, files_to_change: list):
    """
    Example helper function for implementing changes.
    """
    log_phase_start(run_id, "apply", f"Modifying {len(files_to_change)} files")

    for file_path in files_to_change:
        with audit_context(run_id, f"Update {file_path}", phase="apply"):
            # Your implementation logic here
            # Example: modify file, run formatters, etc.

            log_file_change(
                run_id,
                file_path,
                "Updated according to plan",
                change_type="modify",
                phase="apply"
            )

    log_phase_end(run_id, "apply", success=True)


# ==================================================================
# Entry Point
# ==================================================================

if __name__ == "__main__":
    main()
