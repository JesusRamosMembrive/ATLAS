# SPDX-License-Identifier: MIT
"""
Language-specific contract handling with Strategy pattern.

Each language has its own strategy for:
- Finding contract blocks (@aegis-contract)
- Parsing known documentation patterns (Doxygen, Google style)
- Inserting/updating contract blocks
"""

from .base import CommentBlock, ContractBlock, LanguageStrategy
from .registry import LanguageRegistry

__all__ = [
    "CommentBlock",
    "ContractBlock",
    "LanguageStrategy",
    "LanguageRegistry",
]
