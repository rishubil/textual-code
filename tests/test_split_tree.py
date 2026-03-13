"""
Tests for the split tree data structure (pure data, no Textual dependency).

Covers: LeafNode, BranchNode, and all tree manipulation functions.
"""

import pytest

from textual_code.widgets.split_tree import (
    BranchNode,
    LeafNode,
    adjacent_leaf,
    all_leaves,
    all_pane_ids,
    find_leaf,
    find_leaf_for_pane,
    make_leaf,
    parent_of,
    remove_leaf,
    replace_node,
    split_leaf,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _leaf(lid: str, panes: set[str] | None = None) -> LeafNode:
    return LeafNode(leaf_id=lid, pane_ids=panes or set(), opened_files={})


# ── find_leaf ────────────────────────────────────────────────────────────────


def test_find_leaf_single_root():
    root = _leaf("leaf_0")
    assert find_leaf(root, "leaf_0") is root


def test_find_leaf_in_branch():
    left = _leaf("leaf_0")
    right = _leaf("leaf_1")
    root = BranchNode(direction="horizontal", children=[left, right], ratios=[0.5, 0.5])
    assert find_leaf(root, "leaf_0") is left
    assert find_leaf(root, "leaf_1") is right


def test_find_leaf_not_found():
    root = _leaf("leaf_0")
    assert find_leaf(root, "nonexistent") is None


def test_find_leaf_nested():
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    inner = BranchNode(direction="vertical", children=[b, c], ratios=[0.5, 0.5])
    root = BranchNode(direction="horizontal", children=[a, inner], ratios=[0.5, 0.5])
    assert find_leaf(root, "c") is c


# ── find_leaf_for_pane ───────────────────────────────────────────────────────


def test_find_leaf_for_pane_found():
    leaf = LeafNode(leaf_id="leaf_0", pane_ids={"pane_1", "pane_2"}, opened_files={})
    root = BranchNode(
        direction="horizontal",
        children=[leaf, _leaf("leaf_1")],
        ratios=[0.5, 0.5],
    )
    assert find_leaf_for_pane(root, "pane_1") is leaf


def test_find_leaf_for_pane_not_found():
    root = _leaf("leaf_0")
    assert find_leaf_for_pane(root, "nonexistent") is None


# ── all_leaves ───────────────────────────────────────────────────────────────


def test_all_leaves_single():
    root = _leaf("leaf_0")
    assert all_leaves(root) == [root]


def test_all_leaves_order():
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    root = BranchNode(direction="horizontal", children=[a, b, c], ratios=[1 / 3] * 3)
    assert all_leaves(root) == [a, b, c]


def test_all_leaves_nested_order():
    """Visual order: a, b, c — even with nesting."""
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    inner = BranchNode(direction="vertical", children=[b, c], ratios=[0.5, 0.5])
    root = BranchNode(direction="horizontal", children=[a, inner], ratios=[0.5, 0.5])
    assert all_leaves(root) == [a, b, c]


# ── all_pane_ids ─────────────────────────────────────────────────────────────


def test_all_pane_ids_empty():
    root = _leaf("leaf_0")
    assert all_pane_ids(root) == set()


def test_all_pane_ids_multiple_leaves():
    a = LeafNode(leaf_id="a", pane_ids={"p1", "p2"}, opened_files={})
    b = LeafNode(leaf_id="b", pane_ids={"p3"}, opened_files={})
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    assert all_pane_ids(root) == {"p1", "p2", "p3"}


# ── parent_of ────────────────────────────────────────────────────────────────


def test_parent_of_root():
    root = _leaf("leaf_0")
    assert parent_of(root, root) is None


def test_parent_of_child():
    a = _leaf("a")
    b = _leaf("b")
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    assert parent_of(root, a) is root
    assert parent_of(root, b) is root


def test_parent_of_nested():
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    inner = BranchNode(direction="vertical", children=[b, c], ratios=[0.5, 0.5])
    root = BranchNode(direction="horizontal", children=[a, inner], ratios=[0.5, 0.5])
    assert parent_of(root, b) is inner
    assert parent_of(root, inner) is root


# ── replace_node ─────────────────────────────────────────────────────────────


def test_replace_node_root():
    old = _leaf("old")
    new = _leaf("new")
    result = replace_node(old, old, new)
    assert result is new


def test_replace_node_child():
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    new_root = replace_node(root, b, c)
    assert isinstance(new_root, BranchNode)
    assert new_root.children == [a, c]


def test_replace_node_deep():
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    d = _leaf("d")
    inner = BranchNode(direction="vertical", children=[b, c], ratios=[0.5, 0.5])
    root = BranchNode(direction="horizontal", children=[a, inner], ratios=[0.5, 0.5])
    new_root = replace_node(root, c, d)
    assert isinstance(new_root, BranchNode)
    inner_new = new_root.children[1]
    assert isinstance(inner_new, BranchNode)
    assert inner_new.children == [b, d]
    # a should be unchanged
    assert new_root.children[0] is a


# ── split_leaf ───────────────────────────────────────────────────────────────


def test_split_leaf_root_becomes_branch():
    root = _leaf("leaf_0")
    new_root, new_leaf = split_leaf(root, "leaf_0", "horizontal")
    assert isinstance(new_root, BranchNode)
    assert new_root.direction == "horizontal"
    assert len(new_root.children) == 2
    assert new_root.children[0] is root
    assert new_root.children[1] is new_leaf
    assert abs(sum(new_root.ratios) - 1.0) < 1e-9


def test_split_leaf_position_before():
    root = _leaf("leaf_0")
    new_root, new_leaf = split_leaf(root, "leaf_0", "horizontal", position="before")
    assert isinstance(new_root, BranchNode)
    assert new_root.children[0] is new_leaf
    assert new_root.children[1] is root


def test_split_leaf_same_direction_adds_sibling():
    """If parent branch has same direction, insert as sibling (N-children)."""
    a = _leaf("a")
    b = _leaf("b")
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    new_root, new_leaf = split_leaf(root, "b", "horizontal")
    assert isinstance(new_root, BranchNode)
    assert len(new_root.children) == 3
    assert new_root.children == [a, b, new_leaf]
    assert abs(sum(new_root.ratios) - 1.0) < 1e-9


def test_split_leaf_same_direction_adds_sibling_before():
    a = _leaf("a")
    b = _leaf("b")
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    new_root, new_leaf = split_leaf(root, "b", "horizontal", position="before")
    assert new_root.children == [a, new_leaf, b]


def test_split_leaf_different_direction_creates_nested():
    """Split within branch of different direction → creates nested branch."""
    a = _leaf("a")
    b = _leaf("b")
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    new_root, new_leaf = split_leaf(root, "b", "vertical")
    assert isinstance(new_root, BranchNode)
    assert new_root.direction == "horizontal"
    assert len(new_root.children) == 2
    assert new_root.children[0] is a
    inner = new_root.children[1]
    assert isinstance(inner, BranchNode)
    assert inner.direction == "vertical"
    assert inner.children == [b, new_leaf]


def test_split_leaf_nonexistent_raises():
    root = _leaf("leaf_0")
    with pytest.raises(ValueError, match="not found"):
        split_leaf(root, "nonexistent", "horizontal")


def test_split_leaf_ratios_sum_to_one():
    """After any split, ratios sum to 1.0."""
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    root = BranchNode(
        direction="horizontal", children=[a, b, c], ratios=[0.5, 0.3, 0.2]
    )
    new_root, _ = split_leaf(root, "b", "horizontal")
    assert abs(sum(new_root.ratios) - 1.0) < 1e-9


# ── remove_leaf ──────────────────────────────────────────────────────────────


def test_remove_leaf_last_returns_none():
    root = _leaf("leaf_0")
    assert remove_leaf(root, "leaf_0") is None


def test_remove_leaf_two_children_collapses():
    """2-child branch: removing one child → remaining child becomes root."""
    a = _leaf("a")
    b = _leaf("b")
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    result = remove_leaf(root, "a")
    assert result is b


def test_remove_leaf_three_children_removes_and_adjusts():
    """3-child branch: removing one child → 2-child branch with adjusted ratios."""
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    root = BranchNode(
        direction="horizontal", children=[a, b, c], ratios=[0.4, 0.3, 0.3]
    )
    result = remove_leaf(root, "b")
    assert isinstance(result, BranchNode)
    assert len(result.children) == 2
    assert result.children == [a, c]
    assert abs(sum(result.ratios) - 1.0) < 1e-9


def test_remove_leaf_middle_of_three():
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    root = BranchNode(direction="horizontal", children=[a, b, c], ratios=[1 / 3] * 3)
    result = remove_leaf(root, "b")
    assert isinstance(result, BranchNode)
    assert result.children == [a, c]


def test_remove_leaf_nonexistent_raises():
    root = _leaf("leaf_0")
    with pytest.raises(ValueError, match="not found"):
        remove_leaf(root, "nonexistent")


def test_remove_leaf_nested_collapses_parent():
    """Removing from nested 2-child branch: collapses that branch."""
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    inner = BranchNode(direction="vertical", children=[b, c], ratios=[0.5, 0.5])
    root = BranchNode(direction="horizontal", children=[a, inner], ratios=[0.5, 0.5])
    result = remove_leaf(root, "b")
    assert isinstance(result, BranchNode)
    assert result.direction == "horizontal"
    assert result.children == [a, c]


# ── adjacent_leaf ────────────────────────────────────────────────────────────


def test_adjacent_leaf_next():
    a = _leaf("a")
    b = _leaf("b")
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    assert adjacent_leaf(root, "a", delta=+1) is b


def test_adjacent_leaf_prev():
    a = _leaf("a")
    b = _leaf("b")
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    assert adjacent_leaf(root, "b", delta=-1) is a


def test_adjacent_leaf_wrap_forward():
    a = _leaf("a")
    b = _leaf("b")
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    assert adjacent_leaf(root, "b", delta=+1) is a


def test_adjacent_leaf_wrap_backward():
    a = _leaf("a")
    b = _leaf("b")
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    assert adjacent_leaf(root, "a", delta=-1) is b


def test_adjacent_leaf_single_returns_self():
    root = _leaf("leaf_0")
    assert adjacent_leaf(root, "leaf_0", delta=+1) is root


def test_adjacent_leaf_nested():
    """Different depths: Branch(Leaf_a, Branch(Leaf_b, Leaf_c))."""
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    inner = BranchNode(direction="vertical", children=[b, c], ratios=[0.5, 0.5])
    root = BranchNode(direction="horizontal", children=[a, inner], ratios=[0.5, 0.5])
    assert adjacent_leaf(root, "a", delta=+1) is b
    assert adjacent_leaf(root, "b", delta=+1) is c
    assert adjacent_leaf(root, "c", delta=+1) is a
    assert adjacent_leaf(root, "a", delta=-1) is c


# ── make_leaf ────────────────────────────────────────────────────────────────


def test_make_leaf_unique_ids():
    l1 = make_leaf()
    l2 = make_leaf()
    assert l1.leaf_id != l2.leaf_id


def test_make_leaf_empty():
    leaf = make_leaf()
    assert leaf.pane_ids == set()
    assert leaf.opened_files == {}


# ── Invariants ───────────────────────────────────────────────────────────────


def test_all_leaves_count_after_split():
    root = _leaf("a")
    new_root, _ = split_leaf(root, "a", "horizontal")
    assert len(all_leaves(new_root)) == 2
    new_root2, _ = split_leaf(new_root, "a", "vertical")
    assert len(all_leaves(new_root2)) == 3


def test_all_leaves_count_after_remove():
    a = _leaf("a")
    b = _leaf("b")
    c = _leaf("c")
    root = BranchNode(direction="horizontal", children=[a, b, c], ratios=[1 / 3] * 3)
    assert len(all_leaves(root)) == 3
    result = remove_leaf(root, "b")
    assert result is not None
    assert len(all_leaves(result)) == 2
