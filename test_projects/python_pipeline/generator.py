# SPDX-License-Identifier: MIT
"""
Generator module that produces data for the pipeline.

@contract:
  role: source
  pattern: chain_of_responsibility
"""

from typing import Any, List

from imodule import IModule


class Generator(IModule):
    """
    Generates sequential data for the pipeline.

    @contract:
      lifecycle:
        phases: [created, started, stopped]
        start_method: start
        stop_method: stop
      ownership:
        _data: owns
    """

    def __init__(self, count: int = 10) -> None:
        super().__init__()
        self._count = count
        self._data: List[int] = []
        self._running = False

    def start(self) -> None:
        """
        Start generating data.

        @contract:
          precondition: not self._running
          postcondition: self._running == True
        """
        self._running = True
        self._data = list(range(1, self._count + 1))
        for item in self._data:
            self.process(item)

    def stop(self) -> None:
        """Stop the generator."""
        self._running = False

    def process(self, data: Any) -> Any:
        """
        Process and forward generated data.

        @contract:
          postcondition: data forwarded to next module
        """
        return self._forward(data)
