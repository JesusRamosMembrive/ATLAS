# SPDX-License-Identifier: MIT
"""
Utilidades para interactuar con la API HTTP de Ollama.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess  # nosec B404 - required for invoking the Ollama CLI safely
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib import parse as urlparse

import httpx

# Configuration: Use environment variables with sensible defaults
OLLAMA_HOST_ENV = "OLLAMA_HOST"
DEFAULT_OLLAMA_HOST = os.getenv(OLLAMA_HOST_ENV, "http://127.0.0.1:11434")
DEFAULT_OLLAMA_PORT = 11434  # Standard Ollama port
MODEL_WARMUP_RETRY_AFTER_SECONDS = 10.0
_LOADING_STATE_TTL = timedelta(minutes=3)
_LOADING_LOCK = threading.Lock()
_LOADING_STATE: Dict[Tuple[str, str], datetime] = {}
ALLOWED_URL_SCHEMES = {"http", "https"}

logger = logging.getLogger(__name__)


def _normalize_endpoint(raw: Optional[str]) -> str:
    """
    Normaliza el endpoint del servidor Ollama asegurando esquema y puerto.
    """
    value = (raw or "").strip()
    if not value:
        return DEFAULT_OLLAMA_HOST

    if "://" not in value:
        value = f"http://{value}"

    parsed = urlparse.urlparse(value)
    netloc = parsed.netloc or parsed.path
    path = "" if parsed.netloc else ""

    if ":" not in netloc and not netloc.startswith("["):
        netloc = f"{netloc}:{DEFAULT_OLLAMA_PORT}"

    normalized = parsed._replace(
        scheme=parsed.scheme or "http",
        netloc=netloc,
        path=path,
        params="",
        query="",
        fragment="",
    )
    return urlparse.urlunparse(normalized).rstrip("/")


def _validate_url(url: str) -> str:
    parsed = urlparse.urlparse(url)
    scheme = parsed.scheme or "http"
    if scheme not in ALLOWED_URL_SCHEMES:
        raise ValueError(f"Unsupported URL scheme: {scheme}")
    return url


def _fetch_json(
    url: str, *, timeout: float = 1.5
) -> tuple[Optional[dict], Optional[str]]:
    """Realiza una petición GET y parsea JSON si es posible."""
    safe_url = _validate_url(url)
    try:
        response = httpx.get(
            safe_url,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json(), None
    except httpx.HTTPStatusError as exc:
        return None, exc.response.text.strip() or str(exc)
    except (httpx.RequestError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _format_bytes(value: Optional[int]) -> Optional[str]:
    """Convierte un tamaño en bytes a formato legible."""
    if value is None or value < 0:
        return None

    units = ("B", "KB", "MB", "GB", "TB")
    size = float(value)
    index = 0

    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1

    if index == 0:
        return f"{int(size)} {units[index]}"
    return f"{size:.1f} {units[index]}"


def _parse_modified(value: Optional[str]) -> Optional[datetime]:
    """Parsea timestamps ISO8601 flexibles."""
    if not value or not isinstance(value, str):
        return None

    candidate = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        pass

    # Normaliza fracciones largas de segundos.
    if "." in candidate:
        head, _, fraction = candidate.partition(".")
        fraction = "".join(ch for ch in fraction if ch.isdigit())
        if "+" in fraction or "-" in fraction:
            fraction, _, tz = fraction.partition("+")
        else:
            tz = ""
        truncated = fraction[:6].ljust(6, "0")
        try:
            return datetime.fromisoformat(f"{head}.{truncated}{tz}")
        except ValueError:
            return None

    return None


def _current_timestamp() -> datetime:
    return datetime.now(timezone.utc)


def _prune_loading_locked(reference: datetime) -> None:
    """Elimina marcas de modelos cargándose que hayan caducado."""
    expired = [
        key
        for key, started in list(_LOADING_STATE.items())
        if reference - started > _LOADING_STATE_TTL
    ]
    for key in expired:
        _LOADING_STATE.pop(key, None)


def _ensure_model_loading(endpoint: str, model: str) -> datetime:
    """Marca un modelo como en proceso de carga y devuelve el timestamp de inicio."""
    now = _current_timestamp()
    with _LOADING_LOCK:
        _prune_loading_locked(now)
        key = (endpoint, model)
        if key not in _LOADING_STATE:
            _LOADING_STATE[key] = now
        return _LOADING_STATE[key]


def _get_model_loading(endpoint: str, model: str) -> Optional[datetime]:
    """Devuelve el instante en el que detectamos que el modelo empezó a cargar."""
    now = _current_timestamp()
    with _LOADING_LOCK:
        _prune_loading_locked(now)
        return _LOADING_STATE.get((endpoint, model))


def _clear_model_loading(endpoint: str, model: str) -> None:
    """Elimina el estado de carga registrado para un modelo."""
    with _LOADING_LOCK:
        _LOADING_STATE.pop((endpoint, model), None)


@dataclass(frozen=True)
class OllamaModelInfo:
    """Modelo instalado disponible para Ollama."""

    name: str
    size_bytes: Optional[int] = None
    size_human: Optional[str] = None
    digest: Optional[str] = None
    modified_at: Optional[datetime] = None
    format: Optional[str] = None


@dataclass(frozen=True)
class OllamaStatus:
    """Estado detectado para Ollama."""

    installed: bool
    running: bool
    models: List[OllamaModelInfo] = field(default_factory=list)
    version: Optional[str] = None
    binary_path: Optional[str] = None
    endpoint: str = DEFAULT_OLLAMA_HOST
    warning: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class OllamaDiscovery:
    """Resultado completo de la detección de Ollama."""

    status: OllamaStatus
    checked_at: datetime


@dataclass(frozen=True)
class OllamaStartResult:
    """Resultado al intentar iniciar el servidor Ollama."""

    started: bool
    already_running: bool
    endpoint: str
    process_id: Optional[int]
    status: OllamaStatus
    checked_at: datetime


class OllamaChatError(RuntimeError):
    """
    Error al comunicarse con Ollama.

    Attributes:
        message: Descripción breve de la causa.
        endpoint: URL del servidor objetivo.
        original_error: Texto del error original si está disponible.
        status_code: Código HTTP retornado por Ollama (si hubo respuesta).
        reason_code: Identificador interno del tipo de error detectado.
        retry_after_seconds: Tiempo recomendado antes de reintentar.
        loading_since: Momento en que se detectó que el modelo inició carga.
    """

    def __init__(
        self,
        message: str,
        *,
        endpoint: str,
        original_error: Optional[str] = None,
        status_code: Optional[int] = None,
        reason_code: Optional[str] = None,
        retry_after_seconds: Optional[float] = None,
        loading_since: Optional[datetime] = None,
    ) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.original_error = original_error
        self.status_code = status_code
        self.reason_code = reason_code
        self.retry_after_seconds = retry_after_seconds
        self.loading_since = loading_since


class OllamaStartError(RuntimeError):
    """Error al intentar iniciar el servidor Ollama."""

    def __init__(
        self,
        message: str,
        *,
        endpoint: str,
        original_error: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.original_error = original_error


@dataclass(frozen=True)
class OllamaChatMessage:
    """Mensaje individual para el formato de chat de Ollama."""

    role: str
    content: str


@dataclass(frozen=True)
class OllamaChatResponse:
    """Respuesta normalizada de una petición de chat."""

    model: str
    message: str
    raw: Dict[str, Any]
    latency_ms: float
    endpoint: str


def chat_with_ollama(
    *,
    model: str,
    messages: Iterable[OllamaChatMessage],
    endpoint: Optional[str] = None,
    timeout: float = 15.0,
) -> OllamaChatResponse:
    """
    Ejecuta una llamada síncrona a la API de chat de Ollama.

    Args:
        model: Identificador del modelo a usar (p. ej. ``"llama3"``).
        messages: Secuencia de mensajes siguiendo el formato chat.
        endpoint: URL base del servidor Ollama (opcional).
        timeout: Tiempo máximo de espera para la respuesta en segundos.
    """
    resolved_endpoint = _normalize_endpoint(endpoint or os.environ.get(OLLAMA_HOST_ENV))
    api_url = _validate_url(f"{resolved_endpoint}/api/chat")
    payload = {
        "model": model,
        "messages": [message.__dict__ for message in messages],
        "stream": False,
    }

    previous_loading = _get_model_loading(resolved_endpoint, model)
    start = time.perf_counter()
    try:
        response = httpx.post(api_url, json=payload, timeout=timeout)
    except httpx.TimeoutException as exc:
        loading_started = previous_loading or _ensure_model_loading(
            resolved_endpoint, model
        )
        raise OllamaChatError(
            "Ollama tardó demasiado en responder. El modelo podría seguir cargándose. Intenta de nuevo en unos segundos.",
            endpoint=resolved_endpoint,
            original_error="timeout",
            reason_code="timeout",
            retry_after_seconds=MODEL_WARMUP_RETRY_AFTER_SECONDS,
            loading_since=loading_started,
        ) from exc
    except httpx.RequestError as exc:
        raise OllamaChatError(
            "No se pudo conectar con el servidor Ollama.",
            endpoint=resolved_endpoint,
            original_error=str(exc),
        ) from exc

    status_code = response.status_code
    if status_code in (503, 504):
        loading_started = _ensure_model_loading(resolved_endpoint, model)
        retry_after = response.headers.get("Retry-After")
        retry_seconds: Optional[float] = MODEL_WARMUP_RETRY_AFTER_SECONDS
        if retry_after:
            try:
                retry_seconds = float(retry_after)
            except ValueError:
                retry_seconds = MODEL_WARMUP_RETRY_AFTER_SECONDS
        raise OllamaChatError(
            "Ollama respondió que el servicio no está listo (posible carga del modelo). Intenta de nuevo en unos segundos.",
            endpoint=resolved_endpoint,
            original_error=response.text.strip() or "service unavailable",
            status_code=status_code,
            reason_code="service_unavailable",
            retry_after_seconds=retry_seconds,
            loading_since=loading_started,
        )

    if status_code >= 400:
        raise OllamaChatError(
            "Error HTTP al invocar Ollama.",
            endpoint=resolved_endpoint,
            original_error=response.text.strip() or str(status_code),
            status_code=status_code,
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise OllamaChatError(
            "Respuesta inválida de Ollama (JSON no parseable).",
            endpoint=resolved_endpoint,
            original_error=str(exc),
        ) from exc

    latency = (time.perf_counter() - start) * 1000
    _clear_model_loading(resolved_endpoint, model)

    message_block = data.get("message") or {}
    content = message_block.get("content")
    if not isinstance(content, str):
        raise OllamaChatError(
            "La respuesta de Ollama no contiene un mensaje válido.",
            endpoint=resolved_endpoint,
            original_error=json.dumps(data, ensure_ascii=False)[:500],
            status_code=status_code,
        )

    return OllamaChatResponse(
        model=model,
        message=content,
        raw=data,
        latency_ms=latency,
        endpoint=resolved_endpoint,
    )


def _detect_ollama(*, timeout: float = 1.5) -> OllamaStatus:
    """Detecta la instalación y estado de ejecución de Ollama."""
    binary_path = shutil.which("ollama")
    installed = binary_path is not None
    version: Optional[str] = None
    warning: Optional[str] = None

    if binary_path:
        output, error = _run_command([binary_path, "--version"])
        if output:
            version = _extract_version(output)
        elif error:
            warning = error

    endpoint = _normalize_endpoint(os.environ.get(OLLAMA_HOST_ENV))
    payload, fetch_error = _fetch_json(f"{endpoint}/api/tags", timeout=timeout)
    models: List[OllamaModelInfo] = []
    running = False

    if payload and isinstance(payload, dict):
        entries = payload.get("models") or []
        for entry in entries:
            name = entry.get("name") or entry.get("model")
            if not name:
                continue
            size = entry.get("size")
            size_bytes = size if isinstance(size, int) else None
            details = (
                entry.get("details") if isinstance(entry.get("details"), dict) else {}
            )
            models.append(
                OllamaModelInfo(
                    name=name,
                    size_bytes=size_bytes,
                    size_human=_format_bytes(size_bytes),
                    digest=entry.get("digest"),
                    modified_at=_parse_modified(entry.get("modified_at")),
                    format=details.get("format"),
                )
            )
        running = True
        # If the endpoint responds, Ollama is definitely installed
        # (even if binary not found in PATH, e.g., Windows service)
        installed = True
    else:
        if fetch_error:
            if warning:
                warning = f"{warning}; {fetch_error}"
            else:
                warning = fetch_error

    return OllamaStatus(
        installed=installed,
        running=running,
        models=models,
        version=version,
        binary_path=binary_path,
        endpoint=endpoint,
        warning=warning if running is False else warning,
    )


def discover_ollama(*, timeout: float = 1.5) -> OllamaDiscovery:
    """Obtiene el estado actual de Ollama."""
    status = _detect_ollama(timeout=timeout)
    return OllamaDiscovery(status=status, checked_at=_current_timestamp())


def _run_command(
    command: List[str], *, timeout: float = 2.0
) -> tuple[Optional[str], Optional[str]]:
    """Ejecuta un comando y devuelve (stdout/stderr combinado, error)."""
    if not command:
        return None, "Comando vacío."
    executable = Path(command[0])
    if not executable.is_absolute():
        resolved = shutil.which(command[0])
        if not resolved:
            return None, "Comando no encontrado."
        executable = Path(resolved)
    sanitized_command = [str(executable)] + command[1:]
    try:
        completed = subprocess.run(  # nosec B603 - parámetros controlados
            sanitized_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return None, "Comando no encontrado."
    except subprocess.TimeoutExpired:
        return None, "Tiempo de espera agotado."
    except (
        OSError,
        subprocess.SubprocessError,
        PermissionError,
    ) as exc:  # pragma: no cover
        # Catch common subprocess errors
        return None, f"Error ejecutando {' '.join(sanitized_command)}: {exc}"
    except Exception as exc:  # pragma: no cover
        # Fallback for truly unexpected errors
        logger.warning("Unexpected error in _safe_run: %s", exc, exc_info=True)
        return None, f"Error inesperado ejecutando {' '.join(sanitized_command)}: {exc}"

    output = (completed.stdout or completed.stderr or "").strip()
    return output or None, None


def _extract_version(raw: Optional[str]) -> Optional[str]:
    """Extrae un token de versión de una salida CLI."""
    if not raw:
        return None
    tokens = raw.strip().split()
    if not tokens:
        return None
    for token in reversed(tokens):
        if any(ch.isdigit() for ch in token):
            return token.strip()
    return tokens[-1]


def start_ollama_server(
    *, timeout: float = 5.0, poll_interval: float = 0.5
) -> OllamaStartResult:
    """
    Intenta iniciar el servidor Ollama (`ollama serve`) y confirma que está operativo.
    """
    discovery = discover_ollama()
    status_before = discovery.status
    if status_before.running:
        return OllamaStartResult(
            started=False,
            already_running=True,
            endpoint=status_before.endpoint,
            process_id=None,
            status=status_before,
            checked_at=discovery.checked_at,
        )

    binary_path = status_before.binary_path or shutil.which("ollama")
    if not binary_path:
        raise OllamaStartError(
            "No se encontró el binario de Ollama en el PATH.",
            endpoint=status_before.endpoint,
            original_error=None,
        )

    try:
        process = (
            subprocess.Popen(  # nosec B603 - se ejecuta binario controlado (ollama)
                [binary_path, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
        )
    except (
        OSError,
        subprocess.SubprocessError,
        PermissionError,
    ) as exc:  # pragma: no cover
        # Catch common subprocess errors: missing binary, permissions, resources
        raise OllamaStartError(
            "No se pudo iniciar el proceso ollama serve.",
            endpoint=status_before.endpoint,
            original_error=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover
        # Fallback for unexpected errors during process creation
        logger.exception("Unexpected error starting Ollama subprocess")
        raise OllamaStartError(
            "Error inesperado al iniciar ollama serve.",
            endpoint=status_before.endpoint,
            original_error=str(exc),
        ) from exc

    elapsed = 0.0
    latest_status = status_before
    while elapsed < timeout:
        time.sleep(poll_interval)
        latest_status = _detect_ollama()
        if latest_status.running:
            return OllamaStartResult(
                started=True,
                already_running=False,
                endpoint=latest_status.endpoint,
                process_id=process.pid,
                status=latest_status,
                checked_at=_current_timestamp(),
            )
        elapsed += poll_interval

    raise OllamaStartError(
        "Ollama no respondió tras intentar iniciarlo.",
        endpoint=latest_status.endpoint,
        original_error="No se detectó actividad en la API dentro del tiempo esperado.",
    )
