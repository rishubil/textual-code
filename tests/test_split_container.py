"""
Tests for the SplitContainer widget and build_split_widgets helper.
"""

from textual.app import App, ComposeResult

from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
from textual_code.widgets.split_container import SplitContainer, build_split_widgets
from textual_code.widgets.split_resize_handle import SplitResizeHandle
from textual_code.widgets.split_tree import BranchNode, LeafNode

# ── build_split_widgets ──────────────────────────────────────────────────────


def test_build_single_leaf():
    """A single LeafNode produces a DraggableTabbedContent."""
    leaf = LeafNode(leaf_id="leaf_0", pane_ids=set(), opened_files={})
    widget = build_split_widgets(leaf)
    assert isinstance(widget, DraggableTabbedContent)
    assert widget.id == "leaf_0"


def test_build_branch_produces_split_container():
    """A BranchNode produces a SplitContainer with children and handles."""
    a = LeafNode(leaf_id="a", pane_ids=set(), opened_files={})
    b = LeafNode(leaf_id="b", pane_ids=set(), opened_files={})
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    widget = build_split_widgets(root)
    assert isinstance(widget, SplitContainer)
    assert widget.direction == "horizontal"


def test_build_nested_tree():
    """Nested tree produces nested SplitContainers."""
    a = LeafNode(leaf_id="a", pane_ids=set(), opened_files={})
    b = LeafNode(leaf_id="b", pane_ids=set(), opened_files={})
    c = LeafNode(leaf_id="c", pane_ids=set(), opened_files={})
    inner = BranchNode(direction="vertical", children=[b, c], ratios=[0.5, 0.5])
    root = BranchNode(direction="horizontal", children=[a, inner], ratios=[0.5, 0.5])
    widget = build_split_widgets(root)
    assert isinstance(widget, SplitContainer)
    assert widget.direction == "horizontal"


# ── SplitContainer layout ───────────────────────────────────────────────────


class _SplitContainerApp(App):
    def __init__(self, split_tree):
        super().__init__()
        self._split_tree = split_tree

    def compose(self) -> ComposeResult:
        yield build_split_widgets(self._split_tree)


async def test_split_container_horizontal_children():
    """Horizontal SplitContainer has children with handles between them."""
    a = LeafNode(leaf_id="a", pane_ids=set(), opened_files={})
    b = LeafNode(leaf_id="b", pane_ids=set(), opened_files={})
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    app = _SplitContainerApp(root)
    async with app.run_test() as pilot:
        await pilot.pause()
        sc = app.query_one(SplitContainer)
        children = list(sc.children)
        # child[0]=DTC, child[1]=handle, child[2]=DTC
        assert len(children) == 3
        assert isinstance(children[0], DraggableTabbedContent)
        assert isinstance(children[1], SplitResizeHandle)
        assert isinstance(children[2], DraggableTabbedContent)


async def test_split_container_vertical_children():
    """Vertical SplitContainer has correct CSS class."""
    a = LeafNode(leaf_id="a", pane_ids=set(), opened_files={})
    b = LeafNode(leaf_id="b", pane_ids=set(), opened_files={})
    root = BranchNode(direction="vertical", children=[a, b], ratios=[0.5, 0.5])
    app = _SplitContainerApp(root)
    async with app.run_test() as pilot:
        await pilot.pause()
        sc = app.query_one(SplitContainer)
        assert sc.has_class("split-vertical")
        assert not sc.has_class("split-horizontal")


async def test_split_container_horizontal_css_class():
    a = LeafNode(leaf_id="a", pane_ids=set(), opened_files={})
    b = LeafNode(leaf_id="b", pane_ids=set(), opened_files={})
    root = BranchNode(direction="horizontal", children=[a, b], ratios=[0.5, 0.5])
    app = _SplitContainerApp(root)
    async with app.run_test() as pilot:
        await pilot.pause()
        sc = app.query_one(SplitContainer)
        assert sc.has_class("split-horizontal")
        assert not sc.has_class("split-vertical")


async def test_split_container_three_children():
    """3-child branch produces 3 DTCs with 2 handles."""
    a = LeafNode(leaf_id="a", pane_ids=set(), opened_files={})
    b = LeafNode(leaf_id="b", pane_ids=set(), opened_files={})
    c = LeafNode(leaf_id="c", pane_ids=set(), opened_files={})
    root = BranchNode(direction="horizontal", children=[a, b, c], ratios=[1 / 3] * 3)
    app = _SplitContainerApp(root)
    async with app.run_test() as pilot:
        await pilot.pause()
        sc = app.query_one(SplitContainer)
        children = list(sc.children)
        # DTC, handle, DTC, handle, DTC
        assert len(children) == 5
        assert isinstance(children[0], DraggableTabbedContent)
        assert isinstance(children[1], SplitResizeHandle)
        assert isinstance(children[2], DraggableTabbedContent)
        assert isinstance(children[3], SplitResizeHandle)
        assert isinstance(children[4], DraggableTabbedContent)


async def test_split_resize_handle_child_index():
    """SplitResizeHandle stores child_index correctly."""
    a = LeafNode(leaf_id="a", pane_ids=set(), opened_files={})
    b = LeafNode(leaf_id="b", pane_ids=set(), opened_files={})
    c = LeafNode(leaf_id="c", pane_ids=set(), opened_files={})
    root = BranchNode(direction="horizontal", children=[a, b, c], ratios=[1 / 3] * 3)
    app = _SplitContainerApp(root)
    async with app.run_test() as pilot:
        await pilot.pause()
        handles = list(app.query(SplitResizeHandle))
        assert len(handles) == 2
        assert handles[0].child_index == 0
        assert handles[1].child_index == 1
