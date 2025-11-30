"""
Tests para AgentController

Prueba funcionalidad básica del controlador de agente
sin requerir API key real (usa mocks).
"""

import pytest
from unittest.mock import patch

from code_map.agent import AgentController, AgentTask, AgentStatus


class TestAgentTask:
    """Tests para AgentTask"""

    def test_create_task(self):
        """Test creación de tarea"""
        task = AgentTask(
            task_id="test-123",
            prompt="Test prompt",
            context={"key": "value"},
            run_id=42
        )

        assert task.task_id == "test-123"
        assert task.prompt == "Test prompt"
        assert task.context == {"key": "value"}
        assert task.run_id == 42
        assert task.status == AgentStatus.IDLE
        assert task.response == ""
        assert task.error is None

    def test_task_to_dict(self):
        """Test serialización de tarea"""
        task = AgentTask(
            task_id="test-456",
            prompt="Another prompt"
        )

        data = task.to_dict()

        assert data["task_id"] == "test-456"
        assert data["prompt"] == "Another prompt"
        assert data["status"] == "idle"
        assert "created_at" in data
        assert data["started_at"] is None
        assert data["completed_at"] is None


class TestAgentController:
    """Tests para AgentController"""

    def test_controller_initialization_without_key(self):
        """Test inicialización sin API key"""
        with patch.dict("os.environ", {}, clear=True):
            controller = AgentController()

            assert controller.api_key is None
            assert not controller.is_configured

    # @pytest.mark.skip(reason="Mock test - requires anthropic package")
    # def test_controller_initialization_with_key(self):
    #     """Test inicialización con API key"""
    #     with patch("code_map.agent.controller.ANTHROPIC_AVAILABLE", True):
    #         with patch("code_map.agent.controller.anthropic.AsyncAnthropic") as mock_client:
    #             controller = AgentController(api_key="test-key")
    #
    #             assert controller.api_key == "test-key"
    #             assert controller.is_configured
    #             mock_client.assert_called_once_with(api_key="test-key")

    def test_get_status_unconfigured(self):
        """Test get_status sin configuración"""
        controller = AgentController()
        status = controller.get_status()

        assert "configured" in status
        assert "anthropic_available" in status
        assert "has_api_key" in status
        assert "active_tasks" in status
        assert status["active_tasks"] == 0

    def test_pause_task_nonexistent(self):
        """Test pausar tarea inexistente"""
        controller = AgentController()
        result = controller.pause_task("nonexistent")

        assert result is False

    def test_resume_task_nonexistent(self):
        """Test reanudar tarea inexistente"""
        controller = AgentController()
        result = controller.resume_task("nonexistent")

        assert result is False

    def test_cancel_task_nonexistent(self):
        """Test cancelar tarea inexistente"""
        controller = AgentController()
        result = controller.cancel_task("nonexistent")

        assert result is False

    def test_get_task_nonexistent(self):
        """Test obtener tarea inexistente"""
        controller = AgentController()
        task = controller.get_task("nonexistent")

        assert task is None

    def test_list_tasks_empty(self):
        """Test listar tareas cuando no hay ninguna"""
        controller = AgentController()
        tasks = controller.list_tasks()

        assert tasks == []

    def test_clear_completed_tasks_empty(self):
        """Test limpiar tareas cuando no hay ninguna"""
        controller = AgentController()
        count = controller.clear_completed_tasks()

        assert count == 0

    def test_pause_resume_cycle(self):
        """Test ciclo de pausar y reanudar tarea"""
        controller = AgentController()
        task = AgentTask(task_id="test-pause", prompt="Test")
        task.status = AgentStatus.RUNNING
        controller.active_tasks["test-pause"] = task

        # Pausar
        result = controller.pause_task("test-pause")
        assert result is True
        assert task.status == AgentStatus.PAUSED

        # Reanudar
        result = controller.resume_task("test-pause")
        assert result is True
        assert task.status == AgentStatus.RUNNING

    def test_cancel_running_task(self):
        """Test cancelar tarea en ejecución"""
        controller = AgentController()
        task = AgentTask(task_id="test-cancel", prompt="Test")
        task.status = AgentStatus.RUNNING
        controller.active_tasks["test-cancel"] = task

        result = controller.cancel_task("test-cancel")
        assert result is True
        assert "test-cancel" in controller._cancel_flags
        assert controller._cancel_flags["test-cancel"] is True

    def test_clear_completed_tasks(self):
        """Test limpiar tareas completadas"""
        controller = AgentController()

        # Añadir tareas en diferentes estados
        task1 = AgentTask(task_id="completed", prompt="Test")
        task1.status = AgentStatus.COMPLETED
        controller.active_tasks["completed"] = task1

        task2 = AgentTask(task_id="running", prompt="Test")
        task2.status = AgentStatus.RUNNING
        controller.active_tasks["running"] = task2

        task3 = AgentTask(task_id="failed", prompt="Test")
        task3.status = AgentStatus.FAILED
        controller.active_tasks["failed"] = task3

        # Limpiar
        count = controller.clear_completed_tasks()

        assert count == 2  # completed y failed
        assert "running" in controller.active_tasks
        assert "completed" not in controller.active_tasks
        assert "failed" not in controller.active_tasks


@pytest.mark.asyncio
async def test_execute_task_unconfigured():
    """Test ejecutar tarea sin configuración"""
    controller = AgentController()
    task = AgentTask(task_id="test", prompt="Test")

    events = []
    async for event in controller.execute_task(task):
        events.append(event)

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "not configured" in events[0]["data"].lower()
