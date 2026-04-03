from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Label,
    ListItem,
    ListView,
    Select,
)

if TYPE_CHECKING:
    from textual_code.app import TextualCode
    from textual_code.config import FooterOrders, ShortcutDisplayEntry


@dataclass
class RebindResult:
    """Result returned by RebindKeyScreen."""

    is_cancelled: bool
    action_name: str | None
    new_key: str | None


class RebindKeyScreen(ModalScreen[RebindResult]):
    """Modal that captures a single key press as a new binding for an action."""

    DEFAULT_CSS = """
    RebindKeyScreen {
        align: center middle;
    }
    RebindKeyScreen #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1 1 1 3;
        padding: 0 1;
        width: 60;
        height: 14;
        border: thick $background 80%;
        background: $surface;
    }
    RebindKeyScreen #title {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }
    RebindKeyScreen #current_row {
        column-span: 2;
        height: 1fr;
    }
    RebindKeyScreen #captured_key {
        column-span: 2;
        height: 1fr;
        content-align: center middle;
        text-style: bold;
    }
    """

    # Keys that are not capturable (reserved for UI control)
    _SKIP_KEYS = frozenset({"escape", "enter", "tab", "shift+tab"})

    def __init__(self, action_name: str, description: str, current_key: str) -> None:
        super().__init__()
        self._action = action_name
        self._description = description
        self._current_key = current_key
        self._captured: str | None = None

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(f"Rebind: {self._description}", id="title"),
            Label(f"Current key: {self._current_key}", id="current_row"),
            Label("Press new key combination...", id="captured_key"),
            Button("Apply", variant="primary", id="apply", disabled=True),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(
                RebindResult(is_cancelled=True, action_name=None, new_key=None)
            )
            event.stop()
            return
        if event.key in self._SKIP_KEYS:
            return
        self._captured = event.key
        self.query_one("#captured_key", Label).update(event.key)
        self.query_one("#apply", Button).disabled = False
        event.stop()

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        if self._captured:
            self.dismiss(
                RebindResult(
                    is_cancelled=False,
                    action_name=self._action,
                    new_key=self._captured,
                )
            )

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(RebindResult(is_cancelled=True, action_name=None, new_key=None))


@dataclass
class ShortcutSettingsResult:
    """Result from the ShortcutSettingsScreen dialog."""

    is_cancelled: bool
    action_name: str | None = None
    new_key: str | None = None
    palette_visible: bool | None = None


