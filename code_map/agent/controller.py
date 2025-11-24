"""
Agent Controller - Sistema de control de agente Claude desde web

Proporciona una interfaz para:
- Enviar tareas/prompts al agente
- Ejecutar Claude con streaming en tiempo real
- Controlar el flujo de ejecución (pause, resume, cancel)
- Integrar con el sistema de audit trail existente
"""

import asyncio
import os
from typing import AsyncIterator, Optional, Dict, Any
from datetime import datetime
from enum import Enum

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class AgentStatus(str, Enum):
    """Estado del agente"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTask:
    """Representa una tarea enviada al agente"""

    def __init__(
        self,
        task_id: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        run_id: Optional[int] = None
    ):
        self.task_id = task_id
        self.prompt = prompt
        self.context = context or {}
        self.run_id = run_id
        self.status = AgentStatus.IDLE
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la tarea a diccionario para serialización"""
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "context": self.context,
            "run_id": self.run_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "response": self.response
        }


class AgentController:
    """
    Controlador principal del agente Claude

    Gestiona la ejecución de tareas enviadas desde la web,
    proporciona streaming en tiempo real y control de flujo.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el controlador

        Args:
            api_key: API key de Anthropic (opcional, usa env var si no se proporciona)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client: Optional[anthropic.AsyncAnthropic] = None
        self.active_tasks: Dict[str, AgentTask] = {}
        self._cancel_flags: Dict[str, bool] = {}
        self._pause_flags: Dict[str, bool] = {}

        if ANTHROPIC_AVAILABLE and self.api_key:
            self.client = anthropic.AsyncAnthropic(api_key=self.api_key)

    @property
    def is_configured(self) -> bool:
        """Verifica si el controlador está configurado correctamente"""
        return ANTHROPIC_AVAILABLE and self.client is not None

    def get_status(self) -> Dict[str, Any]:
        """Retorna el estado actual del controlador"""
        return {
            "configured": self.is_configured,
            "anthropic_available": ANTHROPIC_AVAILABLE,
            "has_api_key": bool(self.api_key),
            "active_tasks": len(self.active_tasks),
            "tasks": {
                task_id: task.to_dict()
                for task_id, task in self.active_tasks.items()
            }
        }

    async def execute_task(
        self,
        task: AgentTask,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Ejecuta una tarea con streaming en tiempo real

        Args:
            task: Tarea a ejecutar
            model: Modelo de Claude a usar
            max_tokens: Máximo de tokens en la respuesta
            system_prompt: Prompt del sistema (opcional)

        Yields:
            Diccionarios con eventos de streaming:
            - type: "status" | "content" | "error" | "complete"
            - data: datos del evento
        """
        if not self.is_configured:
            yield {
                "type": "error",
                "data": "Agent controller not configured. Set ANTHROPIC_API_KEY."
            }
            return

        # Registrar tarea como activa
        self.active_tasks[task.task_id] = task
        self._cancel_flags[task.task_id] = False
        self._pause_flags[task.task_id] = False

        task.status = AgentStatus.RUNNING
        task.started_at = datetime.utcnow()

        yield {
            "type": "status",
            "data": {
                "status": "running",
                "task_id": task.task_id,
                "started_at": task.started_at.isoformat()
            }
        }

        try:
            # Construir mensajes
            messages = [{"role": "user", "content": task.prompt}]

            # Añadir contexto si existe
            if task.context:
                context_str = "\n\n".join([
                    f"**{key}**: {value}"
                    for key, value in task.context.items()
                ])
                messages[0]["content"] = f"{context_str}\n\n{task.prompt}"

            # Ejecutar con streaming
            async with self.client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                system=system_prompt if system_prompt else []
            ) as stream:
                async for text in stream.text_stream:
                    # Verificar pausa
                    while self._pause_flags.get(task.task_id, False):
                        await asyncio.sleep(0.1)

                        # Permitir cancelación durante pausa
                        if self._cancel_flags.get(task.task_id, False):
                            break

                    # Verificar cancelación
                    if self._cancel_flags.get(task.task_id, False):
                        task.status = AgentStatus.CANCELLED
                        task.completed_at = datetime.utcnow()

                        yield {
                            "type": "status",
                            "data": {
                                "status": "cancelled",
                                "task_id": task.task_id
                            }
                        }
                        return

                    # Enviar fragmento de contenido
                    task.response += text

                    yield {
                        "type": "content",
                        "data": {
                            "task_id": task.task_id,
                            "text": text,
                            "cumulative_length": len(task.response)
                        }
                    }

            # Tarea completada
            task.status = AgentStatus.COMPLETED
            task.completed_at = datetime.utcnow()

            yield {
                "type": "complete",
                "data": {
                    "task_id": task.task_id,
                    "status": "completed",
                    "completed_at": task.completed_at.isoformat(),
                    "response_length": len(task.response)
                }
            }

        except Exception as e:
            task.status = AgentStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error = str(e)

            yield {
                "type": "error",
                "data": {
                    "task_id": task.task_id,
                    "error": str(e)
                }
            }

        finally:
            # Limpiar flags
            self._cancel_flags.pop(task.task_id, None)
            self._pause_flags.pop(task.task_id, None)

    def pause_task(self, task_id: str) -> bool:
        """
        Pausa una tarea en ejecución

        Args:
            task_id: ID de la tarea

        Returns:
            True si se pausó correctamente, False si no existe o no está en ejecución
        """
        task = self.active_tasks.get(task_id)
        if task and task.status == AgentStatus.RUNNING:
            self._pause_flags[task_id] = True
            task.status = AgentStatus.PAUSED
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        """
        Reanuda una tarea pausada

        Args:
            task_id: ID de la tarea

        Returns:
            True si se reanudó correctamente, False si no existe o no está pausada
        """
        task = self.active_tasks.get(task_id)
        if task and task.status == AgentStatus.PAUSED:
            self._pause_flags[task_id] = False
            task.status = AgentStatus.RUNNING
            return True
        return False

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancela una tarea en ejecución

        Args:
            task_id: ID de la tarea

        Returns:
            True si se canceló correctamente, False si no existe o ya terminó
        """
        task = self.active_tasks.get(task_id)
        if task and task.status in [AgentStatus.RUNNING, AgentStatus.PAUSED]:
            self._cancel_flags[task_id] = True
            return True
        return False

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Obtiene una tarea por su ID"""
        return self.active_tasks.get(task_id)

    def list_tasks(self) -> list[Dict[str, Any]]:
        """Lista todas las tareas activas"""
        return [task.to_dict() for task in self.active_tasks.values()]

    def clear_completed_tasks(self) -> int:
        """
        Limpia tareas completadas, fallidas o canceladas

        Returns:
            Número de tareas eliminadas
        """
        to_remove = [
            task_id
            for task_id, task in self.active_tasks.items()
            if task.status in [AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.CANCELLED]
        ]

        for task_id in to_remove:
            del self.active_tasks[task_id]

        return len(to_remove)


# Singleton global
_controller: Optional[AgentController] = None


def get_agent_controller(api_key: Optional[str] = None) -> AgentController:
    """
    Obtiene la instancia singleton del controlador de agente

    Args:
        api_key: API key opcional (solo se usa en la primera llamada)

    Returns:
        Instancia del AgentController
    """
    global _controller
    if _controller is None:
        _controller = AgentController(api_key=api_key)
    return _controller
