"""
Terminal API endpoints

Provides WebSocket endpoint for remote terminal access
"""

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from code_map.terminal import PTYShell

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/terminal", tags=["terminal"])


@router.websocket("/ws")
async def terminal_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for remote terminal access

    Spawns a shell process and provides bidirectional communication using text protocol.

    Client can send:
    - Raw text for shell input
    - "__RESIZE__:cols:rows" for terminal resize

    Server sends:
    - Raw text from shell output
    """
    try:
        await websocket.accept()
        print("[TERMINAL] WebSocket connection accepted")  # DEBUG
        logger.info("Terminal WebSocket connection accepted")

        # Spawn shell process
        shell = PTYShell(cols=80, rows=24)

        try:
            shell.spawn()
            print(f"[TERMINAL] Shell spawned: PID={shell.pid}, FD={shell.master_fd}")  # DEBUG
            logger.info(f"Shell spawned successfully: PID={shell.pid}, FD={shell.master_fd}")
        except Exception as e:
            print(f"[TERMINAL] ERROR spawning shell: {e}")  # DEBUG
            logger.error(f"Failed to spawn shell: {e}", exc_info=True)
            await websocket.send_text(f"Failed to spawn shell: {str(e)}\r\n")
            await websocket.close()
            return
    except Exception as e:
        print(f"[TERMINAL] ERROR during initialization: {e}")  # DEBUG
        logger.error(f"Error during WebSocket initialization: {e}", exc_info=True)
        try:
            await websocket.close()
        except:
            pass
        return

    # Create queue for shell output
    output_queue: asyncio.Queue[str | None] = asyncio.Queue()

    # Get the event loop for thread-safe queue operations
    loop = asyncio.get_running_loop()

    # Create task for reading shell output
    async def read_output():
        """Read shell output and send to WebSocket"""
        def send_output(data: str):
            """Callback for shell output - runs in sync context"""
            try:
                # Validate loop is still running before queueing
                # This prevents errors when reconnecting after page reload
                if loop.is_running():
                    # Put data in queue (thread-safe)
                    loop.call_soon_threadsafe(output_queue.put_nowait, data)
                else:
                    logger.warning("Attempted to queue output to closed event loop")
            except Exception as e:
                logger.error(f"Error queueing output: {e}")

        await shell.read(send_output)

        # Shell exited - signal end with None
        logger.info("Shell process exited")
        try:
            if loop.is_running():
                loop.call_soon_threadsafe(output_queue.put_nowait, None)
        except Exception:
            pass

    # Start reading shell output
    print("[TERMINAL] Creating read task")  # DEBUG
    read_task = asyncio.create_task(read_output())
    print("[TERMINAL] Read task created")  # DEBUG

    try:
        # Send initial welcome message
        print("[TERMINAL] Sending welcome message")  # DEBUG
        await websocket.send_text("Connected to shell. Type commands.\r\n")
        print("[TERMINAL] Welcome message sent")  # DEBUG

        # Main event loop - handle both input and output
        while True:
            # Wait for either WebSocket message or shell output
            recv_task = asyncio.create_task(websocket.receive_text())
            pty_task = asyncio.create_task(output_queue.get())

            done, pending = await asyncio.wait(
                {recv_task, pty_task}, return_when=asyncio.FIRST_COMPLETED
            )

            # Handle shell output
            if pty_task in done:
                msg = pty_task.result()
                if msg is None:
                    # PTY closed - close WebSocket
                    if websocket.application_state == WebSocketState.CONNECTED:
                        await websocket.close()
                    break

                # Send shell output to client
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.send_text(msg)

            # Handle client input
            if recv_task in done:
                try:
                    raw = recv_task.result()

                    # Check for resize protocol
                    if raw.startswith("__RESIZE__"):
                        try:
                            _, cols, rows = raw.split(":")
                            shell.resize(int(cols), int(rows))
                            logger.debug(f"Terminal resized to {cols}x{rows}")
                        except Exception as e:
                            logger.error(f"Error parsing resize command: {e}")
                    else:
                        # Regular input - send to shell
                        shell.write(raw)

                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected")
                    break

            # Cancel pending tasks
            for task in pending:
                task.cancel()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in terminal session: {e}", exc_info=True)
    finally:
        # Cleanup - proper order to prevent race conditions
        logger.info("Cleaning up terminal session")

        # 1. Stop the shell (sets running = False, but don't wait for thread yet)
        shell.running = False

        # 2. Cancel the read task immediately
        read_task.cancel()

        try:
            await read_task
        except asyncio.CancelledError:
            pass

        # 3. Now clean up shell resources (including thread join in executor to avoid blocking)
        import concurrent.futures
        loop = asyncio.get_running_loop()
        try:
            # Run blocking shell.close() in thread pool to avoid blocking event loop
            await loop.run_in_executor(None, shell.close)
        except Exception as e:
            logger.error(f"Error during shell cleanup: {e}")

        # 4. Close WebSocket last
        try:
            if websocket.application_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception:
            pass
