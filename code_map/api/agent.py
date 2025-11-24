"""
API endpoints for agent control

Proporciona endpoints REST y SSE para:
- Enviar tareas al agente
- Recibir respuestas en streaming
- Controlar flujo de ejecución (pause, resume, cancel)
"""

import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from code_map.agent import get_agent_controller, AgentTask


router = APIRouter(prefix="/agent", tags=["agent"])


# === Schemas ===

class TaskCreateRequest(BaseModel):
    """Request para crear una nueva tarea"""
    prompt: str = Field(..., description="Prompt/tarea para el agente")
    context: Optional[dict] = Field(default=None, description="Contexto adicional")
    run_id: Optional[int] = Field(default=None, description="ID de audit run asociado")
    model: str = Field(default="claude-3-5-sonnet-20241022", description="Modelo a usar")
    max_tokens: int = Field(default=4096, ge=1, le=8192, description="Tokens máximos")
    system_prompt: Optional[str] = Field(default=None, description="System prompt")


class TaskCreateResponse(BaseModel):
    """Response al crear una tarea"""
    task_id: str
    status: str
    message: str


class ControlRequest(BaseModel):
    """Request para controlar una tarea (pause/resume/cancel)"""
    task_id: str


class ControlResponse(BaseModel):
    """Response de operación de control"""
    success: bool
    task_id: str
    message: str


# === Endpoints ===

@router.get("/status")
async def get_agent_status():
    """
    Obtiene el estado del controlador de agente

    Returns:
        Estado de configuración y tareas activas
    """
    controller = get_agent_controller()
    return controller.get_status()


@router.post("/tasks", response_model=TaskCreateResponse)
async def create_task(request: TaskCreateRequest):
    """
    Crea una nueva tarea para el agente

    La tarea se ejecutará de forma asíncrona. Use el endpoint /tasks/{task_id}/stream
    para recibir la respuesta en tiempo real.

    Args:
        request: Datos de la tarea

    Returns:
        ID de la tarea creada

    Raises:
        HTTPException: Si el controlador no está configurado
    """
    controller = get_agent_controller()

    if not controller.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Agent controller not configured. Set ANTHROPIC_API_KEY environment variable."
        )

    # Generar ID único
    task_id = str(uuid.uuid4())

    # Crear tarea
    task = AgentTask(
        task_id=task_id,
        prompt=request.prompt,
        context=request.context,
        run_id=request.run_id
    )

    return TaskCreateResponse(
        task_id=task_id,
        status="created",
        message="Task created. Use /tasks/{task_id}/stream to receive response."
    )


@router.get("/tasks/{task_id}/stream")
async def stream_task(
    task_id: str,
    model: str = "claude-3-5-sonnet-20241022",
    max_tokens: int = 4096,
    system_prompt: Optional[str] = None
):
    """
    Ejecuta una tarea y retorna la respuesta en streaming (SSE)

    Este endpoint ejecuta la tarea y envía eventos Server-Sent Events con:
    - Fragmentos de contenido a medida que se generan
    - Eventos de estado (running, paused, completed, etc.)
    - Errores si ocurren

    Args:
        task_id: ID de la tarea
        model: Modelo de Claude a usar
        max_tokens: Tokens máximos en la respuesta
        system_prompt: System prompt opcional

    Returns:
        Server-Sent Events stream

    Raises:
        HTTPException: Si la tarea no existe o el controlador no está configurado
    """
    controller = get_agent_controller()

    if not controller.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Agent controller not configured."
        )

    # Obtener tarea
    task = controller.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )

    async def event_generator():
        """Generador de eventos SSE"""
        try:
            async for event in controller.execute_task(
                task=task,
                model=model,
                max_tokens=max_tokens,
                system_prompt=system_prompt
            ):
                # Formato SSE: data: {...}\n\n
                yield f"data: {event}\n\n"

        except Exception as e:
            yield f"data: {{\"type\": \"error\", \"data\": {{\"error\": \"{str(e)}\"}}}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/tasks")
async def list_tasks():
    """
    Lista todas las tareas activas

    Returns:
        Lista de tareas con su estado
    """
    controller = get_agent_controller()
    return {"tasks": controller.list_tasks()}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """
    Obtiene los detalles de una tarea específica

    Args:
        task_id: ID de la tarea

    Returns:
        Detalles de la tarea

    Raises:
        HTTPException: Si la tarea no existe
    """
    controller = get_agent_controller()
    task = controller.get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )

    return task.to_dict()


@router.post("/tasks/{task_id}/pause", response_model=ControlResponse)
async def pause_task(task_id: str):
    """
    Pausa una tarea en ejecución

    Args:
        task_id: ID de la tarea

    Returns:
        Resultado de la operación

    Raises:
        HTTPException: Si la tarea no existe o no puede pausarse
    """
    controller = get_agent_controller()
    success = controller.pause_task(task_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_id} cannot be paused (not running or not found)"
        )

    return ControlResponse(
        success=True,
        task_id=task_id,
        message="Task paused successfully"
    )


@router.post("/tasks/{task_id}/resume", response_model=ControlResponse)
async def resume_task(task_id: str):
    """
    Reanuda una tarea pausada

    Args:
        task_id: ID de la tarea

    Returns:
        Resultado de la operación

    Raises:
        HTTPException: Si la tarea no existe o no puede reanudarse
    """
    controller = get_agent_controller()
    success = controller.resume_task(task_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_id} cannot be resumed (not paused or not found)"
        )

    return ControlResponse(
        success=True,
        task_id=task_id,
        message="Task resumed successfully"
    )


@router.post("/tasks/{task_id}/cancel", response_model=ControlResponse)
async def cancel_task(task_id: str):
    """
    Cancela una tarea en ejecución o pausada

    Args:
        task_id: ID de la tarea

    Returns:
        Resultado de la operación

    Raises:
        HTTPException: Si la tarea no existe o no puede cancelarse
    """
    controller = get_agent_controller()
    success = controller.cancel_task(task_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_id} cannot be cancelled (not running/paused or not found)"
        )

    return ControlResponse(
        success=True,
        task_id=task_id,
        message="Task cancelled successfully"
    )


@router.delete("/tasks")
async def clear_completed_tasks():
    """
    Limpia tareas completadas, fallidas o canceladas

    Returns:
        Número de tareas eliminadas
    """
    controller = get_agent_controller()
    count = controller.clear_completed_tasks()

    return {
        "cleared": count,
        "message": f"Cleared {count} completed tasks"
    }
