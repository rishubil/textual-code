"""
Tests for directional_leaf() — finding spatially adjacent leaves by direction.

Covers: left, right, up, down navigation in horizontal/vertical split trees.
"""

from textual_code.widgets.split_tree import (
    BranchNode,
    LeafNode,
    directional_leaf,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _leaf(lid: str) -> LeafNode:
    return LeafNode(leaf_id=lid, pane_ids=set(), opened_files={})


def _H(*children: LeafNode | BranchNode) -> BranchNode:
    """Horizontal branch with evenly distributed ratios."""
    n = len(children)
    return BranchNode(
        direction="horizontal", children=list(children), ratios=[1 / n] * n
    )


def _V(*children: LeafNode | BranchNode) -> BranchNode:
    """Vertical branch with evenly distributed ratios."""
    n = len(children)
    return BranchNode(direction="vertical", children=list(children), ratios=[1 / n] * n)


# ── Simple horizontal split ─────────────────────────────────────────────────


class TestHorizontalSplit:
    """H(a, b): a is left, b is right."""

    def setup_method(self):
        self.a = _leaf("a")
        self.b = _leaf("b")
        self.root = _H(self.a, self.b)

    def test_left_from_right(self):
        assert directional_leaf(self.root, "b", "left") is self.a

    def test_right_from_left(self):
        assert directional_leaf(self.root, "a", "right") is self.b

    def test_left_boundary(self):
        assert directional_leaf(self.root, "a", "left") is None

    def test_right_boundary(self):
        assert directional_leaf(self.root, "b", "right") is None

    def test_up_cross_axis(self):
        assert directional_leaf(self.root, "a", "up") is None

    def test_down_cross_axis(self):
        assert directional_leaf(self.root, "b", "down") is None


# ── Simple vertical split ───────────────────────────────────────────────────


class TestVerticalSplit:
    """V(a, b): a is top, b is bottom."""

    def setup_method(self):
        self.a = _leaf("a")
        self.b = _leaf("b")
        self.root = _V(self.a, self.b)

    def test_up_from_bottom(self):
        assert directional_leaf(self.root, "b", "up") is self.a

    def test_down_from_top(self):
        assert directional_leaf(self.root, "a", "down") is self.b

    def test_up_boundary(self):
        assert directional_leaf(self.root, "a", "up") is None

    def test_down_boundary(self):
        assert directional_leaf(self.root, "b", "down") is None


# ── Nested tree ──────────────────────────────────────────────────────────────


class TestNestedTree:
    """H(a, V(b, c)): a is left, b is top-right, c is bottom-right."""

    def setup_method(self):
        self.a = _leaf("a")
        self.b = _leaf("b")
        self.c = _leaf("c")
        self.root = _H(self.a, _V(self.b, self.c))

    def test_left_from_b(self):
        assert directional_leaf(self.root, "b", "left") is self.a

    def test_left_from_c(self):
        assert directional_leaf(self.root, "c", "left") is self.a

    def test_right_from_a_returns_first_leaf(self):
        """Right from a → first (topmost) leaf of right subtree = b."""
        assert directional_leaf(self.root, "a", "right") is self.b

    def test_up_from_c(self):
        assert directional_leaf(self.root, "c", "up") is self.b

    def test_down_from_b(self):
        assert directional_leaf(self.root, "b", "down") is self.c

    def test_up_from_b_no_vertical_ancestor(self):
        """b is at top of vertical branch, no vertical ancestor above."""
        assert directional_leaf(self.root, "b", "up") is None


# ── Deep nesting walk-up ────────────────────────────────────────────────────


class TestDeepNesting:
    """V(H(a, b), c): a is top-left, b is top-right, c is bottom."""

    def setup_method(self):
        self.a = _leaf("a")
        self.b = _leaf("b")
        self.c = _leaf("c")
        self.root = _V(_H(self.a, self.b), self.c)

    def test_down_from_b(self):
        """b needs to walk past horizontal ancestor to find vertical ancestor."""
        assert directional_leaf(self.root, "b", "down") is self.c

    def test_down_from_a(self):
        assert directional_leaf(self.root, "a", "down") is self.c

    def test_up_from_c_returns_last_leaf(self):
        """Up from c → last leaf of top subtree = b (descent_idx=-1)."""
        assert directional_leaf(self.root, "c", "up") is self.b

    def test_right_from_a(self):
        assert directional_leaf(self.root, "a", "right") is self.b

    def test_left_from_b(self):
        assert directional_leaf(self.root, "b", "left") is self.a


# ── Three-way horizontal ────────────────────────────────────────────────────


class TestThreeWay:
    """H(a, b, c): three siblings in a row."""

    def setup_method(self):
        self.a = _leaf("a")
        self.b = _leaf("b")
        self.c = _leaf("c")
        self.root = _H(self.a, self.b, self.c)

    def test_right_from_a(self):
        assert directional_leaf(self.root, "a", "right") is self.b

    def test_right_from_b(self):
        assert directional_leaf(self.root, "b", "right") is self.c

    def test_left_from_c(self):
        assert directional_leaf(self.root, "c", "left") is self.b

    def test_left_from_b(self):
        assert directional_leaf(self.root, "b", "left") is self.a

    def test_right_boundary(self):
        assert directional_leaf(self.root, "c", "right") is None

    def test_left_boundary(self):
        assert directional_leaf(self.root, "a", "left") is None


# ── Edge cases ───────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_single_leaf_returns_none(self):
        root = _leaf("only")
        assert directional_leaf(root, "only", "left") is None
        assert directional_leaf(root, "only", "right") is None
        assert directional_leaf(root, "only", "up") is None
        assert directional_leaf(root, "only", "down") is None

    def test_nonexistent_leaf_returns_none(self):
        root = _leaf("a")
        assert directional_leaf(root, "nonexistent", "left") is None

    def test_descent_picks_last_leaf_for_left(self):
        """H(V(a, b), V(c, d)): left from c → last leaf of left subtree = b."""
        a, b, c, d = _leaf("a"), _leaf("b"), _leaf("c"), _leaf("d")
        root = _H(_V(a, b), _V(c, d))
        assert directional_leaf(root, "c", "left") is b

    def test_descent_picks_first_leaf_for_right(self):
        """H(V(a, b), V(c, d)): right from b → first leaf of right subtree = c."""
        a, b, c, d = _leaf("a"), _leaf("b"), _leaf("c"), _leaf("d")
        root = _H(_V(a, b), _V(c, d))
        assert directional_leaf(root, "b", "right") is c


class TestGridLayout:
    """H(V(a, b), V(c, d)): 2x2 grid layout.

    Visual:
        [a] [c]
        [b] [d]
    """

    def setup_method(self):
        self.a = _leaf("a")
        self.b = _leaf("b")
        self.c = _leaf("c")
        self.d = _leaf("d")
        self.root = _H(_V(self.a, self.b), _V(self.c, self.d))

    def test_d_left(self):
        assert directional_leaf(self.root, "d", "left") is self.b

    def test_d_up(self):
        assert directional_leaf(self.root, "d", "up") is self.c

    def test_d_right_boundary(self):
        assert directional_leaf(self.root, "d", "right") is None

    def test_d_down_boundary(self):
        assert directional_leaf(self.root, "d", "down") is None

    def test_a_right(self):
        assert directional_leaf(self.root, "a", "right") is self.c

    def test_a_down(self):
        assert directional_leaf(self.root, "a", "down") is self.b

    def test_a_left_boundary(self):
        assert directional_leaf(self.root, "a", "left") is None

    def test_a_up_boundary(self):
        assert directional_leaf(self.root, "a", "up") is None

    def test_b_right(self):
        assert directional_leaf(self.root, "b", "right") is self.c

    def test_c_left(self):
        assert directional_leaf(self.root, "c", "left") is self.b