class ShortcutSettingsScreen(ModalScreen[ShortcutSettingsResult]):
    """Modal for configuring a single shortcut's display preferences."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    ShortcutSettingsScreen {
        align: center middle;
    }
    ShortcutSettingsScreen #dialog {
        padding: 1 2;
        width: 60;
        height: auto;
        max-height: 20;
        border: thick $background 80%;
        background: $surface;
    }
    ShortcutSettingsScreen #title {
        height: 1;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    ShortcutSettingsScreen #current_key_label {
        height: 1;
        margin-bottom: 1;
    }
    ShortcutSettingsScreen #change_key {
        margin-bottom: 0;
        width: 100%;
    }
    ShortcutSettingsScreen #unbind {
        margin-bottom: 1;
        width: 100%;
    }
    ShortcutSettingsScreen .buttons {
        height: 3;
        margin-top: 1;
        layout: horizontal;
    }
    ShortcutSettingsScreen .buttons Button {
        width: 1fr;
        margin: 0 1;
    }
    """

    def __init__(
        self,
        action_name: str,
        description: str,
        current_key: str,
        palette_visible: bool = True,
    ) -> None:
        super().__init__()
        self._action = action_name
        self._description = description
        self._current_key = current_key
        self._palette_visible = palette_visible
        self._new_key: str | None = None

    def compose(self) -> ComposeResult:
        is_unbound = not self._current_key or self._current_key == "(none)"
        yield Vertical(
            Label(f"Shortcut Settings: {self._description}", id="title"),
            Label(f"Current key: {self._current_key}", id="current_key_label"),
            Button("Change Key...", variant="default", id="change_key"),
            Button(
                "Unbind",
                variant="warning",
                id="unbind",
                disabled=is_unbound,
            ),
            Checkbox(
                "Show in command palette", self._palette_visible, id="palette_visible"
            ),
            Horizontal(
                Button("Save", variant="primary", id="save"),
                Button("Cancel", variant="default", id="cancel"),
                classes="buttons",
            ),
            id="dialog",
        )

    @on(Button.Pressed, "#change_key")
    def on_change_key(self) -> None:
        self.app.push_screen(
            RebindKeyScreen(self._action, self._description, self._current_key),
            self._on_rebind,
        )

    def _on_rebind(self, result: RebindResult | None) -> None:
        if result and not result.is_cancelled and result.new_key:
            self._new_key = result.new_key
            self._current_key = result.new_key
            self.query_one("#current_key_label", Label).update(
                f"Current key: {result.new_key}"
            )

    @on(Button.Pressed, "#unbind")
    def on_unbind(self) -> None:
        self._new_key = ""
        self._current_key = "(none)"
        self.query_one("#current_key_label", Label).update("Current key: (none)")
        self.query_one("#unbind", Button).disabled = True

    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        palette_cb = self.query_one("#palette_visible", Checkbox)
        self.dismiss(
            ShortcutSettingsResult(
                is_cancelled=False,
                action_name=self._action,
                new_key=self._new_key,
                palette_visible=palette_cb.value,
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(ShortcutSettingsResult(is_cancelled=True))


@dataclass
class FooterConfigResult:
    """Result from the FooterConfigScreen dialog."""

    is_cancelled: bool
    order: list[str] | None = None
    area: str = "editor"


class FooterConfigScreen(ModalScreen[FooterConfigResult]):
    """Modal for configuring which shortcuts appear in the footer and their order."""

    DEFAULT_CSS = """
    FooterConfigScreen {
        align: center middle;
    }
    FooterConfigScreen #dialog {
        padding: 1 2;
        width: 70;
        height: 36;
        border: thick $background 80%;
        background: $surface;
    }
    FooterConfigScreen #title {
        height: 1;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    FooterConfigScreen #hint {
        height: 1;
        color: $text-muted;
        margin-bottom: 1;
    }
    FooterConfigScreen #area_select {
        height: 3;
        margin-bottom: 1;
    }
    FooterConfigScreen #footer_list {
        height: 1fr;
    }
    FooterConfigScreen .action-buttons {
        height: 3;
        margin-top: 1;
        layout: horizontal;
    }
    FooterConfigScreen .action-buttons Button {
        width: 1fr;
        margin: 0 1;
    }
    FooterConfigScreen .confirm-buttons {
        height: 3;
        layout: horizontal;
    }
    FooterConfigScreen .confirm-buttons Button {
        width: 1fr;
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("space", "toggle_item", "Toggle", show=False),
        Binding("ctrl+up", "move_up", "Move up", show=False),
        Binding("ctrl+down", "move_down", "Move down", show=False),
    ]

    _AREA_LABELS: dict[str, str] = {
        "editor": "Editor",
        "explorer": "Explorer",
        "search": "Search",
        "image_preview": "Image Preview",
        "markdown_preview": "Markdown Preview",
    }

    def __init__(
        self,
        all_area_actions: dict[str, list[tuple[str, str, str, bool]]],
        footer_orders: FooterOrders,
        *,
        initial_area: str = "editor",
    ) -> None:
        super().__init__()
        self._all_area_actions = all_area_actions
        self._footer_orders = footer_orders
        self._current_area = initial_area
        # Per-area action lookup: area -> {action_name: (name, desc, key)}
        self._area_action_info: dict[str, dict[str, tuple[str, str, str]]] = {}
        for area, actions in all_area_actions.items():
            self._area_action_info[area] = {a[0]: (a[0], a[1], a[2]) for a in actions}
        # Per-area items state cache
        self._area_items: dict[str, list[tuple[str, bool]]] = {}
        for area, actions in all_area_actions.items():
            self._area_items[area] = self._build_items(area, actions)
        self._items = self._area_items.get(initial_area, [])

    def _build_items(
        self,
        area: str,
        actions: list[tuple[str, str, str, bool]],
    ) -> list[tuple[str, bool]]:
        """Build the ordered (action_name, visible) list for an area."""
        current_order = self._footer_orders.for_area(area)
        if current_order is not None:
            action_set = {a[0] for a in actions}
            visible = set(current_order)
            items: list[tuple[str, bool]] = [
                (a, True) for a in current_order if a in action_set
            ]
            for action_name, _desc, _key, _show in actions:
                if action_name not in visible:
                    items.append((action_name, False))
            return items
        return [(a[0], a[3]) for a in actions]

    @property
    def _actions(self) -> dict[str, tuple[str, str, str]]:
        """Return action info for the current area."""
        return self._area_action_info.get(self._current_area, {})

    def _format_item_text(self, action_name: str, visible: bool) -> str:
        """Format the display text for a footer config list item."""
        info = self._actions.get(action_name)
        if info is None:
            return f" {'✓' if visible else '✗'}  {action_name}"
        _name, desc, key = info
        marker = "\u2713" if visible else "\u2717"
        return f" {marker}  {desc} ({key})"

    def compose(self) -> ComposeResult:
        from textual.widgets import Select

        area_options = [
            (label, area)
            for area, label in self._AREA_LABELS.items()
            if area in self._all_area_actions
        ]
        items = [
            ListItem(Label(self._format_item_text(a, v)), name=a)
            for a, v in self._items
        ]
        yield Vertical(
            Label("Configure Footer Shortcuts", id="title"),
            Select(area_options, value=self._current_area, id="area_select"),
            Label("Space: toggle, Ctrl+Up/Down: reorder", id="hint"),
            ListView(*items, id="footer_list"),
            Horizontal(
                Button("Move Up", variant="default", id="move_up"),
                Button("Move Down", variant="default", id="move_down"),
                Button("Toggle", variant="default", id="toggle"),
                classes="action-buttons",
            ),
            Horizontal(
                Button("Save", variant="primary", id="save"),
                Button("Cancel", variant="default", id="cancel"),
                classes="confirm-buttons",
            ),
            id="dialog",
        )

    @on(Select.Changed, "#area_select")
    def on_area_changed(self, event: Select.Changed) -> None:
        """Switch to a different area, preserving current state."""
        new_area = str(event.value)
        if new_area == self._current_area:
            return
        # Save current area state
        self._area_items[self._current_area] = list(self._items)
        self._current_area = new_area
        self._items = list(self._area_items.get(new_area, []))
        # Rebuild the list view
        list_view = self.query_one("#footer_list", ListView)
        list_view.clear()
        for action_name, visible in self._items:
            text = self._format_item_text(action_name, visible)
            list_view.append(ListItem(Label(text), name=action_name))

    def _update_item_label(self, idx: int) -> None:
        """Update the label of a single list item at the given index."""
        list_view = self.query_one("#footer_list", ListView)
        action_name, visible = self._items[idx]
        item = list_view.children[idx]
        item.query_one(Label).update(self._format_item_text(action_name, visible))

    def action_toggle_item(self) -> None:
        list_view = self.query_one("#footer_list", ListView)
        idx = list_view.index
        if idx is not None and 0 <= idx < len(self._items):
            action_name, visible = self._items[idx]
            self._items[idx] = (action_name, not visible)
            self._update_item_label(idx)

    def action_move_up(self) -> None:
        list_view = self.query_one("#footer_list", ListView)
        idx = list_view.index
        if idx is not None and idx > 0:
            self._items[idx], self._items[idx - 1] = (
                self._items[idx - 1],
                self._items[idx],
            )
            self._update_item_label(idx)
            self._update_item_label(idx - 1)
            list_view.index = idx - 1

    def action_move_down(self) -> None:
        list_view = self.query_one("#footer_list", ListView)
        idx = list_view.index
        if idx is not None and idx < len(self._items) - 1:
            self._items[idx], self._items[idx + 1] = (
                self._items[idx + 1],
                self._items[idx],
            )
            self._update_item_label(idx)
            self._update_item_label(idx + 1)
            list_view.index = idx + 1

    @on(Button.Pressed, "#move_up")
    def on_move_up_btn(self) -> None:
        self.action_move_up()

    @on(Button.Pressed, "#move_down")
    def on_move_down_btn(self) -> None:
        self.action_move_down()

    @on(Button.Pressed, "#toggle")
    def on_toggle_btn(self) -> None:
        self.action_toggle_item()

    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        # Save current area state first
        self._area_items[self._current_area] = list(self._items)
        order = [name for name, visible in self._items if visible]
        self.dismiss(
            FooterConfigResult(is_cancelled=False, order=order, area=self._current_area)
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(FooterConfigResult(is_cancelled=True))


class ShowShortcutsScreen(ModalScreen[None]):
    """Modal that lists all keyboard shortcuts and allows rebinding."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    ShowShortcutsScreen {
        align: center middle;
    }
    ShowShortcutsScreen #dialog {
        padding: 0 1;
        width: 80;
        height: 30;
        border: thick $background 80%;
        background: $surface;
    }
    ShowShortcutsScreen #title {
        height: 1;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    ShowShortcutsScreen #shortcuts_table {
        height: 1fr;
    }
    ShowShortcutsScreen #close {
        margin-top: 1;
        width: 100%;
    }
    """

    def __init__(
        self,
        rows: list[tuple[str, str, str, str]],
        display_config: dict[str, ShortcutDisplayEntry] | None = None,
    ) -> None:
        super().__init__()
        # rows: (key, description, context, action_name)
        self._rows = rows
        self._display_config = display_config or {}

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Keyboard Shortcuts", id="title"),
            DataTable(id="shortcuts_table", cursor_type="row"),
            Button("Close", variant="default", id="close"),
            id="dialog",
        )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Key", "Description", "Context")
        for key, desc, ctx, action in self._rows:
            table.add_row(key, desc, ctx, key=action)

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        action_name = str(event.row_key.value)
        row = next(r for r in self._rows if r[3] == action_name)
        current_key, desc, _ctx, _action = row
        display_entry = self._display_config.get(action_name)
        palette_visible = (
            display_entry.palette
            if display_entry and display_entry.palette is not None
            else True
        )
        self.app.push_screen(
            ShortcutSettingsScreen(
                action_name=action_name,
                description=desc,
                current_key=current_key,
                palette_visible=palette_visible,
            ),
            self._on_settings_result,
        )

    def _on_settings_result(self, result: ShortcutSettingsResult | None) -> None:
        if result is None or result.is_cancelled:
            return
        app = cast("TextualCode", self.app)
        if result.new_key is not None and result.action_name:
            app.set_keybinding(result.action_name, result.new_key)
        if result.action_name:
            from textual_code.config import ShortcutDisplayEntry

            entry = ShortcutDisplayEntry(palette=result.palette_visible)
            app.set_shortcut_display(result.action_name, entry)
            self._display_config[result.action_name] = entry

    @on(Button.Pressed, "#close")
    def on_close(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)
