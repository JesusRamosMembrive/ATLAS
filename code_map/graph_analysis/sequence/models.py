# SPDX-License-Identifier: MIT
"""
Data models for UML Sequence Diagrams.

Represents the components of a sequence diagram:
- Lifelines: Vertical participants (classes/objects)
- Messages: Horizontal arrows between lifelines
- Activation boxes: Execution periods on lifelines
- Combined fragments: Control flow (alt, opt, loop)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MessageType(str, Enum):
    """Type of message arrow in sequence diagram."""

    SYNC = "sync"  # Solid filled arrow -> (synchronous call)
    ASYNC = "async"  # Open arrow ->> (asynchronous call)
    RETURN = "return"  # Dashed arrow <-- (return message)
    CREATE = "create"  # Dashed arrow with <<create>>
    DESTROY = "destroy"  # Arrow to X (object destruction)
    SELF = "self"  # Self-call (loops back to same lifeline)


class FragmentType(str, Enum):
    """Type of combined fragment in sequence diagram."""

    ALT = "alt"  # Alternative (if/else)
    OPT = "opt"  # Optional (if without else)
    LOOP = "loop"  # Loop (while/for)
    PAR = "par"  # Parallel execution
    TRY = "try"  # Try/except block
    BREAK = "break"  # Break out of enclosing fragment


class ParticipantType(str, Enum):
    """Type of participant/lifeline."""

    CLASS = "class"  # Regular class
    OBJECT = "object"  # Instance of a class
    ACTOR = "actor"  # External actor
    BOUNDARY = "boundary"  # UI/system boundary
    CONTROL = "control"  # Controller
    ENTITY = "entity"  # Data entity
    MODULE = "module"  # Module-level (no class)


@dataclass
class Lifeline:
    """
    A vertical participant in the sequence diagram.

    Represents a class, object, or module that participates in the interaction.
    """

    id: str  # Unique identifier
    name: str  # Display name (class name or module name)
    qualified_name: str  # Full qualified name
    participant_type: ParticipantType = ParticipantType.CLASS
    order: int = 0  # Horizontal position (left to right, 0-indexed)
    file_path: Optional[Path] = None
    line: int = 0
    is_entry_point: bool = False  # True if this is where the sequence starts

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "participant_type": self.participant_type.value,
            "order": self.order,
            "file_path": str(self.file_path) if self.file_path else None,
            "line": self.line,
            "is_entry_point": self.is_entry_point,
        }


@dataclass
class Message:
    """
    A horizontal arrow between lifelines representing a method call.

    Messages are ordered by sequence_number (top to bottom in the diagram).
    """

    id: str  # Unique identifier
    from_lifeline: str  # Source lifeline ID
    to_lifeline: str  # Target lifeline ID
    label: str  # Method name or expression
    message_type: MessageType = MessageType.SYNC
    sequence_number: int = 0  # Order in the sequence (top to bottom)
    arguments: Optional[List[str]] = None
    return_value: Optional[str] = None  # For return messages
    call_site_line: int = 0  # Line number in source code
    # Combined fragment context
    fragment_id: Optional[str] = None  # If inside a fragment
    fragment_operand_index: Optional[int] = None  # Which operand (0=if, 1=else)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "from_lifeline": self.from_lifeline,
            "to_lifeline": self.to_lifeline,
            "label": self.label,
            "message_type": self.message_type.value,
            "sequence_number": self.sequence_number,
            "arguments": self.arguments,
            "return_value": self.return_value,
            "call_site_line": self.call_site_line,
            "fragment_id": self.fragment_id,
            "fragment_operand_index": self.fragment_operand_index,
        }


@dataclass
class ActivationBox:
    """
    A rectangle on a lifeline showing when the object is active.

    Activation boxes show the period during which an object is executing
    a method (between receiving a call and returning).
    """

    id: str  # Unique identifier
    lifeline_id: str  # Which lifeline this activation is on
    start_sequence: int  # Sequence number when activation starts
    end_sequence: int  # Sequence number when activation ends
    nesting_level: int = 0  # For nested activations (recursive calls)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "lifeline_id": self.lifeline_id,
            "start_sequence": self.start_sequence,
            "end_sequence": self.end_sequence,
            "nesting_level": self.nesting_level,
        }


@dataclass
class FragmentOperand:
    """
    One branch/operand within a combined fragment.

    For example, in an 'alt' fragment:
    - Operand 0: [condition] - the 'if' branch
    - Operand 1: [else] - the 'else' branch
    """

    guard: str  # Condition text: [x > 0] or [else]
    message_ids: List[str] = field(default_factory=list)  # Messages in this operand

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "guard": self.guard,
            "message_ids": self.message_ids,
        }


@dataclass
class CombinedFragment:
    """
    A UML 2.0 combined fragment representing control flow.

    Combined fragments are boxes that span multiple lifelines and contain
    one or more operands (branches).
    """

    id: str  # Unique identifier
    fragment_type: FragmentType
    condition_text: str  # The main condition expression
    operands: List[FragmentOperand] = field(default_factory=list)
    start_sequence: int = 0  # First message sequence in fragment
    end_sequence: int = 0  # Last message sequence in fragment
    covering_lifelines: List[str] = field(default_factory=list)  # Lifelines this spans
    parent_fragment_id: Optional[str] = None  # For nested fragments

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "fragment_type": self.fragment_type.value,
            "condition_text": self.condition_text,
            "operands": [op.to_dict() for op in self.operands],
            "start_sequence": self.start_sequence,
            "end_sequence": self.end_sequence,
            "covering_lifelines": self.covering_lifelines,
            "parent_fragment_id": self.parent_fragment_id,
        }


@dataclass
class SequenceDiagram:
    """
    Complete sequence diagram generated from a call flow.

    Contains all the elements needed to render a UML sequence diagram.
    """

    entry_point: str  # Function/method that starts the sequence
    source_file: Optional[Path] = None
    lifelines: Dict[str, Lifeline] = field(default_factory=dict)
    messages: List[Message] = field(default_factory=list)
    activation_boxes: List[ActivationBox] = field(default_factory=list)
    fragments: Dict[str, CombinedFragment] = field(default_factory=dict)
    max_depth: int = 5

    def add_lifeline(self, lifeline: Lifeline) -> None:
        """Add a lifeline to the diagram."""
        self.lifelines[lifeline.id] = lifeline

    def add_message(self, message: Message) -> None:
        """Add a message to the diagram."""
        self.messages.append(message)

    def add_activation_box(self, box: ActivationBox) -> None:
        """Add an activation box to the diagram."""
        self.activation_boxes.append(box)

    def add_fragment(self, fragment: CombinedFragment) -> None:
        """Add a combined fragment to the diagram."""
        self.fragments[fragment.id] = fragment

    def lifeline_count(self) -> int:
        """Get number of lifelines."""
        return len(self.lifelines)

    def message_count(self) -> int:
        """Get number of messages."""
        return len(self.messages)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entry_point": self.entry_point,
            "source_file": str(self.source_file) if self.source_file else None,
            "lifelines": {lid: l.to_dict() for lid, l in self.lifelines.items()},
            "messages": [m.to_dict() for m in self.messages],
            "activation_boxes": [a.to_dict() for a in self.activation_boxes],
            "fragments": {fid: f.to_dict() for fid, f in self.fragments.items()},
            "max_depth": self.max_depth,
        }

    def to_react_flow(self) -> Dict[str, Any]:
        """
        Convert to React Flow compatible format.

        Returns a structure optimized for frontend rendering with
        lifelines as columns and messages as horizontal edges.
        """
        # Lifelines become header nodes at the top
        lifeline_nodes = []
        for lifeline in sorted(self.lifelines.values(), key=lambda l: l.order):
            lifeline_nodes.append({
                "id": f"lifeline:{lifeline.id}",
                "type": "lifelineNode",
                "data": {
                    "name": lifeline.name,
                    "qualifiedName": lifeline.qualified_name,
                    "participantType": lifeline.participant_type.value,
                    "filePath": str(lifeline.file_path) if lifeline.file_path else None,
                    "line": lifeline.line,
                    "isEntryPoint": lifeline.is_entry_point,
                    "order": lifeline.order,
                },
            })

        # Messages become edges (will be positioned vertically by frontend)
        message_edges = []
        for msg in sorted(self.messages, key=lambda m: m.sequence_number):
            edge_type = "syncMessage" if msg.message_type == MessageType.SYNC else "returnMessage"
            if msg.message_type == MessageType.SELF:
                edge_type = "selfMessage"

            message_edges.append({
                "id": f"msg:{msg.id}",
                "source": f"lifeline:{msg.from_lifeline}",
                "target": f"lifeline:{msg.to_lifeline}",
                "type": edge_type,
                "data": {
                    "label": msg.label,
                    "messageType": msg.message_type.value,
                    "sequenceNumber": msg.sequence_number,
                    "arguments": msg.arguments,
                    "returnValue": msg.return_value,
                    "callSiteLine": msg.call_site_line,
                    "fragmentId": msg.fragment_id,
                    "fragmentOperandIndex": msg.fragment_operand_index,
                },
            })

        # Activation boxes as overlay data
        activation_data = [box.to_dict() for box in self.activation_boxes]

        # Fragments as grouped rectangles
        fragment_data = [frag.to_dict() for frag in self.fragments.values()]

        return {
            "lifelines": lifeline_nodes,
            "messages": message_edges,
            "activationBoxes": activation_data,
            "fragments": fragment_data,
            "metadata": {
                "entryPoint": self.entry_point,
                "sourceFile": str(self.source_file) if self.source_file else None,
                "lifelineCount": self.lifeline_count(),
                "messageCount": self.message_count(),
                "maxDepth": self.max_depth,
            },
        }
