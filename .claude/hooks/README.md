# Agent Audit Bridge

This directory contains the **Agent Audit Bridge** - a simple Python interface that allows Claude Code agents (and other AI agents) to automatically log their work to the ATLAS Agent Monitoring Dashboard.

## Quick Start

### 1. Start an Audit Session

```python
from audit_bridge import start_audit_session, end_audit_session, log_thought

# Start tracking your work
run_id = start_audit_session(
    name="Fix authentication bug",
    notes="User reported login issues with expired tokens"
)
```

### 2. Log Your Work

```python
# Log your analysis and planning
log_thought(run_id, "The token refresh logic has a race condition", phase="plan")

# Log commands you run
from audit_bridge import log_command
result = log_command(run_id, "pytest tests/test_auth.py -v", phase="validate")

# Log file changes
from audit_bridge import log_file_change
log_file_change(
    run_id,
    "src/auth/token.py",
    "Fixed race condition in token refresh",
    change_type="modify"
)
```

### 3. End the Session

```python
# When done
end_audit_session(
    run_id,
    success=True,
    summary="Fixed token refresh race condition, all tests passing"
)
```

## Available Functions

### Session Management

- **`start_audit_session(name, root_path=None, notes=None, actor="claude_code")`**
  - Starts a new audit session
  - Returns `run_id` to use for all subsequent calls
  - Creates a session entry in the dashboard

- **`end_audit_session(run_id, success=True, summary=None, actor="claude_code")`**
  - Ends the audit session
  - Marks run as closed in the dashboard
  - Logs final summary

### Event Logging

- **`log_thought(run_id, thought, phase="plan", actor="claude_code")`**
  - Log analysis, reasoning, or design decisions
  - Appears as "thought" events in the timeline

- **`log_command(run_id, command, phase="apply", actor="claude_code", timeout=None)`**
  - Runs and logs a shell command
  - Captures stdout/stderr automatically
  - Returns `CompletedProcess` result

- **`log_file_change(run_id, file_path, description, change_type="modify", phase="apply")`**
  - Log file creations, modifications, or deletions
  - `change_type`: "create", "modify", or "delete"

- **`log_git_operation(run_id, operation, description, phase="apply", payload=None)`**
  - Log git operations (commit, push, branch, merge)
  - Optional payload for commit hash, branch name, etc.

- **`log_error(run_id, error_message, error_type=None, phase=None, traceback=None)`**
  - Log errors and exceptions
  - Include full traceback for debugging

- **`log_phase_start(run_id, phase_name, description=None)`** / **`log_phase_end(run_id, phase_name, success=True, summary=None)`**
  - Mark workflow phase boundaries
  - Phases: "plan", "apply", "validate", "explore"

### Context Manager

- **`audit_context(run_id, title, phase="apply", actor="claude_code", detail=None)`**
  - Wraps a block of work with automatic start/end events
  - Captures exceptions automatically

```python
from audit_bridge import audit_context

with audit_context(run_id, "Analyze authentication flow", phase="plan"):
    # Your work here
    analyze_code()
    review_dependencies()
# Automatically logs start, end, duration, and any errors
```

### Helpers

- **`get_current_run_id()`**
  - Gets run ID from `ATLAS_AUDIT_RUN_ID` environment variable
  - Useful for sharing run ID across functions

## Workflow Phases

The audit system organizes work into phases:

- **`plan`** - Analysis, design, and planning work
- **`apply`** - Implementation and code changes
- **`validate`** - Testing, verification, and validation
- **`explore`** - Investigation and exploration

Use these consistently to make the timeline view more useful.

## Integration with Claude Code

### Option 1: Manual Instrumentation

Add audit calls directly to your agent code:

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/path/to/ATLAS')
from .claude.hooks.audit_bridge import *

def my_agent_task():
    run_id = start_audit_session("Implement feature X")

    try:
        log_phase_start(run_id, "plan")
        # planning work...
        log_phase_end(run_id, "plan", success=True)

        log_phase_start(run_id, "apply")
        # implementation work...
        log_phase_end(run_id, "apply", success=True)

        end_audit_session(run_id, success=True)
    except Exception as e:
        log_error(run_id, str(e), type(e).__name__)
        end_audit_session(run_id, success=False)
        raise
```

### Option 2: Environment Variable

Set `ATLAS_AUDIT_RUN_ID` once and use `get_current_run_id()`:

```python
import os
from .claude.hooks.audit_bridge import *

# In your agent startup
run_id = start_audit_session("My work session")
os.environ["ATLAS_AUDIT_RUN_ID"] = str(run_id)

# Later, in any function
def some_function():
    run_id = get_current_run_id()
    log_thought(run_id, "Some analysis...")
```

## Viewing Your Work

Once you start logging, your work appears in real-time on the **Agent Monitoring Dashboard**:

1. **Start the ATLAS backend**:
   ```bash
   cd /path/to/ATLAS
   python -m code_map.cli run --root .
   ```

2. **Open the dashboard**:
   ```
   http://localhost:8010
   ```

3. **Navigate to Audit Trail**:
   - Click "Audit Trail" in the sidebar
   - Select your session from the list
   - See real-time events as they happen

## Event Types

The bridge emits these event types:

- `session` - Session start/end
- `thought` - Analysis and reasoning
- `command` - Shell command execution
- `command_result` - Command output and result
- `file_change` - File create/modify/delete
- `git` - Git operations
- `phase` - Phase start/end
- `error` - Errors and exceptions
- `operation` - Generic tracked operations

## Example: Complete Workflow

See `audit_bridge.py` function `example_usage()` for a complete example, or run:

```bash
python .claude/hooks/audit_bridge.py
```

This runs a demonstration that creates a session, logs various events, and displays them in the dashboard.

## Graceful Degradation

The bridge gracefully handles cases where the audit system is unavailable:

- If `code_map.audit` cannot be imported, all functions become no-ops
- `start_audit_session()` returns `None` instead of `run_id`
- All other functions check for `None` run_id and skip logging
- Your agent code continues working normally

This means you can use the bridge even in environments where ATLAS isn't available.

## Architecture

```
.claude/hooks/audit_bridge.py   (simplified interface for agents)
        ↓
code_map/audit/hooks.py          (core audit hooks system)
        ↓
code_map/audit/storage.py        (SQLite database storage)
        ↓
code_map/api/audit.py            (REST API + SSE endpoint)
        ↓
frontend/AuditSessionsView.tsx   (Real-time dashboard UI)
```

## Next Steps

**Fase 2** will add:
- Terminal emulator integration (xterm.js) to display command output live
- Timeline view (Gantt chart) to visualize phase durations
- 3-column dashboard layout: terminal | timeline | event stream

**Fase 3** will add:
- Real-time file diffs as agents make changes
- Syntax highlighting for code changes
- File tree navigation

**Fase 4** will add:
- Export audit sessions (JSON, Markdown, HTML)
- Performance metrics (durations, token usage, costs)
- Analytics dashboard
