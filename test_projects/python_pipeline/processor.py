# SPDX-License-Identifier: MIT
"""
Processor module that transforms data in the pipeline.

@contract:
  role: processing
  pattern: chain_of_responsibility
"""

from typing import Any, Callable, Optional

from imodule import IModule


class Processor(IModule):
    """
    Transforms data using a configurable function.

    @contract:
      thread_safety: safe_after_start
      invariants:
        - transform function must be pure
    """

    def __init__(self, transform: Optional[Callable[[Any], Any]] = None) -> None:
        super().__init__()
        self._transform = transform or (lambda x: x * 2)
        self._processed_count = 0

    def process(self, data: Any) -> Any:
        """
        Transform data and forward to next module.

        @contract:
          precondition: data is not None
          postcondition: result == transform(data)
        """
        result = self._transform(data)
        self._processed_count += 1
        return self._forward(result)

    @property
    def processed_count(self) -> int:
        """Return the number of items processed."""
        return self._processed_count
