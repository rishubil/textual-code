"""
SplitContainer: holds N children with SplitResizeHandles between them.

Each child is either another SplitContainer or a DraggableTabbedContent.
"""

from __future__ import annotations

from textual.containers import Container
from textual.widget import Widget

from textual_code.widgets.split_resize_handle import SplitResizeHandle
from textual_code.widgets.split_tree import LeafNode, SplitNode


class SplitContainer(Container):
    """Holds N children with SplitResizeHandles between them."""

    def __init__(self, *children: Widget, direction: str = "horizontal", **kwargs):
        super().__init__(*children, **kwargs)
        self._direction = direction
        if direction == "vertical":
            self.add_class("split-vertical")
        else:
            self.add_class("split-horizontal")

    @property
    def direction(self) -> str:
        return self._direction


def build_split_widgets(node: SplitNode) -> Widget:
    """Build widget tree from split tree data structure."""
    from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent

    if isinstance(node, LeafNode):
        return DraggableTabbedContent(id=node.leaf_id)

    children_and_handles: list[Widget] = []
    for i, child in enumerate(node.children):
        if i > 0:
            children_and_handles.append(SplitResizeHandle(child_index=i - 1))
        children_and_handles.append(build_split_widgets(child))

    return SplitContainer(*children_and_handles, direction=node.direction)
