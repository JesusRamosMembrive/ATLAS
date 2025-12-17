# SPDX-License-Identifier: MIT
"""
ExtractorFactory: Factory for creating language-specific call flow extractors.

Provides a unified interface for getting the appropriate extractor based on
file extension, supporting automatic language detection and lazy loading.

Example:
    >>> from code_map.graph_analysis.call_flow.factory import ExtractorFactory
    >>>
    >>> extractor = ExtractorFactory.get_extractor(Path("app.py"))
    >>> if extractor:
    ...     graph = extractor.extract(Path("app.py"), "main")
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Set, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .languages.base_extractor import BaseCallFlowExtractor
    from code_map.index import SymbolIndex


class ExtractorFactory:
    """
    Factory for creating language-specific call flow extractors.

    Provides automatic language detection based on file extension and
    lazy loading of extractors to minimize import overhead.

    Usage:
        # Get extractor for a specific file
        extractor = ExtractorFactory.get_extractor(Path("src/main.py"))

        # Check if extension is supported
        if ExtractorFactory.is_supported(".py"):
            print("Python is supported")

        # Get all supported extensions
        extensions = ExtractorFactory.get_supported_extensions()
    """

    # Extension to language mapping
    _EXTENSION_MAP: Dict[str, str] = {
        # Python
        ".py": "python",
        ".pyw": "python",
        # TypeScript/JavaScript
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mts": "typescript",
        ".cts": "typescript",
        ".js": "typescript",
        ".jsx": "typescript",
        ".mjs": "typescript",
        ".cjs": "typescript",
        # C/C++
        ".c": "cpp",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".h": "cpp",
        ".hpp": "cpp",
        ".hxx": "cpp",
    }

    # Cache for loaded extractor classes
    _extractor_cache: Dict[str, Type["BaseCallFlowExtractor"]] = {}

    @classmethod
    def get_extractor(
        cls,
        file_path: Path,
        root_path: Optional[Path] = None,
        symbol_index: Optional["SymbolIndex"] = None,
    ) -> Optional["BaseCallFlowExtractor"]:
        """
        Get an appropriate extractor for the given file.

        Args:
            file_path: Path to the source file
            root_path: Optional project root for symbol IDs
            symbol_index: Optional SymbolIndex for faster lookups

        Returns:
            Extractor instance for the file type, or None if unsupported
        """
        language = cls._get_language(file_path)
        if language is None:
            return None

        extractor_class = cls._get_extractor_class(language)
        if extractor_class is None:
            return None

        return extractor_class(root_path=root_path, symbol_index=symbol_index)

    @classmethod
    def get_extractor_for_extension(
        cls,
        extension: str,
        root_path: Optional[Path] = None,
        symbol_index: Optional["SymbolIndex"] = None,
    ) -> Optional["BaseCallFlowExtractor"]:
        """
        Get an extractor for a specific file extension.

        Args:
            extension: File extension including dot (e.g., ".py")
            root_path: Optional project root for symbol IDs
            symbol_index: Optional SymbolIndex for faster lookups

        Returns:
            Extractor instance for the extension, or None if unsupported
        """
        language = cls._EXTENSION_MAP.get(extension.lower())
        if language is None:
            return None

        extractor_class = cls._get_extractor_class(language)
        if extractor_class is None:
            return None

        return extractor_class(root_path=root_path, symbol_index=symbol_index)

    @classmethod
    def is_supported(cls, extension: str) -> bool:
        """
        Check if a file extension is supported.

        Args:
            extension: File extension including dot (e.g., ".py")

        Returns:
            True if the extension is supported
        """
        return extension.lower() in cls._EXTENSION_MAP

    @classmethod
    def get_supported_extensions(cls) -> Set[str]:
        """
        Get all supported file extensions.

        Returns:
            Set of supported extensions (including dots)
        """
        return set(cls._EXTENSION_MAP.keys())

    @classmethod
    def get_supported_languages(cls) -> Set[str]:
        """
        Get all supported language names.

        Returns:
            Set of supported language identifiers
        """
        return set(cls._EXTENSION_MAP.values())

    @classmethod
    def _get_language(cls, file_path: Path) -> Optional[str]:
        """Get the language identifier for a file."""
        extension = file_path.suffix.lower()
        return cls._EXTENSION_MAP.get(extension)

    @classmethod
    def _get_extractor_class(cls, language: str) -> Optional[Type["BaseCallFlowExtractor"]]:
        """
        Get the extractor class for a language (lazy loading).

        Uses caching to avoid repeated imports.
        """
        if language in cls._extractor_cache:
            return cls._extractor_cache[language]

        extractor_class = None

        try:
            if language == "python":
                from .languages.python import PythonCallFlowExtractor
                extractor_class = PythonCallFlowExtractor
            elif language == "typescript":
                from .languages.typescript import TsCallFlowExtractor
                extractor_class = TsCallFlowExtractor
            elif language == "cpp":
                from .languages.cpp import CppCallFlowExtractor
                extractor_class = CppCallFlowExtractor
        except ImportError:
            pass

        if extractor_class is not None:
            cls._extractor_cache[language] = extractor_class

        return extractor_class

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the extractor class cache (for testing)."""
        cls._extractor_cache.clear()


# Convenience function for quick access
def get_extractor(
    file_path: Path,
    root_path: Optional[Path] = None,
    symbol_index: Optional["SymbolIndex"] = None,
) -> Optional["BaseCallFlowExtractor"]:
    """
    Get an appropriate extractor for the given file.

    Convenience wrapper for ExtractorFactory.get_extractor().
    """
    return ExtractorFactory.get_extractor(file_path, root_path, symbol_index)
