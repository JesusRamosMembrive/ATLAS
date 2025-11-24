"""
Terminal API endpoints

Provides WebSocket endpoint for remote terminal access
"""

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from code_map.terminal import PTYShell

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/terminal", tags=["terminal"])


@router.websocket("/ws")
async def terminal_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for remote terminal access

    Spawns a shell process and provides bidirectional communication:
    - Receives keyboard input from client
    - Sends shell output to client
    - Handles terminal resize events

    Client messages format:
    - {"type": "input", "data": "command text"}
    - {"type": "resize", "cols": 80, "rows": 24}

    Server messages format:
    - {"type": "output", "data": "shell output"}
    - {"type": "exit", "code": 0}
    - {"type": "error", "message": "error details"}
    """
    await websocket.accept()
    logger.info("Terminal WebSocket connection accepted")

    # Spawn shell process
    shell = PTYShell(cols=80, rows=24)

    try:
        shell.spawn()
    except Exception as e:
        logger.error(f"Failed to spawn shell: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to spawn shell: {str(e)}"
        })
        await websocket.close()
        return

    # Create task for reading shell output
    async def read_output():
        """Read shell output and send to WebSocket"""
        def send_output(data: str):
            """Callback for shell output"""
            try:
                # Send output to client
                asyncio.create_task(websocket.send_json({
                    "type": "output",
                    "data": data
                }))
            except Exception as e:
                logger.error(f"Error sending output: {e}")

        await shell.read(send_output)

        # Shell exited
        logger.info("Shell process exited")
        try:
            await websocket.send_json({
                "type": "exit",
                "code": 0
            })
        except Exception:
            pass

    # Start reading shell output
    read_task = asyncio.create_task(read_output())

    try:
        # Handle incoming WebSocket messages
        while True:
            try:
                # Receive message from client
                message = await websocket.receive_json()
                msg_type = message.get("type")

                if msg_type == "input":
                    # User keyboard input
                    data = message.get("data", "")
                    shell.write(data)

                elif msg_type == "resize":
                    # Terminal resize
                    cols = message.get("cols", 80)
                    rows = message.get("rows", 24)
                    shell.resize(cols, rows)

                else:
                    logger.warning(f"Unknown message type: {msg_type}")

            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
                break

            except Exception as e:
                logger.error(f"Error handling message: {e}")
                break

    finally:
        # Cleanup
        logger.info("Cleaning up terminal session")
        shell.close()
        read_task.cancel()

        try:
            await read_task
        except asyncio.CancelledError:
            pass

        try:
            await websocket.close()
        except Exception:
            pass
