"""Git helpers for timeline visualizations and Code Map features."""

import os
import subprocess  # nosec B404 - Required for invoking git CLI safely. All commands use list args (no shell injection risk).
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import re


class GitHistoryError(Exception):
    """Raised when git operations fail."""

    pass


class CommitInfo:
    """Information about a single git commit."""

    def __init__(
        self,
        hash: str,
        author: str,
        date: datetime,
        message: str,
        files_changed: List[str],
    ):
        self.hash = hash
        self.author = author
        self.date = date
        self.message = message
        self.files_changed = files_changed

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "hash": self.hash,
            "author": self.author,
            "date": self.date.isoformat(),
            "message": self.message,
            "files_changed": self.files_changed,
        }


@dataclass(slots=True)
class WorkingTreeChange:
    """Represents a single file change in the working tree vs HEAD."""

    path: str
    staged: str
    unstaged: str
    raw: str
    rename_from: Optional[str] = None

    def status_label(self) -> str:
        """Return a normalized status label (modified, added, etc.)."""

        code = self.raw.strip() or self.raw
        if code == "??":
            return "untracked"
        if code == "!!":
            return "ignored"
        tokens = set(code)
        if "U" in tokens:
            return "conflict"
        if "D" in tokens:
            return "deleted"
        if "R" in tokens:
            return "renamed"
        if "C" in tokens:
            return "copied"
        if "A" in tokens:
            return "added"
        if "M" in tokens:
            return "modified"
        return "modified"

    def summary(self) -> str:
        """Provide a short human description of the change."""

        status = self.status_label()
        if status == "ignored":
            return "Ignored file"
        if status == "untracked":
            return "New file (not committed yet)"
        if status == "renamed" and self.rename_from:
            return f"Renamed from {self.rename_from}"
        if status == "deleted":
            scope = self._format_scope()
            return f"Deleted {scope}" if scope else "Deleted locally"
        if status == "conflict":
            return "Merge conflict in progress"
        scope = self._format_scope()
        if scope:
            return f"{status.capitalize()} ({scope})"
        return status.capitalize()

    def payload(self) -> Dict[str, str]:
        """Serialize change metadata for API responses."""

        return {
            "status": self.status_label(),
            "summary": self.summary(),
        }

    def _format_scope(self) -> str:
        staged_flag = self.staged.strip()
        unstaged_flag = self.unstaged.strip()

        scopes = []
        if staged_flag and staged_flag not in {"?", "!"}:
            scopes.append("staged")
        if unstaged_flag and unstaged_flag not in {"?", "!"}:
            scopes.append("working tree")

        if not scopes:
            return ""
        if len(scopes) == 2:
            return "staged + working tree changes"
        return f"{scopes[0]} changes"


