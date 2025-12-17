# SPDX-License-Identifier: MIT
"""
Main composition root for the Python pipeline.

This file demonstrates the Chain of Responsibility pattern with:
- Generator (source) -> Processor (transform) -> Output (sink)

@aegis-composition-root
"""

from generator import Generator
from processor import Processor
from output import Output


def main() -> None:
    """
    Create and wire the pipeline components.

    @contract:
      type: composition_root
      pattern: chain_of_responsibility
    """
    # Create instances
    gen = Generator(count=5)
    proc = Processor(transform=lambda x: x * 2)
    out = Output()

    # Wire the pipeline: gen -> proc -> out
    gen.set_next(proc)
    proc.set_next(out)

    # Start the pipeline
    gen.start()

    # Print results
    print(f"Results: {out.results}")
    print(f"Processed count: {proc.processed_count}")

    # Cleanup
    gen.stop()


if __name__ == "__main__":
    main()
