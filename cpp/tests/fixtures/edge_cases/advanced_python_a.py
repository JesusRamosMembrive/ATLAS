#!/usr/bin/env python3
"""Advanced Python syntax test file A."""

import asyncio
from typing import TypeVar, Generic, Protocol
from dataclasses import dataclass, field

T = TypeVar('T')

# Decorators
@dataclass
class Point:
    x: float = 0.0
    y: float = 0.0

    def __post_init__(self):
        self.magnitude = (self.x**2 + self.y**2)**0.5


# Async functions
async def fetch_data(url: str) -> dict:
    """Async function example."""
    await asyncio.sleep(0.1)
    return {"url": url, "data": "content"}


# Walrus operator
def process_items(items: list) -> list:
    """Uses walrus operator."""
    results = []
    while (item := items.pop() if items else None):
        results.append(item * 2)
    return results


# Match statement (Python 3.10+)
def handle_command(command: dict) -> str:
    match command:
        case {"action": "start", "target": target}:
            return f"Starting {target}"
        case {"action": "stop"}:
            return "Stopping"
        case _:
            return "Unknown command"


# Context managers
class Resource:
    def __enter__(self):
        print("Acquiring resource")
        return self

    def __exit__(self, *args):
        print("Releasing resource")


# Generic class
class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()


# Lambda and comprehensions
process = lambda x: x * 2
squares = [x**2 for x in range(10)]
even_squares = {x: x**2 for x in range(10) if x % 2 == 0}
unique_chars = {c for c in "hello world"}


# f-strings with expressions
def format_data(name: str, value: float) -> str:
    return f"{name=}, {value=:.2f}, {len(name)=}"


# Multiple assignment and unpacking
a, b, *rest = [1, 2, 3, 4, 5]
first, *middle, last = "hello"
