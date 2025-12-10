#!/usr/bin/env python3
"""Advanced Python syntax test file B - clone of A with renames."""

import asyncio
from typing import TypeVar, Generic, Protocol
from dataclasses import dataclass, field

U = TypeVar('U')

# Decorators
@dataclass
class Coordinate:
    lat: float = 0.0
    lon: float = 0.0

    def __post_init__(self):
        self.distance = (self.lat**2 + self.lon**2)**0.5


# Async functions
async def get_content(endpoint: str) -> dict:
    """Async function example."""
    await asyncio.sleep(0.1)
    return {"url": endpoint, "data": "content"}


# Walrus operator
def transform_elements(elements: list) -> list:
    """Uses walrus operator."""
    output = []
    while (elem := elements.pop() if elements else None):
        output.append(elem * 2)
    return output


# Match statement (Python 3.10+)
def process_request(request: dict) -> str:
    match request:
        case {"action": "start", "target": target}:
            return f"Starting {target}"
        case {"action": "stop"}:
            return "Stopping"
        case _:
            return "Unknown command"


# Context managers
class Connection:
    def __enter__(self):
        print("Acquiring resource")
        return self

    def __exit__(self, *args):
        print("Releasing resource")


# Generic class
class Queue(Generic[U]):
    def __init__(self) -> None:
        self._data: list[U] = []

    def enqueue(self, value: U) -> None:
        self._data.append(value)

    def dequeue(self) -> U:
        return self._data.pop()


# Lambda and comprehensions
transform = lambda y: y * 2
powers = [n**2 for n in range(10)]
filtered_powers = {n: n**2 for n in range(10) if n % 2 == 0}
chars_set = {ch for ch in "hello world"}


# f-strings with expressions
def render_info(label: str, amount: float) -> str:
    return f"{label=}, {amount=:.2f}, {len(label)=}"


# Multiple assignment and unpacking
x, y, *tail = [1, 2, 3, 4, 5]
head, *body, end = "hello"
