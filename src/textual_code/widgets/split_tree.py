"""
Pure data tree representing the split layout.

No Textual dependency — just dataclasses and functions.
Structural mutations (split/remove) return new roots;
leaf internal data (pane_ids, opened_files) is mutable in-place.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path

_counter = itertools.count()


@dataclass
class LeafNode:
    leaf_id: str
    pane_ids: set[str] = field(default_factory=set)
    opened_files: dict[Path, str] = field(default_factory=dict)


@dataclass
class BranchNode:
    direction: str  # "horizontal" | "vertical"
    children: list[SplitNode] = field(default_factory=list)
    ratios: list[float] = field(default_factory=list)


SplitNode = LeafNode | BranchNode


def make_leaf() -> LeafNode:
    """Create a new LeafNode with a unique leaf_id."""
    return LeafNode(leaf_id=f"leaf_{next(_counter)}")


def find_leaf(root: SplitNode, leaf_id: str) -> LeafNode | None:
    """Find a LeafNode by its leaf_id."""
    if isinstance(root, LeafNode):
        return root if root.leaf_id == leaf_id else None
    for child in root.children:
        result = find_leaf(child, leaf_id)
        if result is not None:
            return result
    return None


def find_leaf_for_pane(root: SplitNode, pane_id: str) -> LeafNode | None:
    """Find the LeafNode that contains pane_id."""
    if isinstance(root, LeafNode):
        return root if pane_id in root.pane_ids else None
    for child in root.children:
        result = find_leaf_for_pane(child, pane_id)
        if result is not None:
            return result
    return None


def all_leaves(root: SplitNode) -> list[LeafNode]:
    """Return all leaves in visual order (left→right, top→bottom)."""
    if isinstance(root, LeafNode):
        return [root]
    result: list[LeafNode] = []
    for child in root.children:
        result.extend(all_leaves(child))
    return result


def all_pane_ids(root: SplitNode) -> set[str]:
    """Return all pane IDs across all leaves."""
    result: set[str] = set()
    for leaf in all_leaves(root):
        result.update(leaf.pane_ids)
    return result


def parent_of(root: SplitNode, node: SplitNode) -> BranchNode | None:
    """Find the parent BranchNode of node, or None if node is root."""
    if root is node:
        return None
    if isinstance(root, LeafNode):
        return None
    for child in root.children:
        if child is node:
            return root
        result = parent_of(child, node)
        if result is not None:
            return result
    return None


def replace_node(root: SplitNode, old: SplitNode, new: SplitNode) -> SplitNode:
    """Return a new tree with old replaced by new. Shallow copy of branches on path."""
    if root is old:
        return new
    if isinstance(root, LeafNode):
        return root
    new_children = []
    changed = False
    for child in root.children:
        replaced = replace_node(child, old, new)
        new_children.append(replaced)
        if replaced is not child:
            changed = True
    if not changed:
        return root
    return BranchNode(
        direction=root.direction,
        children=new_children,
        ratios=list(root.ratios),
    )


def split_leaf(
    root: SplitNode,
    leaf_id: str,
    direction: str,
    position: str = "after",
) -> tuple[SplitNode, LeafNode]:
    """Split a leaf, returning (new_root, new_leaf).

    If the parent BranchNode has the same direction, the new leaf is inserted
    as a sibling. Otherwise, a new BranchNode wraps old + new leaf.

    Raises ValueError if leaf_id is not found.
    """
    leaf = find_leaf(root, leaf_id)
    if leaf is None:
        raise ValueError(f"Leaf {leaf_id!r} not found")

    new_leaf = make_leaf()
    parent = parent_of(root, leaf)

    if parent is not None and parent.direction == direction:
        # Insert as sibling in existing branch
        idx = parent.children.index(leaf)
        insert_idx = idx + 1 if position == "after" else idx
        new_children = list(parent.children)
        new_children.insert(insert_idx, new_leaf)
        # Redistribute ratios evenly
        n = len(new_children)
        new_ratios = [1.0 / n] * n
        new_branch = BranchNode(
            direction=parent.direction,
            children=new_children,
            ratios=new_ratios,
        )
        return replace_node(root, parent, new_branch), new_leaf

    # Create new BranchNode wrapping old leaf + new leaf
    children = [leaf, new_leaf] if position == "after" else [new_leaf, leaf]
    new_branch = BranchNode(
        direction=direction,
        children=children,
        ratios=[0.5, 0.5],
    )
    return replace_node(root, leaf, new_branch), new_leaf


def remove_leaf(root: SplitNode, leaf_id: str) -> SplitNode | None:
    """Remove a leaf, returning new root or None if tree is empty.

    - 2-child parent: collapses, remaining child replaces parent
    - N-child parent (N>2): removes child, adjusts ratios

    Raises ValueError if leaf_id is not found.
    """
    leaf = find_leaf(root, leaf_id)
    if leaf is None:
        raise ValueError(f"Leaf {leaf_id!r} not found")

    if root is leaf:
        return None

    parent = parent_of(root, leaf)
    assert parent is not None

    idx = parent.children.index(leaf)

    if len(parent.children) == 2:
        # Collapse: remaining child replaces parent
        remaining = parent.children[1 - idx]
        return replace_node(root, parent, remaining)

    # N-child: remove child and adjust ratios
    new_children = [c for i, c in enumerate(parent.children) if i != idx]
    old_ratios = [r for i, r in enumerate(parent.ratios) if i != idx]
    ratio_sum = sum(old_ratios)
    new_ratios = (
        [r / ratio_sum for r in old_ratios]
        if ratio_sum > 0
        else [1.0 / len(new_children)] * len(new_children)
    )
    new_branch = BranchNode(
        direction=parent.direction,
        children=new_children,
        ratios=new_ratios,
    )
    return replace_node(root, parent, new_branch)


def adjacent_leaf(root: SplitNode, leaf_id: str, delta: int = 1) -> LeafNode | None:
    """Return the next (delta=+1) or previous (delta=-1) leaf, wrapping around."""
    leaves = all_leaves(root)
    for i, leaf in enumerate(leaves):
        if leaf.leaf_id == leaf_id:
            return leaves[(i + delta) % len(leaves)]
    return None
