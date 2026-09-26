"""Node type enum for visualization.

Types of nodes in the track graph. Currently used for standardizing
visualization. All nodes are exactly one type.
"""

from enum import Enum


class NodeType(Enum):
    """Type of node based on graph topology (number of children)."""

    SPLIT = "SPLIT"  # Division node (2+ children)
    END = "END"  # Terminal node (no children)
    CONTINUE = "CONTINUE"  # Node with one child
