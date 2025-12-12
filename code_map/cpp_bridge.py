"""
Python bridge for AEGIS C++ Static Analysis Motor.

This module provides a Python interface to communicate with the C++ analysis
server via Unix Domain Sockets.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default socket path - use system temp directory for portability
DEFAULT_SOCKET_PATH = os.path.join(tempfile.gettempdir(), "aegis-cpp.sock")

# Path to the C++ executable (relative to project root)
CPP_EXECUTABLE = "cpp/build/static_analysis_motor"


@dataclass
class FunctionMetrics:
    """Metrics for a single function."""

    name: str
    qualified_name: str
    line_start: int
    line_end: int
    length: int
    cyclomatic_complexity: int


@dataclass
class FileMetrics:
    """Metrics for a single file."""

    path: str
    total_lines: int
    code_lines: int
    blank_lines: int
    comment_lines: int
    functions: list[FunctionMetrics] = field(default_factory=list)


@dataclass
class ProjectMetrics:
    """Aggregated metrics for a project."""

    total_files: int
    total_lines: int
    total_code_lines: int
    total_functions: int
    files: list[FileMetrics] = field(default_factory=list)


class CppBridgeError(Exception):
    """Exception raised when communication with C++ motor fails."""

    pass


class CppBridge:
    """
    Bridge to communicate with the C++ Static Analysis Motor.

    The motor can run in two modes:
    1. Server mode: Long-running process accepting requests via Unix socket
    2. Standalone mode: One-shot analysis via command line

    Example usage:
        >>> bridge = CppBridge()
        >>> bridge.start_server()
        >>> metrics = bridge.analyze("/path/to/project")
        >>> bridge.stop_server()

    Or standalone mode:
        >>> bridge = CppBridge()
        >>> metrics = bridge.analyze_standalone("/path/to/project")
    """

    def __init__(
        self,
        socket_path: str = DEFAULT_SOCKET_PATH,
        executable_path: Optional[Path] = None,
    ):
        """
        Initialize the C++ bridge.

        Args:
            socket_path: Path for the Unix domain socket
            executable_path: Path to the C++ executable. If None, uses default.
        """
        self.socket_path = socket_path
        self._server_process: Optional[subprocess.Popen[bytes]] = None
        self._socket: Optional[socket.socket] = None

        if executable_path:
            self.executable_path = executable_path
        else:
            # Find executable relative to this file
            project_root = Path(__file__).parent.parent
            self.executable_path = project_root / CPP_EXECUTABLE

    def is_available(self) -> bool:
        """Check if the C++ motor executable is available."""
        return self.executable_path.exists() and os.access(
            self.executable_path, os.X_OK
        )

    def start_server(self, timeout: float = 5.0) -> None:
        """
        Start the C++ analysis server.

        Args:
            timeout: Maximum time to wait for server to start

        Raises:
            CppBridgeError: If server fails to start
        """
        if self._server_process is not None:
            logger.warning("Server already running")
            return

        if not self.is_available():
            raise CppBridgeError(
                f"C++ motor not found at {self.executable_path}. "
                "Build it with: cd cpp && cmake -B build && cmake --build build"
            )

        # Remove existing socket file
        socket_file = Path(self.socket_path)
        if socket_file.exists():
            socket_file.unlink()

        # Start server process
        cmd = [str(self.executable_path), "--socket", self.socket_path]
        logger.info(f"Starting C++ motor: {' '.join(cmd)}")

        self._server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for socket to be available
        start_time = time.time()
        while time.time() - start_time < timeout:
            if socket_file.exists():
                logger.info("C++ motor started successfully")
                return
            time.sleep(0.1)

            # Check if process died
            if self._server_process.poll() is not None:
                stdout, stderr = self._server_process.communicate()
                raise CppBridgeError(
                    f"C++ motor exited unexpectedly:\n"
                    f"stdout: {stdout.decode()}\n"
                    f"stderr: {stderr.decode()}"
                )

        raise CppBridgeError("Timeout waiting for C++ motor to start")

    def stop_server(self) -> None:
        """Stop the C++ analysis server."""
        if self._server_process is None:
            return

        try:
            # Send shutdown request
            self._send_request({"id": str(uuid.uuid4()), "method": "shutdown"})
        except Exception:
            pass  # Ignore errors during shutdown

        # Close socket
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        # Terminate process
        try:
            self._server_process.terminate()
            self._server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._server_process.kill()
            self._server_process.wait()
        finally:
            self._server_process = None

        # Clean up socket file
        socket_file = Path(self.socket_path)
        if socket_file.exists():
            try:
                socket_file.unlink()
            except Exception:
                pass

        logger.info("C++ motor stopped")

    def _connect(self) -> socket.socket:
        """Get or create socket connection."""
        if self._socket is None:
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.connect(self.socket_path)
        return self._socket

    def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Send a request to the server and receive response.

        Args:
            request: Request dictionary

        Returns:
            Response dictionary

        Raises:
            CppBridgeError: If communication fails
        """
        sock = self._connect()

        # Send request (newline-delimited JSON)
        message = json.dumps(request) + "\n"
        sock.sendall(message.encode("utf-8"))

        # Receive response
        buffer = b""
        while b"\n" not in buffer:
            chunk = sock.recv(65536)
            if not chunk:
                raise CppBridgeError("Connection closed by server")
            buffer += chunk

        # Parse response
        response_str = buffer.split(b"\n")[0].decode("utf-8")
        try:
            response = json.loads(response_str)
        except json.JSONDecodeError as e:
            raise CppBridgeError(f"Invalid JSON response: {e}")

        if "error" in response:
            raise CppBridgeError(response["error"].get("message", "Unknown error"))

        return response

    def analyze(
        self,
        root: str | Path,
        extensions: Optional[list[str]] = None,
    ) -> ProjectMetrics:
        """
        Analyze a project using the running server.

        Args:
            root: Root directory to analyze
            extensions: File extensions to include (e.g., [".cpp", ".hpp"])

        Returns:
            Project metrics

        Raises:
            CppBridgeError: If analysis fails
        """
        request: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "method": "analyze",
            "params": {"root": str(root)},
        }

        if extensions:
            request["params"]["extensions"] = extensions

        response = self._send_request(request)
        return self._parse_project_metrics(response.get("result", {}))

    def get_file_tree(
        self,
        root: str | Path,
        extensions: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Get file tree from the running server.

        Args:
            root: Root directory to scan
            extensions: File extensions to include

        Returns:
            List of file paths
        """
        request: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "method": "file_tree",
            "params": {"root": str(root)},
        }

        if extensions:
            request["params"]["extensions"] = extensions

        response = self._send_request(request)
        result = response.get("result", {})
        return result.get("files", [])

    def analyze_standalone(
        self,
        root: str | Path,
        extensions: Optional[list[str]] = None,
    ) -> ProjectMetrics:
        """
        Run one-shot analysis without starting a server.

        Args:
            root: Root directory to analyze
            extensions: File extensions to include

        Returns:
            Project metrics

        Raises:
            CppBridgeError: If analysis fails
        """
        if not self.is_available():
            raise CppBridgeError(
                f"C++ motor not found at {self.executable_path}. "
                "Build it with: cd cpp && cmake -B build && cmake --build build"
            )

        cmd = [str(self.executable_path), "--analyze", str(root)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,  # 5 minute timeout
            )
        except subprocess.TimeoutExpired:
            raise CppBridgeError("Analysis timed out")

        if result.returncode != 0:
            raise CppBridgeError(f"Analysis failed: {result.stderr}")

        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise CppBridgeError(f"Invalid JSON output: {e}")

        return self._parse_project_metrics(response.get("result", {}))

    def _parse_project_metrics(self, data: dict[str, Any]) -> ProjectMetrics:
        """Parse project metrics from JSON response."""
        files = []
        for file_data in data.get("files", []):
            functions = [
                FunctionMetrics(
                    name=f.get("name", ""),
                    qualified_name=f.get("qualified_name", ""),
                    line_start=f.get("line_start", 0),
                    line_end=f.get("line_end", 0),
                    length=f.get("length", 0),
                    cyclomatic_complexity=f.get("cyclomatic_complexity", 1),
                )
                for f in file_data.get("functions", [])
            ]

            files.append(
                FileMetrics(
                    path=file_data.get("path", ""),
                    total_lines=file_data.get("total_lines", 0),
                    code_lines=file_data.get("code_lines", 0),
                    blank_lines=file_data.get("blank_lines", 0),
                    comment_lines=file_data.get("comment_lines", 0),
                    functions=functions,
                )
            )

        return ProjectMetrics(
            total_files=data.get("total_files", 0),
            total_lines=data.get("total_lines", 0),
            total_code_lines=data.get("total_code_lines", 0),
            total_functions=data.get("total_functions", 0),
            files=files,
        )

    def __enter__(self) -> "CppBridge":
        """Context manager entry."""
        self.start_server()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.stop_server()
