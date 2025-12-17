# SPDX-License-Identifier: MIT
"""
Registry for language-specific contract strategies.

Similar pattern to analyzer_registry.py in AEGIS v1.
Allows registering strategies and getting them by file extension.
"""

from pathlib import Path
from typing import Dict, List, Optional, Type

from .base import LanguageStrategy


class LanguageRegistry:
    """
    Central registry of Language Strategies.

    Allows registering strategies and obtaining them by file extension.
    """

    _strategies: Dict[str, LanguageStrategy] = {}
    _extension_map: Dict[str, str] = {}

    @classmethod
    def register(cls, strategy_class: Type[LanguageStrategy]) -> Type[LanguageStrategy]:
        """
        Register a strategy. Can be used as decorator.

        Example:
            @LanguageRegistry.register
            class MyLanguageStrategy(LanguageStrategy):
                ...
        """
        instance = strategy_class()
        cls._strategies[instance.language_id] = instance

        for ext in instance.file_extensions:
            ext_lower = ext.lower()
            cls._extension_map[ext_lower] = instance.language_id

        return strategy_class

    @classmethod
    def get_for_file(cls, path: Path) -> Optional[LanguageStrategy]:
        """Get appropriate strategy for a file by its extension."""
        ext = path.suffix.lower()
        lang_id = cls._extension_map.get(ext)
        return cls._strategies.get(lang_id) if lang_id else None

    @classmethod
    def get_by_id(cls, language_id: str) -> Optional[LanguageStrategy]:
        """Get strategy by language identifier."""
        return cls._strategies.get(language_id)

    @classmethod
    def supported_extensions(cls) -> List[str]:
        """List all supported file extensions."""
        return list(cls._extension_map.keys())

    @classmethod
    def supported_languages(cls) -> List[str]:
        """List all supported language IDs."""
        return list(cls._strategies.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear the registry. Useful for tests."""
        cls._strategies.clear()
        cls._extension_map.clear()
