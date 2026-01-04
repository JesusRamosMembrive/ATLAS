# SPDX-License-Identifier: MIT
"""
Transformer to convert CallGraph to SequenceDiagram.

The transformer extracts:
1. Lifelines from unique classes/modules in call nodes
2. Messages from call edges (ordered by execution sequence)
3. Combined fragments from decision nodes
4. Activation boxes from call/return pairs
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..call_flow.models import (
    CallGraph,
    CallNode,
    CallEdge,
    DecisionNode,
    DecisionType,
    ReturnNode,
    ExternalCallNode,
    ExternalCallType,
)
from .models import (
    SequenceDiagram,
    Lifeline,
    Message,
    MessageType,
    ActivationBox,
    CombinedFragment,
    FragmentType,
    FragmentOperand,
    ParticipantType,
)

logger = logging.getLogger(__name__)


class CallFlowToSequenceTransformer:
    """
    Transform a CallGraph into a SequenceDiagram.

    The transformation process:
    1. Extract unique participants (classes/modules) as lifelines
    2. Order lifelines by first appearance in call sequence
    3. Convert call edges to messages with sequence numbers
    4. Map decision nodes to combined fragments (alt/opt/loop)
    5. Calculate activation boxes from message pairs
    """

    def __init__(self):
        self._lifeline_order_counter = 0
        self._sequence_counter = 0
        self._lifeline_cache: Dict[str, str] = {}  # qualified_name -> lifeline_id

    def transform(self, call_graph: CallGraph) -> SequenceDiagram:
        """
        Transform a CallGraph into a SequenceDiagram.

        Args:
            call_graph: The call flow graph to transform

        Returns:
            A SequenceDiagram ready for visualization
        """
        # Reset counters
        self._lifeline_order_counter = 0
        self._sequence_counter = 0
        self._lifeline_cache = {}

        diagram = SequenceDiagram(
            entry_point=call_graph.entry_point,
            source_file=call_graph.source_file,
            max_depth=call_graph.max_depth,
        )

        # Step 1: Extract lifelines from call nodes
        self._extract_lifelines(call_graph, diagram)

        # Step 2: Convert edges to messages
        self._extract_messages(call_graph, diagram)

        # Step 3: Extract external calls as messages
        self._extract_external_calls(call_graph, diagram)

        # Step 4: Convert decision nodes to combined fragments
        self._extract_fragments(call_graph, diagram)

        # Step 5: Calculate activation boxes
        self._calculate_activations(diagram)

        logger.info(
            "Transformed CallGraph to SequenceDiagram: %d lifelines, %d messages, %d fragments",
            diagram.lifeline_count(),
            diagram.message_count(),
            len(diagram.fragments),
        )

        return diagram

    def _extract_lifelines(
        self, call_graph: CallGraph, diagram: SequenceDiagram
    ) -> None:
        """
        Extract lifelines from call nodes.

        Groups call nodes by their class/module to create lifelines.
        Orders lifelines by their first appearance in the call sequence.
        """
        # Track order of first appearance
        seen_participants: Dict[str, int] = {}

        # First pass: identify all unique participants
        for node in call_graph.iter_nodes():
            participant_id = self._get_participant_id(node)
            if participant_id not in seen_participants:
                seen_participants[participant_id] = self._lifeline_order_counter
                self._lifeline_order_counter += 1

                lifeline = self._create_lifeline_from_node(
                    node, seen_participants[participant_id]
                )
                diagram.add_lifeline(lifeline)
                self._lifeline_cache[participant_id] = lifeline.id

        # Mark entry point lifeline
        entry_node = call_graph.get_node(call_graph.entry_point)
        if entry_node:
            entry_participant = self._get_participant_id(entry_node)
            if entry_participant in self._lifeline_cache:
                lifeline_id = self._lifeline_cache[entry_participant]
                if lifeline_id in diagram.lifelines:
                    diagram.lifelines[lifeline_id].is_entry_point = True

    def _extract_messages(
        self, call_graph: CallGraph, diagram: SequenceDiagram
    ) -> None:
        """
        Convert call edges to messages.

        Orders messages by their execution sequence (depth-first traversal).
        """
        # Build adjacency list for traversal
        adjacency: Dict[str, List[CallEdge]] = {}
        for edge in call_graph.iter_edges():
            if edge.source_id not in adjacency:
                adjacency[edge.source_id] = []
            adjacency[edge.source_id].append(edge)

        # Sort edges within each source by call site line for deterministic order
        for edges in adjacency.values():
            edges.sort(key=lambda e: e.call_site_line)

        # Depth-first traversal from entry point to establish sequence
        visited_edges: Set[str] = set()
        self._traverse_calls(
            call_graph.entry_point,
            adjacency,
            visited_edges,
            call_graph,
            diagram,
        )

        # Add return messages for each call
        self._add_return_messages(call_graph, diagram)

    def _traverse_calls(
        self,
        node_id: str,
        adjacency: Dict[str, List[CallEdge]],
        visited_edges: Set[str],
        call_graph: CallGraph,
        diagram: SequenceDiagram,
    ) -> None:
        """Depth-first traversal to create messages in execution order."""
        if node_id not in adjacency:
            return

        source_node = call_graph.get_node(node_id)
        if not source_node:
            return

        for edge in adjacency[node_id]:
            edge_key = f"{edge.source_id}->{edge.target_id}@{edge.call_site_line}"
            if edge_key in visited_edges:
                continue
            visited_edges.add(edge_key)

            target_node = call_graph.get_node(edge.target_id)
            if not target_node:
                continue

            # Create message from source to target
            message = self._create_message_from_edge(
                edge, source_node, target_node, diagram
            )
            if message:
                diagram.add_message(message)

            # Recurse into target
            self._traverse_calls(
                edge.target_id, adjacency, visited_edges, call_graph, diagram
            )

    def _add_return_messages(
        self, call_graph: CallGraph, diagram: SequenceDiagram
    ) -> None:
        """
        Add return messages for explicit return statements.

        Creates dashed arrows back to the caller for return nodes.
        """
        # Group return nodes by their parent call
        returns_by_parent: Dict[str, List[ReturnNode]] = {}
        for return_node in call_graph.iter_return_nodes():
            parent_id = return_node.parent_call_id
            if parent_id not in returns_by_parent:
                returns_by_parent[parent_id] = []
            returns_by_parent[parent_id].append(return_node)

        # Find incoming edges for each node to determine caller
        incoming_edges: Dict[str, CallEdge] = {}
        for edge in call_graph.iter_edges():
            incoming_edges[edge.target_id] = edge

        # Create return messages
        for parent_id, returns in returns_by_parent.items():
            parent_node = call_graph.get_node(parent_id)
            if not parent_node:
                continue

            # Find who called this function
            if parent_id in incoming_edges:
                caller_edge = incoming_edges[parent_id]
                caller_node = call_graph.get_node(caller_edge.source_id)
                if caller_node:
                    for ret in returns:
                        return_msg = self._create_return_message(
                            ret, parent_node, caller_node, diagram
                        )
                        if return_msg:
                            diagram.add_message(return_msg)

    def _extract_external_calls(
        self, call_graph: CallGraph, diagram: SequenceDiagram
    ) -> None:
        """
        Extract external library calls as messages.

        Creates lifelines for external modules (stdlib, builtin, third-party)
        and messages from caller to those external lifelines.
        """
        # Group external calls by caller to maintain order
        external_by_caller: Dict[str, List[ExternalCallNode]] = {}
        for ext_node in call_graph.iter_external_call_nodes():
            caller_id = ext_node.parent_call_id
            if caller_id not in external_by_caller:
                external_by_caller[caller_id] = []
            external_by_caller[caller_id].append(ext_node)

        # Sort external calls within each caller by line number
        for ext_calls in external_by_caller.values():
            ext_calls.sort(key=lambda e: e.line)

        # Process external calls
        for caller_id, ext_calls in external_by_caller.items():
            caller_node = call_graph.get_node(caller_id)
            if not caller_node:
                continue

            caller_participant = self._get_participant_id(caller_node)
            caller_lifeline = self._lifeline_cache.get(caller_participant)
            if not caller_lifeline:
                continue

            for ext_node in ext_calls:
                # Create or get lifeline for external module
                ext_lifeline_id = self._get_or_create_external_lifeline(
                    ext_node, diagram
                )

                # Create message from caller to external
                self._sequence_counter += 1

                # Determine message type (self if same module - unlikely for external)
                message_type = MessageType.SYNC

                message = Message(
                    id=f"ext:{self._sequence_counter}",
                    from_lifeline=caller_lifeline,
                    to_lifeline=ext_lifeline_id,
                    label=self._format_external_label(ext_node),
                    message_type=message_type,
                    sequence_number=self._sequence_counter,
                    call_site_line=ext_node.line,
                    fragment_id=ext_node.decision_id,
                    fragment_operand_index=(
                        self._get_branch_index(ext_node.branch_id)
                        if ext_node.branch_id else None
                    ),
                )
                diagram.add_message(message)

    def _get_or_create_external_lifeline(
        self, ext_node: ExternalCallNode, diagram: SequenceDiagram
    ) -> str:
        """
        Get or create a lifeline for an external module.

        Groups external calls by module_hint or call_type to avoid
        creating too many lifelines.
        """
        # Determine the external lifeline name
        if ext_node.module_hint:
            # Use module name (e.g., "requests", "json", "os")
            ext_name = ext_node.module_hint.split(".")[0]  # Top-level module
        else:
            # Use call type as fallback (e.g., "builtin", "stdlib")
            ext_name = ext_node.call_type.value

        # Create a unique ID for this external lifeline
        ext_lifeline_key = f"ext:{ext_name}"

        if ext_lifeline_key not in self._lifeline_cache:
            # Create new lifeline for this external module
            lifeline = Lifeline(
                id=ext_lifeline_key,
                name=ext_name,
                qualified_name=ext_name,
                participant_type=ParticipantType.ENTITY,  # External entities
                order=self._lifeline_order_counter,
                file_path=None,  # External modules don't have a project file
                line=0,
                is_entry_point=False,
            )
            self._lifeline_order_counter += 1
            diagram.add_lifeline(lifeline)
            self._lifeline_cache[ext_lifeline_key] = lifeline.id

        return self._lifeline_cache[ext_lifeline_key]

    def _format_external_label(self, ext_node: ExternalCallNode) -> str:
        """
        Format the label for an external call message.

        Shortens long expressions while keeping them informative.
        """
        expr = ext_node.expression

        # If expression is too long, truncate with ellipsis
        if len(expr) > 40:
            # Try to extract just the function/method name
            if "(" in expr:
                # Get the part before the arguments
                call_part = expr.split("(")[0]
                # Get just the last part (method name)
                if "." in call_part:
                    method = call_part.split(".")[-1]
                    return f"{method}(...)"
                return f"{call_part}(...)"
            return expr[:37] + "..."

        return expr

    def _extract_fragments(
        self, call_graph: CallGraph, diagram: SequenceDiagram
    ) -> None:
        """
        Convert decision nodes to combined fragments.

        Maps:
        - IF_ELSE with 2+ branches -> alt
        - IF_ELSE with 1 branch -> opt
        - TRY_EXCEPT -> alt with [try] and [except] operands
        """
        for decision_node in call_graph.iter_decision_nodes():
            fragment = self._create_fragment_from_decision(decision_node, diagram)
            if fragment:
                diagram.add_fragment(fragment)

    def _calculate_activations(self, diagram: SequenceDiagram) -> None:
        """
        Calculate activation boxes from message pairs.

        An activation starts when a lifeline receives a sync message
        and ends when it sends a return message.
        """
        # Track activations per lifeline
        active_calls: Dict[str, List[Tuple[int, int]]] = {}  # lifeline_id -> [(start, end)]

        # Group messages by target lifeline
        messages_to_lifeline: Dict[str, List[Message]] = {}
        for msg in diagram.messages:
            if msg.to_lifeline not in messages_to_lifeline:
                messages_to_lifeline[msg.to_lifeline] = []
            messages_to_lifeline[msg.to_lifeline].append(msg)

        # For each lifeline, find call/return pairs
        for lifeline_id, messages in messages_to_lifeline.items():
            incoming_calls = [m for m in messages if m.message_type == MessageType.SYNC]
            outgoing_returns = [
                m for m in diagram.messages
                if m.from_lifeline == lifeline_id and m.message_type == MessageType.RETURN
            ]

            # Simple heuristic: each incoming call creates an activation
            # that ends at the next return from this lifeline
            for call_msg in incoming_calls:
                # Find the return that ends this activation
                end_seq = call_msg.sequence_number + 1  # Default to next sequence
                for ret_msg in outgoing_returns:
                    if ret_msg.sequence_number > call_msg.sequence_number:
                        end_seq = ret_msg.sequence_number
                        break

                activation = ActivationBox(
                    id=f"act:{lifeline_id}:{call_msg.sequence_number}",
                    lifeline_id=lifeline_id,
                    start_sequence=call_msg.sequence_number,
                    end_sequence=end_seq,
                    nesting_level=0,  # TODO: Calculate nesting for recursive calls
                )
                diagram.add_activation_box(activation)

    # Helper methods

    def _get_participant_id(self, node: CallNode) -> str:
        """
        Get the participant (lifeline) ID from a call node.

        For methods: returns the class name
        For functions: returns the module name
        For external calls: returns the module hint or inferred module
        """
        # Handle external/builtin nodes specially
        if node.kind in ("external", "builtin"):
            # Try to extract module from qualified name (e.g., "session.exec" -> "session")
            qualified = node.qualified_name
            if "." in qualified:
                parts = qualified.split(".")
                return f"ext:{parts[0]}"  # e.g., "ext:session"
            # Try to extract from node ID (e.g., "external:sqlmodel:select:813" -> "sqlmodel")
            if node.id.startswith("external:"):
                parts = node.id.split(":")
                if len(parts) >= 2 and parts[1]:
                    return f"ext:{parts[1]}"  # e.g., "ext:sqlmodel"
            # Fallback to kind
            return f"ext:{node.kind}"

        qualified = node.qualified_name

        # If it's a method (contains dot), extract class name
        if "." in qualified:
            parts = qualified.rsplit(".", 1)
            return parts[0]  # Class or module name

        # For standalone functions, use module from file path
        if node.file_path:
            return node.file_path.stem  # File name without extension

        return "unknown"

    def _create_lifeline_from_node(self, node: CallNode, order: int) -> Lifeline:
        """Create a Lifeline from a CallNode."""
        participant_id = self._get_participant_id(node)

        # Determine participant type
        if node.kind == "method":
            participant_type = ParticipantType.CLASS
        elif node.kind == "function":
            participant_type = ParticipantType.MODULE
        elif node.kind == "external" or node.kind == "builtin":
            participant_type = ParticipantType.ENTITY
        else:
            participant_type = ParticipantType.CLASS

        # Extract display name - for external IDs like "ext:session", use "session"
        if participant_id.startswith("ext:"):
            display_name = participant_id[4:]  # Remove "ext:" prefix
        else:
            display_name = participant_id.split(".")[-1]  # Short name

        return Lifeline(
            id=f"ll:{participant_id}",
            name=display_name,
            qualified_name=participant_id,
            participant_type=participant_type,
            order=order,
            file_path=node.file_path,
            line=node.line,
        )

    def _create_message_from_edge(
        self,
        edge: CallEdge,
        source_node: CallNode,
        target_node: CallNode,
        diagram: SequenceDiagram,
    ) -> Optional[Message]:
        """Create a Message from a CallEdge."""
        source_participant = self._get_participant_id(source_node)
        target_participant = self._get_participant_id(target_node)

        source_lifeline = self._lifeline_cache.get(source_participant)
        target_lifeline = self._lifeline_cache.get(target_participant)

        if not source_lifeline or not target_lifeline:
            return None

        # Determine message type
        if source_lifeline == target_lifeline:
            message_type = MessageType.SELF
        else:
            message_type = MessageType.SYNC

        self._sequence_counter += 1

        return Message(
            id=f"m:{self._sequence_counter}",
            from_lifeline=source_lifeline,
            to_lifeline=target_lifeline,
            label=target_node.name,  # Method/function being called
            message_type=message_type,
            sequence_number=self._sequence_counter,
            arguments=edge.arguments,
            call_site_line=edge.call_site_line,
            fragment_id=edge.decision_id,
            fragment_operand_index=self._get_branch_index(edge.branch_id) if edge.branch_id else None,
        )

    def _create_return_message(
        self,
        return_node: ReturnNode,
        from_node: CallNode,
        to_node: CallNode,
        diagram: SequenceDiagram,
    ) -> Optional[Message]:
        """Create a return Message from a ReturnNode."""
        from_participant = self._get_participant_id(from_node)
        to_participant = self._get_participant_id(to_node)

        from_lifeline = self._lifeline_cache.get(from_participant)
        to_lifeline = self._lifeline_cache.get(to_participant)

        if not from_lifeline or not to_lifeline:
            return None

        self._sequence_counter += 1

        return Message(
            id=f"r:{self._sequence_counter}",
            from_lifeline=from_lifeline,
            to_lifeline=to_lifeline,
            label=return_node.return_value or "return",
            message_type=MessageType.RETURN,
            sequence_number=self._sequence_counter,
            return_value=return_node.return_value,
            call_site_line=return_node.line,
            fragment_id=return_node.decision_id,
            fragment_operand_index=self._get_branch_index(return_node.branch_id) if return_node.branch_id else None,
        )

    def _create_fragment_from_decision(
        self, decision_node: DecisionNode, diagram: SequenceDiagram
    ) -> Optional[CombinedFragment]:
        """Create a CombinedFragment from a DecisionNode."""
        # Map decision type to fragment type
        if decision_node.decision_type == DecisionType.IF_ELSE:
            if len(decision_node.branches) > 1:
                fragment_type = FragmentType.ALT
            else:
                fragment_type = FragmentType.OPT
        elif decision_node.decision_type == DecisionType.TRY_EXCEPT:
            fragment_type = FragmentType.TRY
        elif decision_node.decision_type == DecisionType.MATCH_CASE:
            fragment_type = FragmentType.ALT
        else:
            fragment_type = FragmentType.OPT

        # Create operands from branches
        operands = []
        for branch in decision_node.branches:
            operand = FragmentOperand(
                guard=f"[{branch.label}] {branch.condition_text}".strip(),
                message_ids=[],  # Will be populated by messages with this fragment_id
            )
            operands.append(operand)

        # Find messages within this fragment
        fragment_messages = [
            m for m in diagram.messages
            if m.fragment_id == decision_node.id
        ]

        # Determine which lifelines this fragment covers
        covering_lifelines = set()
        for msg in fragment_messages:
            covering_lifelines.add(msg.from_lifeline)
            covering_lifelines.add(msg.to_lifeline)

        # Calculate sequence range
        if fragment_messages:
            start_seq = min(m.sequence_number for m in fragment_messages)
            end_seq = max(m.sequence_number for m in fragment_messages)
        else:
            start_seq = 0
            end_seq = 0

        return CombinedFragment(
            id=f"frag:{decision_node.id}",
            fragment_type=fragment_type,
            condition_text=decision_node.condition_text,
            operands=operands,
            start_sequence=start_seq,
            end_sequence=end_seq,
            covering_lifelines=list(covering_lifelines),
        )

    def _get_branch_index(self, branch_id: Optional[str]) -> Optional[int]:
        """Extract branch index from branch_id (format: 'decision_id:branch:N')."""
        if not branch_id:
            return None
        parts = branch_id.split(":branch:")
        if len(parts) == 2:
            try:
                return int(parts[1])
            except ValueError:
                pass
        return None