class GitHistory:
    """
    Git history analyzer for timeline visualization.

    Stage 1 MVP:
    - Parse git log with file changes
    - Filter by date range, author, file path
    - Extract commit metadata
    """

    def __init__(self, repo_path: Path, audit_run_id: Optional[int] = None):
        """
        Initialize git history analyzer.

        Args:
            repo_path: Path to git repository root
            audit_run_id: Optional audit run ID for tracking git operations
        """
        self.repo_path = Path(repo_path)
        self.audit_run_id = audit_run_id

        # Try to get audit_run_id from environment if not provided
        if self.audit_run_id is None:
            audit_run_id_str = os.getenv("ATLAS_AUDIT_RUN_ID")
            if audit_run_id_str:
                try:
                    self.audit_run_id = int(audit_run_id_str)
                except ValueError:
                    pass

        self._validate_git_repo()

    def _validate_git_repo(self) -> None:
        """Validate that repo_path is a git repository."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            raise GitHistoryError(f"Not a git repository: {self.repo_path}")

    def _run_git_command(self, args: List[str]) -> str:
        """
        Run a git command and return output.

        Args:
            args: Git command arguments (without 'git')

        Returns:
            Command output as string

        Raises:
            GitHistoryError: If command fails
        """
        # Use audit hook if run_id is available
        if self.audit_run_id is not None:
            try:
                from code_map.audit.hooks import audit_run_command

                result = audit_run_command(
                    ["git"] + args,
                    run_id=self.audit_run_id,
                    phase="explore",
                    actor="system",
                    cwd=self.repo_path,
                )
                if result.returncode != 0:
                    raise GitHistoryError(f"Git command failed: {result.stderr}")
                return result.stdout
            except ImportError:
                # Fallback if audit module not available
                pass

        # Normal execution without audit
        try:
            result = subprocess.run(  # nosec B603 - Git command constructed from controlled list args, no user input in command itself
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise GitHistoryError(f"Git command failed: {e.stderr}")

    def get_commits(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        author: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: int = 100,
    ) -> List[CommitInfo]:
        """
        Get commit history with optional filters.

        Args:
            since: Only commits after this date
            until: Only commits before this date
            author: Filter by author name/email
            file_path: Only commits that modified this file
            limit: Maximum number of commits to return

        Returns:
            List of CommitInfo objects
        """
        # Build git log command
        # Format: hash|author|date|message
        args = [
            "log",
            "--name-only",  # Show file names
            "--pretty=format:%H|%an|%ai|%s",
            f"-n{limit}",
        ]

        # Add filters
        if since:
            args.append(f"--since={since.isoformat()}")
        if until:
            args.append(f"--until={until.isoformat()}")
        if author:
            args.append(f"--author={author}")
        if file_path:
            args.append("--")
            args.append(file_path)

        output = self._run_git_command(args)

        return self._parse_commit_log(output)

    def _parse_commit_log(self, log_output: str) -> List[CommitInfo]:
        """
        Parse git log output into CommitInfo objects.

        Format:
        hash|author|date|message
        file1.py
        file2.py

        hash2|author2|date2|message2
        file3.py
        """
        commits = []
        lines = log_output.strip().split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Parse commit header
            if "|" in line:
                parts = line.split("|", 3)
                if len(parts) == 4:
                    hash_str, author, date_str, message = parts

                    # Parse date
                    try:
                        # Git date format: 2025-11-09 12:34:56 +0100
                        date = datetime.fromisoformat(date_str.rsplit(" ", 1)[0])
                    except (ValueError, IndexError):
                        date = datetime.now()

                    # Collect files changed (lines after header until next commit or end)
                    files_changed = []
                    i += 1
                    while i < len(lines) and "|" not in lines[i]:
                        file_line = lines[i].strip()
                        if file_line:
                            files_changed.append(file_line)
                        i += 1

                    commits.append(
                        CommitInfo(
                            hash=hash_str,
                            author=author,
                            date=date,
                            message=message,
                            files_changed=files_changed,
                        )
                    )
                    continue

            i += 1

        return commits

    def get_file_history(self, file_path: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get commit history for a specific file.

        Args:
            file_path: Path to file (relative to repo root)
            limit: Maximum number of commits

        Returns:
            Dictionary with file_path, commits, and total_changes
        """
        commits = self.get_commits(file_path=file_path, limit=limit)

        return {
            "file_path": file_path,
            "commits": [c.to_dict() for c in commits],
            "total_changes": len(commits),
        }

    def get_commit_details(self, commit_hash: str) -> Optional[CommitInfo]:
        """
        Get detailed information about a specific commit.

        Args:
            commit_hash: Git commit hash (full or short)

        Returns:
            CommitInfo object or None if commit not found
        """
        try:
            commits = self.get_commits(limit=1)
            # Get specific commit
            args = ["show", "--name-only", "--pretty=format:%H|%an|%ai|%s", commit_hash]
            output = self._run_git_command(args)
            commits = self._parse_commit_log(output)
            return commits[0] if commits else None
        except GitHistoryError:
            return None

    def get_all_files(self) -> List[str]:
        """
        Get list of all files currently tracked by git.

        Returns:
            List of file paths (relative to repo root)
        """
        try:
            output = self._run_git_command(["ls-files"])
            return [line.strip() for line in output.split("\n") if line.strip()]
        except GitHistoryError:
            return []

    def get_timeline_matrix(
        self, limit: int = 50, file_pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get timeline data structured for DAW-style visualization.

        Returns a matrix where:
        - Rows: Files
        - Columns: Commits (chronological)
        - Cells: True if file changed in that commit

        Args:
            limit: Maximum number of commits
            file_pattern: Optional regex pattern to filter files

        Returns:
            Dictionary with:
            - commits: List of commit metadata
            - files: List of file paths
            - matrix: 2D array of booleans (file_index, commit_index)
        """
        commits = self.get_commits(limit=limit)

        # Collect all unique files
        all_files: Set[str] = set()
        for commit in commits:
            all_files.update(commit.files_changed)

        # Filter files by pattern if provided
        if file_pattern:
            pattern = re.compile(file_pattern)
            all_files = {f for f in all_files if pattern.search(f)}

        files_list = sorted(all_files)

        # Build matrix
        matrix = []
        for file_path in files_list:
            row = []
            for commit in commits:
                row.append(file_path in commit.files_changed)
            matrix.append(row)

        return {
            "commits": [c.to_dict() for c in commits],
            "files": files_list,
            "matrix": matrix,
            "total_files": len(files_list),
            "total_commits": len(commits),
        }

    def get_working_tree_changes(self) -> List[WorkingTreeChange]:
        """Return a list of files changed since the last commit (HEAD)."""

        output = self._run_git_command(["status", "--porcelain=1", "-z"])
        if not output:
            return []

        tokens = output.split("\0")
        changes: List[WorkingTreeChange] = []
        idx = 0

        while idx < len(tokens):
            entry = tokens[idx]
            idx += 1
            if not entry:
                continue

            status = entry[:2]
            if status.strip() == "!!":
                # Ignored files are not relevant for change tracking
                continue

            path_fragment = entry[3:] if len(entry) > 3 else ""
            rename_from: Optional[str] = None

            if any(flag in {"R", "C"} for flag in status):
                rename_from = path_fragment
                if idx < len(tokens):
                    path_fragment = tokens[idx]
                    idx += 1

            if not path_fragment:
                continue

            normalized_path = Path(path_fragment).as_posix()
            normalized_rename = Path(rename_from).as_posix() if rename_from else None

            staged_flag = status[0] if len(status) >= 1 else " "
            unstaged_flag = status[1] if len(status) >= 2 else " "

            change = WorkingTreeChange(
                path=normalized_path,
                staged=staged_flag,
                unstaged=unstaged_flag,
                raw=status,
                rename_from=normalized_rename,
            )

            if change.status_label() == "ignored":
                continue

            changes.append(change)

        return changes

    def get_working_tree_change_map(self) -> Dict[str, WorkingTreeChange]:
        """Return working tree changes keyed by relative path."""

        return {change.path: change for change in self.get_working_tree_changes()}

    def get_working_tree_change_for_path(
        self, file_path: str
    ) -> Optional[WorkingTreeChange]:
        """Fetch working tree change info for a specific file."""

        normalized = Path(file_path).as_posix()
        return self.get_working_tree_change_map().get(normalized)

    def get_working_tree_diff(self, file_path: str) -> str:
        """Return diff between working tree and HEAD for the given file."""

        normalized = Path(file_path).as_posix()

        # Use audit hook if run_id is available
        if self.audit_run_id is not None:
            try:
                from code_map.audit.hooks import audit_run_command

                result = audit_run_command(
                    ["git", "diff", "HEAD", "--", normalized],
                    run_id=self.audit_run_id,
                    phase="explore",
                    actor="system",
                    cwd=self.repo_path,
                )
                if result.returncode not in {0, 1}:
                    raise GitHistoryError(result.stderr.strip() or "git diff failed")
                return result.stdout
            except ImportError:
                # Fallback if audit module not available
                pass

        # Normal execution without audit
        try:
            result = subprocess.run(  # nosec B603 - arguments are controlled
                ["git", "diff", "HEAD", "--", normalized],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
            raise GitHistoryError(f"Git diff failed: {exc.stderr}") from exc

        if result.returncode not in {0, 1}:
            raise GitHistoryError(result.stderr.strip() or "git diff failed")

        return result.stdout

    def get_file_diff(self, commit_hash: str, file_path: str) -> Optional[str]:
        """
        Get the diff for a specific file in a commit.

        Args:
            commit_hash: Git commit hash
            file_path: Path to file (relative to repo root)

        Returns:
            Diff string or None if file not in commit
        """
        try:
            # Get diff for specific file in this commit
            output = self._run_git_command(["show", f"{commit_hash}", "--", file_path])
            return output
        except GitHistoryError:
            return None
