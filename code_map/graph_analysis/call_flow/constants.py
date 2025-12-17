# SPDX-License-Identifier: MIT
"""
Constants for Call Flow resolution.

Provides:
- PYTHON_BUILTINS: Set of Python builtin function/class names
- is_stdlib(): Check if a module is part of the standard library
"""

from __future__ import annotations

import importlib.util
import sys
from typing import FrozenSet

# Python builtin functions and types that don't need resolution
# Based on Python 3.10+ builtins
PYTHON_BUILTINS: FrozenSet[str] = frozenset({
    # Builtin functions
    "abs", "aiter", "all", "anext", "any", "ascii",
    "bin", "bool", "breakpoint", "bytearray", "bytes",
    "callable", "chr", "classmethod", "compile", "complex",
    "delattr", "dict", "dir", "divmod",
    "enumerate", "eval", "exec",
    "filter", "float", "format", "frozenset",
    "getattr", "globals",
    "hasattr", "hash", "help", "hex",
    "id", "input", "int", "isinstance", "issubclass", "iter",
    "len", "list", "locals",
    "map", "max", "memoryview", "min",
    "next",
    "object", "oct", "open", "ord",
    "pow", "print", "property",
    "range", "repr", "reversed", "round",
    "set", "setattr", "slice", "sorted", "staticmethod", "str", "sum", "super",
    "tuple", "type",
    "vars",
    "zip",
    # Builtin exceptions and base classes
    "BaseException", "Exception",
    "ArithmeticError", "AssertionError", "AttributeError",
    "BlockingIOError", "BrokenPipeError", "BufferError",
    "BytesWarning",
    "ChildProcessError", "ConnectionAbortedError", "ConnectionError",
    "ConnectionRefusedError", "ConnectionResetError",
    "DeprecationWarning",
    "EOFError", "EnvironmentError", "ExceptionGroup",
    "FileExistsError", "FileNotFoundError", "FloatingPointError",
    "FutureWarning",
    "GeneratorExit",
    "IOError", "ImportError", "ImportWarning", "IndentationError",
    "IndexError", "InterruptedError", "IsADirectoryError",
    "KeyError", "KeyboardInterrupt",
    "LookupError",
    "MemoryError", "ModuleNotFoundError",
    "NameError", "NotADirectoryError", "NotImplemented", "NotImplementedError",
    "OSError", "OverflowError",
    "PendingDeprecationWarning", "PermissionError", "ProcessLookupError",
    "RecursionError", "ReferenceError", "ResourceWarning", "RuntimeError",
    "RuntimeWarning",
    "StopAsyncIteration", "StopIteration", "SyntaxError", "SyntaxWarning",
    "SystemError", "SystemExit",
    "TabError", "TimeoutError", "TypeError",
    "UnboundLocalError", "UnicodeDecodeError", "UnicodeEncodeError",
    "UnicodeError", "UnicodeTranslationError", "UnicodeWarning", "UserWarning",
    "ValueError",
    "Warning",
    "ZeroDivisionError",
    # Special constants
    "True", "False", "None", "Ellipsis", "__debug__",
    # Special attributes/methods that might appear in calls
    "__import__", "__build_class__",
})


def is_stdlib_module(module_name: str) -> bool:
    """
    Check if a module name belongs to the Python standard library.

    Args:
        module_name: The module name to check (e.g., "os", "json", "collections.abc")

    Returns:
        True if the module is part of stdlib, False otherwise.

    Note:
        This uses importlib.util.find_spec which may have import side effects
        for some modules. For safety, we first check builtin_module_names.
    """
    if not module_name:
        return False

    # Get the top-level package name
    top_level = module_name.split(".")[0]

    # Check if it's a builtin module (compiled into Python)
    if top_level in sys.builtin_module_names:
        return True

    # Try to find the module spec
    try:
        spec = importlib.util.find_spec(top_level)
    except (ModuleNotFoundError, ValueError, ImportError):
        return False

    if spec is None or spec.origin is None:
        # Could be a namespace package or not found
        return False

    # Check if the module comes from site-packages (third-party)
    # or from the stdlib location
    origin = spec.origin.lower()

    # If it's in site-packages, it's third-party
    if "site-packages" in origin or "dist-packages" in origin:
        return False

    # If it's a .pyd/.so file in Python's installation, it's stdlib
    # If it's a .py file in Python's lib folder, it's stdlib
    # This is a heuristic that works for most cases
    return True


# Common stdlib modules for quick lookup (avoids importlib overhead)
COMMON_STDLIB_MODULES: FrozenSet[str] = frozenset({
    # Core modules
    "abc", "argparse", "ast", "asyncio", "atexit",
    "base64", "binascii", "bisect", "builtins",
    "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd", "code",
    "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "contextvars", "copy",
    "copyreg", "cProfile", "crypt", "csv", "ctypes", "curses",
    "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis",
    "distutils", "doctest",
    "email", "encodings", "enum", "errno",
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch",
    "fractions", "ftplib", "functools",
    "gc", "getopt", "getpass", "gettext", "glob", "graphlib", "grp", "gzip",
    "hashlib", "heapq", "hmac", "html", "http",
    "idlelib", "imaplib", "imghdr", "importlib", "inspect", "io", "ipaddress",
    "itertools",
    "json",
    "keyword",
    "lib2to3", "linecache", "locale", "logging", "lzma",
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap", "modulefinder",
    "multiprocessing",
    "netrc", "nis", "nntplib", "numbers",
    "operator", "optparse", "os",
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil",
    "platform", "plistlib", "poplib", "posix", "posixpath", "pprint",
    "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc",
    "queue", "quopri",
    "random", "re", "readline", "reprlib", "resource", "rlcompleter", "runpy",
    "sched", "secrets", "select", "selectors", "shelve", "shlex", "shutil",
    "signal", "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver",
    "spwd", "sqlite3", "ssl", "stat", "statistics", "string", "stringprep",
    "struct", "subprocess", "sunau", "symtable", "sys", "sysconfig", "syslog",
    "tabnanny", "tarfile", "telnetlib", "tempfile", "termios", "test", "textwrap",
    "threading", "time", "timeit", "tkinter", "token", "tokenize", "tomllib",
    "trace", "traceback", "tracemalloc", "tty", "turtle", "turtledemo", "types",
    "typing",
    "unicodedata", "unittest", "urllib", "uu", "uuid",
    "venv",
    "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref",
    "xdrlib", "xml", "xmlrpc",
    "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo",
    # Internal/private but commonly seen
    "_thread", "_collections_abc", "_io", "_weakref",
})


def is_stdlib(module_name: str) -> bool:
    """
    Fast check if a module is part of the standard library.

    Uses a pre-computed set of common stdlib modules first,
    then falls back to is_stdlib_module() for edge cases.

    Args:
        module_name: The module name to check.

    Returns:
        True if the module is part of stdlib.
    """
    if not module_name:
        return False

    top_level = module_name.split(".")[0]

    # Fast path: check common modules
    if top_level in COMMON_STDLIB_MODULES:
        return True

    # Slow path: use importlib
    return is_stdlib_module(module_name)
