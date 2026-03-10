"""
Regex search/replace feature tests.

Behaviour spec:
- use_regex=True → python re 패턴으로 검색
- 잘못된 regex → error notification, 크래시 없음
- (?i) 인라인 플래그로 대소문자 무시 검색 가능
- replace_all에서 캡처 그룹 지원 (\1 등)
- use_regex=False (기본값) → 기존 평범한 문자열 검색 (회귀 없음)
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.code_editor import _find_next

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def regex_file(workspace: Path) -> Path:
    """regex 테스트용 파일."""
    f = workspace / "regex_test.txt"
    f.write_text("hello world\nHELLO WORLD\nfoo123 bar456\n")
    return f


# ── _find_next 단위 테스트 ──────────────────────────────────────────────────────


def test_find_next_plain_returns_tuple():
    """use_regex=False → (start, end) 튜플 반환."""
    text = "hello world"
    start, end = _find_next(text, "world", 0, use_regex=False)
    assert start == 6
    assert end == 11


def test_find_next_plain_not_found_returns_minus_one():
    """use_regex=False → 없으면 (-1, -1) 반환."""
    assert _find_next("hello", "xyz", 0, use_regex=False) == (-1, -1)


def test_find_next_regex_basic():
    """use_regex=True → 패턴 매칭."""
    text = "hello world"
    start, end = _find_next(text, r"he.lo", 0, use_regex=True)
    assert start == 0
    assert end == 5


def test_find_next_regex_not_found():
    """use_regex=True → 패턴 없으면 (-1, -1)."""
    assert _find_next("hello", r"xyz.+", 0, use_regex=True) == (-1, -1)


def test_find_next_regex_wrap_around():
    """use_regex=True → cursor 이후 없으면 처음부터 재검색."""
    text = "abc def abc"
    # cursor_offset=4 (d 위치), 'abc' 는 이후에 offset 8에 있음
    start, end = _find_next(text, r"abc", 4, use_regex=True)
    assert start == 8
    assert end == 11


def test_find_next_regex_wrap_around_from_end():
    """cursor 이후에 없고, 처음에 있으면 처음 것을 반환."""
    text = "abc def"
    # cursor_offset=4 → 'abc'는 cursor 이후에 없음 → wrap → offset 0
    start, end = _find_next(text, r"abc", 4, use_regex=True)
    assert start == 0
    assert end == 3


def test_find_next_invalid_regex_raises():
    """잘못된 regex → re.error 발생."""
    import re

    with pytest.raises(re.error):
        _find_next("hello", r"[unclosed", 0, use_regex=True)


# ── regex find 통합 테스트 ──────────────────────────────────────────────────────


async def test_regex_find_matches_dot_pattern(workspace: Path, regex_file: Path):
    """he.lo 패턴으로 hello를 선택한다."""
    app = make_app(workspace, open_file=regex_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        input_widget = app.screen.query_one("#query")
        await pilot.click(input_widget)
        await pilot.press("h", "e", ".", "l", "o")
        await pilot.click("#find")
        await pilot.pause()

        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_regex_find_no_match_shows_warning(workspace: Path, regex_file: Path):
    """매칭 없는 regex → 커서 이동 없음 (not found)."""
    app = make_app(workspace, open_file=regex_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_find()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        input_widget = app.screen.query_one("#query")
        await pilot.click(input_widget)
        await pilot.press("x", "y", "z", ".", "+")
        await pilot.click("#find")
        await pilot.pause()

        assert editor.editor.cursor_location == original_location


async def test_regex_find_wrap_around(workspace: Path, regex_file: Path):
    """커서 끝에서 regex 검색 → wrap-around로 처음 매치를 찾는다."""
    app = make_app(workspace, open_file=regex_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # 마지막 라인으로 커서 이동
        editor.editor.cursor_location = (2, 0)
        await pilot.pause()

        editor.action_find()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        input_widget = app.screen.query_one("#query")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#find")
        await pilot.pause()

        sel = editor.editor.selection
        # wrap-around → 첫 번째 'hello' at (0, 0)
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_invalid_regex_find_shows_error(workspace: Path, regex_file: Path):
    """잘못된 regex → error notification, 크래시 없음."""
    app = make_app(workspace, open_file=regex_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_find()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        input_widget = app.screen.query_one("#query")
        await pilot.click(input_widget)
        # "[unclosed" → re.error
        await pilot.press("[")
        await pilot.click("#find")
        await pilot.pause()

        # 크래시 없음 + 커서 이동 없음
        assert editor.editor.cursor_location == original_location


async def test_regex_find_case_insensitive_inline(workspace: Path, regex_file: Path):
    """(?i)hello → HELLO도 선택된다."""
    # regex_file: "hello world\nHELLO WORLD\nfoo123 bar456\n"
    app = make_app(workspace, open_file=regex_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # 커서를 첫 'hello' 이후로 이동해서 두 번째 'HELLO'를 찾도록
        editor.editor.cursor_location = (1, 0)
        await pilot.pause()

        editor.action_find()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        input_widget = app.screen.query_one("#query")
        await pilot.click(input_widget)
        for ch in "(?i)hello":
            await pilot.press(ch)
        await pilot.click("#find")
        await pilot.pause()

        sel = editor.editor.selection
        # 커서가 (1,0)이므로 (1,0)부터 검색 → HELLO at (1,0)–(1,5)
        assert sel.start == (1, 0)
        assert sel.end == (1, 5)


async def test_plain_find_regression(workspace: Path, regex_file: Path):
    """use_regex 체크 없음 → 기존 평범한 검색 동작 유지."""
    app = make_app(workspace, open_file=regex_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.pause()

        # use_regex 체크 안 함
        input_widget = app.screen.query_one("#query")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#find")
        await pilot.pause()

        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


# ── regex replace_all 통합 테스트 ─────────────────────────────────────────────


async def test_regex_replace_all_basic(workspace: Path, regex_file: Path):
    r"""\d+ → [NUM] 전체 치환."""
    app = make_app(workspace, open_file=regex_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        await pilot.click("#find_query")
        await pilot.press("\\", "d", "+")
        await pilot.click("#replace_text")
        await pilot.press("[", "N", "U", "M", "]")
        await pilot.click("#replace_all")
        await pilot.pause()

        # "foo123 bar456" → "foo[NUM] bar[NUM]"
        assert "[NUM]" in editor.text
        assert "123" not in editor.text
        assert "456" not in editor.text


async def test_regex_replace_all_capture_group(workspace: Path):
    r"""(\w+) → [\1] 캡처 그룹 치환."""
    f = workspace / "capture.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        await pilot.click("#find_query")
        # pattern: (\w+)
        await pilot.press("(", "\\", "w", "+", ")")
        await pilot.click("#replace_text")
        # replacement: [\1]
        await pilot.press("[", "\\", "1", "]")
        await pilot.click("#replace_all")
        await pilot.pause()

        assert "[hello]" in editor.text
        assert "[world]" in editor.text


async def test_invalid_regex_replace_all_error(workspace: Path, regex_file: Path):
    """잘못된 regex replace_all → error notification, 텍스트 변경 없음."""
    app = make_app(workspace, open_file=regex_file)
    original_text = regex_file.read_text()
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        await pilot.click("#find_query")
        await pilot.press("[")
        await pilot.click("#replace_text")
        await pilot.press("x")
        await pilot.click("#replace_all")
        await pilot.pause()

        # 텍스트 변경 없음
        assert editor.text == original_text


# ── regex replace single 통합 테스트 ──────────────────────────────────────────


async def test_regex_replace_single_match_replaces(workspace: Path):
    r"""선택이 fullmatch → 치환 후 다음 매치 선택."""
    f = workspace / "single_rep.txt"
    f.write_text("foo123 foo456\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # 먼저 foo123을 선택
        from textual.widgets.text_area import Selection

        editor.editor.selection = Selection(start=(0, 0), end=(0, 6))
        await pilot.pause()

        editor.action_replace()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        await pilot.click("#find_query")
        await pilot.press("f", "o", "o", "\\", "d", "+")
        await pilot.click("#replace_text")
        await pilot.press("X")
        await pilot.click("#replace")
        await pilot.pause()

        # foo123 → X, 그 후 foo456 선택됨
        assert "X" in editor.text
        assert "foo123" not in editor.text


async def test_regex_replace_single_no_match_finds(workspace: Path):
    """선택이 불일치 → 다음 regex 매치를 선택만 한다."""
    f = workspace / "no_match_sel.txt"
    f.write_text("hello foo123\n")
    app = make_app(workspace, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # cursor는 처음에 있고 선택 없음 (selected_text != "foo\d+")
        editor.action_replace()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        await pilot.click("#find_query")
        await pilot.press("f", "o", "o", "\\", "d", "+")
        await pilot.click("#replace_text")
        await pilot.press("X")
        await pilot.click("#replace")
        await pilot.pause()

        sel = editor.editor.selection
        # foo123 at (0, 6)–(0, 12) 가 선택돼야 함
        assert sel.start == (0, 6)
        assert sel.end == (0, 12)
        # 텍스트는 아직 변경 안 됨
        assert "foo123" in editor.text


async def test_invalid_regex_replace_single_error(workspace: Path, regex_file: Path):
    """잘못된 regex replace single → error notification, 텍스트 변경 없음."""
    app = make_app(workspace, open_file=regex_file)
    original_text = regex_file.read_text()
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = app.screen.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        await pilot.click("#find_query")
        await pilot.press("[")
        await pilot.click("#replace_text")
        await pilot.press("x")
        await pilot.click("#replace")
        await pilot.pause()

        # 텍스트 변경 없음
        assert editor.text == original_text
