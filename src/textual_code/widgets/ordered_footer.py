"""Footer with deterministic shortcut display order.

Subclasses Textual's Footer to sort bindings by a predefined priority list,
ensuring important shortcuts (Save, Find, etc.) always appear first regardless
of which widget is focused.

Based on Textual 8.0.2 Footer.compose() (_footer.py:266-328).
"""

from __future__ import annotations

from collections import defaultdict
from itertools import groupby

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer
from textual.widgets._footer import FooterKey, FooterLabel, KeyGroup


class OrderedFooter(Footer):
    """Footer that displays shortcuts in a fixed, deterministic order."""

    # Display priority order for actions.  Actions not listed here appear at
    # the end, preserving their original relative order (stable sort).
    ACTION_ORDER: tuple[str, ...] = (
        "save",
        "find",
        "replace",
        "goto_line",
        "close_editor",
        "open_file",
        "new_untitled_file",
        "toggle_sidebar",
    )

    # Per-area default action orders used when no custom order is configured.
    DEFAULT_ACTION_ORDERS: dict[str, tuple[str, ...]] = {
        "editor": ACTION_ORDER,
        "explorer": (
            "create_file",
            "create_directory",
            "delete_node",
            "rename_node",
            "open_file",
            "new_untitled_file",
            "toggle_sidebar",
        ),
        "search": (
            "open_file",
            "new_untitled_file",
            "toggle_sidebar",
        ),
        "image_preview": (
            "close_editor",
            "open_file",
            "new_untitled_file",
            "toggle_sidebar",
        ),
        "markdown_preview": (
            "close_editor",
            "open_file",
            "new_untitled_file",
            "toggle_sidebar",
        ),
    }

    def _should_show_in_footer(self, binding: Binding) -> bool:
        """Check if a binding should appear in the footer.

        Uses the area-aware order from the app (always non-None).
        Falls back to binding.show for non-TextualCode apps.
        """
        from textual_code.app import TextualCode

        app = self.app
        if isinstance(app, TextualCode):
            order = app.get_footer_order()
            return binding.action in order
        return binding.show

    def _action_sort_key(self, action: str) -> int:
        from textual_code.app import TextualCode

        app = self.app
        if isinstance(app, TextualCode):
            return app.get_footer_priority(action)
        try:
            return self.ACTION_ORDER.index(action)
        except ValueError:
            return len(self.ACTION_ORDER)

    def compose(self) -> ComposeResult:
        # Adapted from Footer.compose() in Textual 8.0.2 (_footer.py:266-328).
        # Only change: action_to_bindings values are sorted by ACTION_ORDER
        # before the groupby iteration.
        if not self._bindings_ready:
            return
        active_bindings = self.screen.active_bindings
        bindings = []
        for _, binding, enabled, tooltip in active_bindings.values():
            show = self._should_show_in_footer(binding)
            if show:
                bindings.append((binding, enabled, tooltip))
        action_to_bindings: defaultdict[str, list[tuple[Binding, bool, str]]]
        action_to_bindings = defaultdict(list)
        for binding, enabled, tooltip in bindings:
            action_to_bindings[binding.action].append((binding, enabled, tooltip))

        self.styles.grid_size_columns = len(action_to_bindings)

        # Sort by predefined priority order.
        # Note: groupby groups consecutive items by binding.group.  After
        # sorting, items of the same group may no longer be consecutive.
        # This is safe because all current bindings use group=None.
        sorted_values = sorted(
            action_to_bindings.values(),
            key=lambda bl: self._action_sort_key(bl[0][0].action),
        )

        for group, multi_bindings_iterable in groupby(
            sorted_values,
            lambda multi_bindings_: multi_bindings_[0][0].group,
        ):
            multi_bindings_list = list(multi_bindings_iterable)
            if group is not None and len(multi_bindings_list) > 1:
                with KeyGroup(classes="-compact" if group.compact else ""):
                    for entry in multi_bindings_list:
                        binding, enabled, tooltip = entry[0]
                        yield FooterKey(
                            binding.key,
                            self.app.get_key_display(binding),
                            "",
                            binding.action,
                            disabled=not enabled,
                            tooltip=tooltip or binding.description,
                            classes="-grouped",
                        ).data_bind(compact=Footer.compact)
                yield FooterLabel(group.description)
            else:
                for entry in multi_bindings_list:
                    binding, enabled, tooltip = entry[0]
                    yield FooterKey(
                        binding.key,
                        self.app.get_key_display(binding),
                        binding.description,
                        binding.action,
                        disabled=not enabled,
                        tooltip=tooltip,
                    ).data_bind(compact=Footer.compact)
        if self.show_command_palette and self.app.ENABLE_COMMAND_PALETTE:
            try:
                _node, binding, enabled, tooltip = active_bindings[
                    self.app.COMMAND_PALETTE_BINDING
                ]
            except KeyError:
                pass
            else:
                yield FooterKey(
                    binding.key,
                    self.app.get_key_display(binding),
                    binding.description,
                    binding.action,
                    classes="-command-palette",
                    disabled=not enabled,
                    tooltip=binding.tooltip or binding.description,
                )
