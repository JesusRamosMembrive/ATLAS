# SPDX-License-Identifier: MIT
"""
CLI principal para gestionar Code Map desde la terminal.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - solo para tipado
    import typer  # type: ignore[import-not-found]
else:  # pragma: no cover - manejo de dependencia opcional en runtime


    try:
        import typer  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Typer es un requisito para ejecutar la CLI de Code Map."
        ) from exc
import uvicorn

from .settings import AppSettings, load_settings, save_settings

app = typer.Typer(
    help="Utilidades de Code Map para configurar y lanzar el backend.",
    no_args_is_help=True,
    pretty_exceptions_enable=True,
)
config_app = typer.Typer(help="Gestiona la configuración persistente.")
app.add_typer(config_app, name="config")


def _validate_root(path: Path) -> Path:
    """Normaliza y valida que la ruta sea un directorio existente."""
    normalized = path.expanduser().resolve()
    if not normalized.exists():
        raise typer.BadParameter(f"La ruta `{normalized}` no existe")
    if not normalized.is_dir():
        raise typer.BadParameter(f"La ruta `{normalized}` debe ser un directorio")
    return normalized


def _persist_root(new_root: Optional[Path]) -> AppSettings:
    """Actualiza la configuración persistente con la ruta indicada."""
    if new_root is not None:
        settings = load_settings(root_override=new_root)
    else:
        settings = load_settings()

    save_settings(settings)
    return settings


@app.command()
def run(
    root: Optional[Path] = typer.Option(
        None,
        "--root",
        "-r",
        help="Directorio a analizar. Por defecto se usa el directorio actual.",
        dir_okay=True,
        file_okay=False,
        resolve_path=True,
        show_default=False,
    ),
    host: str = typer.Option(
        os.getenv("CODE_MAP_HOST", "127.0.0.1"),
        help="Host donde exponer la API (usa 0.0.0.0 para acceso externo controlado). Env: CODE_MAP_HOST",
    ),
    port: int = typer.Option(
        int(os.getenv("CODE_MAP_PORT", "8010")),
        help="Puerto donde escuchar. Env: CODE_MAP_PORT",
    ),
    log_level: str = typer.Option(
        "info",
        help="Nivel de log de Uvicorn.",
        case_sensitive=False,
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Recarga automática al editar archivos del backend.",
    ),
) -> None:
    """
    Arranca el backend FastAPI usando la configuración almacenada.
    """
    selected_root: Optional[Path] = None
    if root is not None:
        selected_root = _validate_root(root)

    settings = _persist_root(selected_root)
    typer.secho(
        f"Escaneando proyecto en {settings.root_path}",
        fg=typer.colors.GREEN,
    )

    config = uvicorn.Config(
        "code_map.server:create_app",
        factory=True,
        host=host,
        port=port,
        log_level=log_level.lower(),
        reload=reload,
    )

    server = uvicorn.Server(config)
    try:
        server.run()
    except KeyboardInterrupt:  # pragma: no cover - flujo estándar
        typer.echo("\nServidor detenido por el usuario.")
    except Exception as exc:  # pragma: no cover - reporte genérico
        typer.secho(f"Error al iniciar el servidor: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc


@config_app.command("show")
def config_show() -> None:
    """Muestra la configuración almacenada actualmente."""
    settings = load_settings()
    typer.echo(f"Raíz: {settings.root_path}")
    typer.echo(f"Incluir docstrings: {settings.include_docstrings}")
    typer.echo(f"Exclusiones: {', '.join(settings.exclude_dirs) or '(ninguna)'}")


@config_app.command("set-root")
def config_set_root(
    root: Path = typer.Argument(..., help="Directorio a analizar.")
) -> None:
    """Actualiza la raíz analizada por el backend."""
    normalized = _validate_root(root)
    settings = _persist_root(normalized)
    typer.secho(f"Raíz actualizada a {settings.root_path}", fg=typer.colors.GREEN)


@config_app.command("reset")
def config_reset() -> None:
    """Restablece la raíz al directorio actual."""
    current = Path.cwd()
    settings = _persist_root(current)
    typer.secho(f"Raíz restablecida a {settings.root_path}", fg=typer.colors.GREEN)


def main() -> None:
    """Punto de entrada para `python -m code_map`."""
    app()


if __name__ == "__main__":  # pragma: no cover - ejecución directa
    main()
