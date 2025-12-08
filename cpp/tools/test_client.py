#!/usr/bin/env python3
"""
Test client for AEGIS Static Analysis Motor.

Usage:
    python test_client.py                    # Analyze current directory
    python test_client.py /path/to/project   # Analyze specific directory
    python test_client.py --file-tree        # Get file tree only
    python test_client.py --shutdown         # Stop the server
"""

import argparse
import json
import socket
import sys
import uuid
from pathlib import Path

DEFAULT_SOCKET = "/tmp/aegis-cpp.sock"


def send_request(sock_path: str, request: dict) -> dict:
    """Send a JSON request and receive response."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(sock_path)

        # Send request (newline-delimited)
        message = json.dumps(request) + "\n"
        sock.sendall(message.encode("utf-8"))

        # Receive response
        response = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            response += chunk
            if b"\n" in response:
                break

        return json.loads(response.decode("utf-8").strip())


def analyze(sock_path: str, root: str, extensions: list[str] | None = None) -> dict:
    """Request full analysis of a directory."""
    request = {
        "id": str(uuid.uuid4()),
        "method": "analyze",
        "params": {
            "root": str(Path(root).resolve())
        }
    }
    if extensions:
        request["params"]["extensions"] = extensions

    return send_request(sock_path, request)


def file_tree(sock_path: str, root: str, extensions: list[str] | None = None) -> dict:
    """Request file tree only."""
    request = {
        "id": str(uuid.uuid4()),
        "method": "file_tree",
        "params": {
            "root": str(Path(root).resolve())
        }
    }
    if extensions:
        request["params"]["extensions"] = extensions

    return send_request(sock_path, request)


def shutdown(sock_path: str) -> dict:
    """Request server shutdown."""
    request = {
        "id": str(uuid.uuid4()),
        "method": "shutdown"
    }
    return send_request(sock_path, request)


def print_analysis(result: dict) -> None:
    """Pretty print analysis results."""
    if "error" in result:
        print(f"Error: {result['error']['message']}", file=sys.stderr)
        return

    data = result.get("result", {})

    print("=" * 60)
    print("AEGIS Static Analysis Results")
    print("=" * 60)
    print(f"Total files:      {data.get('total_files', 0)}")
    print(f"Total lines:      {data.get('total_lines', 0)}")
    print(f"Total code lines: {data.get('total_code_lines', 0)}")
    print(f"Total functions:  {data.get('total_functions', 0)}")
    print()

    files = data.get("files", [])
    if files:
        print("Files:")
        print("-" * 60)
        for f in files[:10]:  # Limit to first 10 files
            print(f"  {f['path']}")
            print(f"    Lines: {f['total_lines']} (code: {f['code_lines']}, "
                  f"blank: {f['blank_lines']}, comments: {f['comment_lines']})")

            functions = f.get("functions", [])
            if functions:
                print(f"    Functions ({len(functions)}):")
                for func in functions[:5]:  # Limit to first 5 functions
                    print(f"      - {func['name']} "
                          f"(lines {func['line_start']}-{func['line_end']}, "
                          f"CC={func['cyclomatic_complexity']})")
                if len(functions) > 5:
                    print(f"      ... and {len(functions) - 5} more")
            print()

        if len(files) > 10:
            print(f"... and {len(files) - 10} more files")


def print_file_tree(result: dict) -> None:
    """Pretty print file tree results."""
    if "error" in result:
        print(f"Error: {result['error']['message']}", file=sys.stderr)
        return

    data = result.get("result", {})
    files = data.get("files", [])

    print(f"Found {data.get('total_files', 0)} files:")
    print("-" * 40)
    for f in files:
        print(f"  {f}")


def main():
    parser = argparse.ArgumentParser(
        description="Test client for AEGIS Static Analysis Motor"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to analyze (default: current directory)"
    )
    parser.add_argument(
        "--socket", "-s",
        default=DEFAULT_SOCKET,
        help=f"Unix socket path (default: {DEFAULT_SOCKET})"
    )
    parser.add_argument(
        "--file-tree", "-t",
        action="store_true",
        help="Get file tree only (no analysis)"
    )
    parser.add_argument(
        "--shutdown",
        action="store_true",
        help="Shutdown the server"
    )
    parser.add_argument(
        "--extensions", "-e",
        nargs="+",
        help="File extensions to include (e.g., .cpp .hpp)"
    )
    parser.add_argument(
        "--raw", "-r",
        action="store_true",
        help="Print raw JSON response"
    )

    args = parser.parse_args()

    try:
        if args.shutdown:
            result = shutdown(args.socket)
            print("Server shutdown requested")
            if args.raw:
                print(json.dumps(result, indent=2))
        elif args.file_tree:
            result = file_tree(args.socket, args.path, args.extensions)
            if args.raw:
                print(json.dumps(result, indent=2))
            else:
                print_file_tree(result)
        else:
            result = analyze(args.socket, args.path, args.extensions)
            if args.raw:
                print(json.dumps(result, indent=2))
            else:
                print_analysis(result)

    except FileNotFoundError:
        print(f"Error: Socket not found at {args.socket}", file=sys.stderr)
        print("Is the server running?", file=sys.stderr)
        sys.exit(1)
    except ConnectionRefusedError:
        print(f"Error: Connection refused to {args.socket}", file=sys.stderr)
        print("Is the server running?", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON response: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
