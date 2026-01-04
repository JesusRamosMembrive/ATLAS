# SPDX-License-Identifier: MIT
"""
Sequence diagram generation from call flow graphs.

Transforms CallGraph data into UML sequence diagram format for visualization.
"""

from .models import (
    Lifeline,
    Message,
    MessageType,
    ActivationBox,
    CombinedFragment,
    FragmentType,
    FragmentOperand,
    SequenceDiagram,
)
from .transformer import CallFlowToSequenceTransformer

__all__ = [
    "Lifeline",
    "Message",
    "MessageType",
    "ActivationBox",
    "CombinedFragment",
    "FragmentType",
    "FragmentOperand",
    "SequenceDiagram",
    "CallFlowToSequenceTransformer",
]
