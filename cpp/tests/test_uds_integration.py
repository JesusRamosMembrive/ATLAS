#!/usr/bin/env python3
"""Test UDS server integration with Python client."""

import socket
import json
import subprocess
import time
import uuid
import os
import sys

SOCKET_PATH = "/tmp/test-aegis-integration.sock"
EXECUTABLE = "./static_analysis_motor"
FIXTURES_DIR = "../tests/fixtures"


def send_request(sock: socket.socket, method: str, params: dict) -> dict:
    """Send a JSON-RPC style request and get response."""
    request = {"id": str(uuid.uuid4()), "method": method, "params": params}
    sock.sendall((json.dumps(request) + "\n").encode())

    # Read response
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk

    if not data:
        return {"error": "No response received"}

    return json.loads(data.decode().strip())


def test_server():
    """Test the UDS server."""
    # Clean up old socket
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    # Start server
    print("Starting server...")
    server_proc = subprocess.Popen(
        [EXECUTABLE, "--socket", SOCKET_PATH],
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.abspath(__file__)) + "/../build",
    )

    # Wait for server to start
    time.sleep(1)

    if server_proc.poll() is not None:
        stderr = server_proc.stderr.read().decode()
        print(f"Server failed to start: {stderr}")
        return False

    print(f"Server started (PID: {server_proc.pid})")

    try:
        # Connect to server
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        print("Connected to server")

        # Test 1: Analyze
        print("\n=== Test 1: analyze ===")
        response = send_request(
            sock, "analyze", {"root": FIXTURES_DIR, "extensions": [".py"]}
        )

        if "error" in response:
            print(f"Error: {response['error']}")
            return False

        result = response.get("result", {})
        print(f"Files analyzed: {result.get('summary', {}).get('files_analyzed', 0)}")
        print(f"Clones found: {len(result.get('clones', []))}")

        # Check performance metrics
        perf = result.get("performance", {})
        if perf.get("loc_per_second", 0) > 0:
            print(f"Performance: {perf.get('loc_per_second', 0):.0f} LOC/sec")

        # Test 2: File tree
        print("\n=== Test 2: file_tree ===")
        response = send_request(
            sock, "file_tree", {"root": FIXTURES_DIR, "extensions": [".py"]}
        )

        if "error" in response:
            print(f"Error: {response['error']}")
            return False

        result = response.get("result", {})
        print(f"Files found: {result.get('count', 0)}")

        # Test 3: get_hotspots
        print("\n=== Test 3: get_hotspots ===")
        response = send_request(
            sock,
            "get_hotspots",
            {"root": FIXTURES_DIR, "extensions": [".py"], "limit": 5},
        )

        if "error" in response:
            print(f"Error: {response['error']}")
            return False

        result = response.get("result", {})
        print(f"Top hotspots: {result.get('count', 0)}")
        for hotspot in result.get("hotspots", [])[:3]:
            print(
                f"  - {os.path.basename(hotspot.get('file', 'unknown'))}: "
                f"score={hotspot.get('duplication_score', 0):.2f}, "
                f"clones={hotspot.get('clone_count', 0)}"
            )

        # Test 4: get_file_clones
        print("\n=== Test 4: get_file_clones ===")
        response = send_request(
            sock,
            "get_file_clones",
            {"root": FIXTURES_DIR, "file": "example_a.py", "extensions": [".py"]},
        )

        if "error" in response:
            print(f"Error: {response['error']}")
            return False

        result = response.get("result", {})
        print(f"Clones involving 'example_a.py': {result.get('count', 0)}")

        # Test 5: compare_files
        print("\n=== Test 5: compare_files ===")
        response = send_request(
            sock,
            "compare_files",
            {
                "file1": FIXTURES_DIR + "/example_a.py",
                "file2": FIXTURES_DIR + "/example_b.py",
            },
        )

        if "error" in response:
            print(f"Error: {response['error']}")
            return False

        result = response.get("result", {})
        print(f"Comparison clones: {len(result.get('clones', []))}")

        # Test 6: Shutdown
        print("\n=== Test 6: shutdown ===")
        response = send_request(sock, "shutdown", {})

        if "error" in response:
            print(f"Error: {response['error']}")
            return False

        result = response.get("result", {})
        print(f"Status: {result.get('status', 'unknown')}")

        sock.close()

        # Wait for server to stop
        time.sleep(1)
        if server_proc.poll() is None:
            server_proc.terminate()
            server_proc.wait(timeout=5)

        print("\n=== All 6 tests passed! ===")
        return True

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        server_proc.terminate()
        server_proc.wait(timeout=5)
        return False

    finally:
        # Cleanup
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)


if __name__ == "__main__":
    success = test_server()
    sys.exit(0 if success else 1)
