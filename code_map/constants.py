# SPDX-License-Identifier: MIT
"""
Constantes compartidas para rutas y archivos internos.
"""

META_DIR_NAME = ".code-map"

# Directorios excluidos por defecto en escaneos/watcher/linters
DEFAULT_EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    META_DIR_NAME,
    "env",
    "node_modules",
    "venv",
}
