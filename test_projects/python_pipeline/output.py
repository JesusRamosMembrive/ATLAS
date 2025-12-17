# SPDX-License-Identifier: MIT
"""
Output module that collects results from the pipeline.

@contract:
  role: sink
  pattern: chain_of_responsibility
"""

from typing import Any, List

from imodule import IModule


class Output(IModule):
    """
    Collects and stores processed data.

    @contract:
      ownership:
        _results: owns
      thread_safety: not_safe
    """

    def __init__(self) -> None:
        super().__init__()
        self._results: List[Any] = []

    def process(self, data: Any) -> Any:
        """
        Store received data.

        @contract:
          postcondition: data in self._results
        """
        self._results.append(data)
        return self._forward(data)

    @property
    def results(self) -> List[Any]:
        """Return collected results."""
        return self._results.copy()

    def clear(self) -> None:
        """Clear stored results."""
        self._results.clear()
