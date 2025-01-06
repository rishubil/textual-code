import contextlib
from collections.abc import Iterable
from functools import partial

from textual.app import App
from textual.message import Message
from textual.widget import Widget


@contextlib.contextmanager
def ready_to_handle(
    target: Widget | App, event: Message, should_exists: Iterable | None = None
):
    event.stop()
    is_ready = target.is_attached if isinstance(target, App) else target.is_mounted
    if (not is_ready) or (should_exists is not None and not all(should_exists)):
        # recycle event to be handled later
        callback = partial(target.post_message, event)
        target.set_timer(delay=0.05, callback=callback)
        return
    yield
