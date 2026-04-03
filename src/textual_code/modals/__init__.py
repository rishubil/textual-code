"""Modal dialog screens for textual-code.

Re-exports all modal classes for backward compatibility.
"""

from __future__ import annotations

from textual_code.modals.appearance import (
    AVAILABLE_SYNTAX_THEMES as AVAILABLE_SYNTAX_THEMES,
)
from textual_code.modals.appearance import (
    ChangeSyntaxThemeModalResult as ChangeSyntaxThemeModalResult,
)
from textual_code.modals.appearance import (
    ChangeSyntaxThemeModalScreen as ChangeSyntaxThemeModalScreen,
)
from textual_code.modals.appearance import (
    ChangeUIThemeModalResult as ChangeUIThemeModalResult,
)
from textual_code.modals.appearance import (
    ChangeUIThemeModalScreen as ChangeUIThemeModalScreen,
)
from textual_code.modals.appearance import (
    ChangeWordWrapModalResult as ChangeWordWrapModalResult,
)
from textual_code.modals.appearance import (
    ChangeWordWrapModalScreen as ChangeWordWrapModalScreen,
)
from textual_code.modals.editor_config import (
    ChangeEncodingModalResult as ChangeEncodingModalResult,
)
from textual_code.modals.editor_config import (
    ChangeEncodingModalScreen as ChangeEncodingModalScreen,
)
from textual_code.modals.editor_config import (
    ChangeIndentModalResult as ChangeIndentModalResult,
)
from textual_code.modals.editor_config import (
    ChangeIndentModalScreen as ChangeIndentModalScreen,
)
from textual_code.modals.editor_config import (
    ChangeLanguageModalResult as ChangeLanguageModalResult,
)
from textual_code.modals.editor_config import (
    ChangeLanguageModalScreen as ChangeLanguageModalScreen,
)
from textual_code.modals.editor_config import (
    ChangeLineEndingModalResult as ChangeLineEndingModalResult,
)
from textual_code.modals.editor_config import (
    ChangeLineEndingModalScreen as ChangeLineEndingModalScreen,
)
from textual_code.modals.editor_config import (
    GotoLineModalResult as GotoLineModalResult,
)
from textual_code.modals.editor_config import (
    GotoLineModalScreen as GotoLineModalScreen,
)
from textual_code.modals.file_ops import (
    DeleteFileModalResult as DeleteFileModalResult,
)
from textual_code.modals.file_ops import (
    DeleteFileModalScreen as DeleteFileModalScreen,
)
from textual_code.modals.file_ops import (
    DiscardAndReloadModalResult as DiscardAndReloadModalResult,
)
from textual_code.modals.file_ops import (
    DiscardAndReloadModalScreen as DiscardAndReloadModalScreen,
)
from textual_code.modals.file_ops import (
    LargeFileConfirmModalResult as LargeFileConfirmModalResult,
)
from textual_code.modals.file_ops import (
    LargeFileConfirmModalScreen as LargeFileConfirmModalScreen,
)
from textual_code.modals.file_ops import (
    OverwriteConfirmModalResult as OverwriteConfirmModalResult,
)
from textual_code.modals.file_ops import (
    OverwriteConfirmModalScreen as OverwriteConfirmModalScreen,
)
from textual_code.modals.file_ops import (
    RenameModalResult as RenameModalResult,
)
from textual_code.modals.file_ops import (
    RenameModalScreen as RenameModalScreen,
)
from textual_code.modals.file_ops import (
    SaveAsModalResult as SaveAsModalResult,
)
from textual_code.modals.file_ops import (
    SaveAsModalScreen as SaveAsModalScreen,
)
from textual_code.modals.file_ops import (
    UnsavedChangeModalResult as UnsavedChangeModalResult,
)
from textual_code.modals.file_ops import (
    UnsavedChangeModalScreen as UnsavedChangeModalScreen,
)
from textual_code.modals.file_ops import (
    UnsavedChangeQuitModalResult as UnsavedChangeQuitModalResult,
)
from textual_code.modals.file_ops import (
    UnsavedChangeQuitModalScreen as UnsavedChangeQuitModalScreen,
)
from textual_code.modals.find_replace import (
    FindModalResult as FindModalResult,
)
from textual_code.modals.find_replace import (
    FindModalScreen as FindModalScreen,
)
from textual_code.modals.find_replace import (
    ReplaceModalResult as ReplaceModalResult,
)
from textual_code.modals.find_replace import (
    ReplaceModalScreen as ReplaceModalScreen,
)
from textual_code.modals.find_replace import (
    ReplacePreviewResult as ReplacePreviewResult,
)
from textual_code.modals.find_replace import (
    ReplacePreviewScreen as ReplacePreviewScreen,
)
from textual_code.modals.layout import (
    SidebarResizeModalResult as SidebarResizeModalResult,
)
from textual_code.modals.layout import (
    SidebarResizeModalScreen as SidebarResizeModalScreen,
)
from textual_code.modals.layout import (
    SplitResizeModalResult as SplitResizeModalResult,
)
from textual_code.modals.layout import (
    SplitResizeModalScreen as SplitResizeModalScreen,
)
from textual_code.modals.search import (
    _MAX_DISCOVERY as _MAX_DISCOVERY,
)
from textual_code.modals.search import (
    PathSearchModal as PathSearchModal,
)
from textual_code.modals.search import (
    _adjust_score_for_path as _adjust_score_for_path,
)
from textual_code.modals.shortcuts_config import (
    FooterConfigResult as FooterConfigResult,
)
from textual_code.modals.shortcuts_config import (
    FooterConfigScreen as FooterConfigScreen,
)
from textual_code.modals.shortcuts_config import (
    RebindKeyScreen as RebindKeyScreen,
)
from textual_code.modals.shortcuts_config import (
    RebindResult as RebindResult,
)
from textual_code.modals.shortcuts_config import (
    ShortcutSettingsResult as ShortcutSettingsResult,
)
from textual_code.modals.shortcuts_config import (
    ShortcutSettingsScreen as ShortcutSettingsScreen,
)
from textual_code.modals.shortcuts_config import (
    ShowShortcutsScreen as ShowShortcutsScreen,
)
