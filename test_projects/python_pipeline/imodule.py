# SPDX-License-Identifier: MIT
"""
Base interface for pipeline modules.

@contract:
  type: interface
  pattern: chain_of_responsibility
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class IModule(ABC):
    """
    Abstract base class for pipeline modules.

    Implements the Chain of Responsibility pattern.
    """

    def __init__(self) -> None:
        self._next: Optional["IModule"] = None

    def set_next(self, module: "IModule") -> "IModule":
        """
        Set the next module in the chain.

        @contract:
          precondition: module is not None
          postcondition: self._next == module
        """
        self._next = module
        return module

    @abstractmethod
    def process(self, data: Any) -> Any:
        """
        Process data and pass to next module.

        @contract:
          thread_safety: safe_if_immutable_data
        """
        pass

    def _forward(self, data: Any) -> Any:
        """Forward data to the next module in chain."""
        if self._next is not None:
            return self._next.process(data)
        return data
