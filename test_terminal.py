#!/usr/bin/env python3
"""
Quick test for terminal module
"""
import asyncio
from code_map.terminal import PTYShell


async def test_terminal():
    """Test basic terminal functionality"""
    print("🧪 Testing PTY Shell...")

    # Create shell
    shell = PTYShell(cols=80, rows=24)
    print("✓ Shell created")

    # Spawn process
    try:
        shell.spawn()
        print("✓ Shell spawned")
    except Exception as e:
        print(f"✗ Failed to spawn shell: {e}")
        return

    # Write a simple command
    shell.write("echo 'Hello from PTY Shell'\n")
    print("✓ Command sent")

    # Read output (limited time)
    output_received = []

    def collect_output(data: str):
        output_received.append(data)

    # Read for 2 seconds
    try:
        await asyncio.wait_for(
            shell.read(collect_output),
            timeout=2.0
        )
    except asyncio.TimeoutError:
        pass

    # Close shell
    shell.close()
    print("✓ Shell closed")

    # Show output
    all_output = "".join(output_received)
    if "Hello from PTY Shell" in all_output:
        print("✓ Output contains expected text")
    else:
        print("✗ Output did not contain expected text")

    print("\n📊 Output received:")
    print(repr(all_output[:200]))


if __name__ == "__main__":
    asyncio.run(test_terminal())
