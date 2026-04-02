"""
VSCode case transformation tests ported from linesOperations.test.ts.

Source: src/vs/editor/contrib/linesOperations/test/browser/linesOperations.test.ts
Lines: 902-1363 ('toggle case' test block)

Our editor supports all 7 transforms: uppercase, lowercase, title case,
snake_case, camelCase, kebab-case, PascalCase (via command palette).

Collapsed cursor behavior matches VSCode: auto-selects the word under
the cursor and transforms it.
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app
from textual_code.widgets.multi_cursor_text_area import (
    _to_camel_case,
    _to_kebab_case,
    _to_pascal_case,
    _to_snake_case,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_ta(app):
    """Return the MultiCursorTextArea from the active code editor."""
    return app.main_view.get_active_code_editor().editor


# ── Uppercase: VSCode assertions (lines 932-935, 957-960) ────────────────────


@pytest.mark.asyncio
async def test_uppercase_full_line(workspace: Path):
    """VSCode L932-935: select full line 'hello world' → 'HELLO WORLD'."""
    f = workspace / "case.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "HELLO WORLD"
        # Selection must be preserved (VSCode L935)
        assert ta.selection == Selection((0, 0), (0, 11))


@pytest.mark.asyncio
async def test_uppercase_unicode(workspace: Path):
    """VSCode L957-960: Unicode 'öçşğü' → 'ÖÇŞĞÜ'."""
    f = workspace / "unicode.txt"
    f.write_text("öçşğü\n", encoding="utf-8")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 5))
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "ÖÇŞĞÜ"
        assert ta.selection == Selection((0, 0), (0, 5))


# ── Lowercase: VSCode assertions (lines 937-940, 962-965) ────────────────────


@pytest.mark.asyncio
async def test_lowercase_full_line(workspace: Path):
    """VSCode L937-940: select 'HELLO WORLD' → 'hello world'."""
    f = workspace / "case.txt"
    f.write_text("HELLO WORLD\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_lowercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "hello world"
        assert ta.selection == Selection((0, 0), (0, 11))


@pytest.mark.asyncio
async def test_lowercase_unicode(workspace: Path):
    """VSCode L962-965: Unicode 'ÖÇŞĞÜ' → 'öçşğü'."""
    f = workspace / "unicode.txt"
    f.write_text("ÖÇŞĞÜ\n", encoding="utf-8")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 5))
        ta.action_transform_lowercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "öçşğü"
        assert ta.selection == Selection((0, 0), (0, 5))


# ── Round-trip: VSCode L932-940 combined ─────────────────────────────────────


@pytest.mark.asyncio
async def test_uppercase_then_lowercase_round_trip(workspace: Path):
    """VSCode L932-940: 'hello world' → uppercase → lowercase returns original."""
    f = workspace / "case.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))

        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "HELLO WORLD"

        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_lowercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "hello world"


# ── Idempotency ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_uppercase_idempotent(workspace: Path):
    """Applying uppercase to already-uppercase text is a no-op."""
    f = workspace / "case.txt"
    f.write_text("HELLO WORLD\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "HELLO WORLD"


@pytest.mark.asyncio
async def test_lowercase_idempotent(workspace: Path):
    """Applying lowercase to already-lowercase text is a no-op."""
    f = workspace / "case.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_lowercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "hello world"


# ── Whitespace / empty: VSCode L1150-1178 ───────────────────────────────────


@pytest.mark.asyncio
async def test_uppercase_whitespace_only_selection(workspace: Path):
    """VSCode L1169-1172: selecting whitespace and transforming preserves it."""
    f = workspace / "space.txt"
    f.write_text("   \n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 3))
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "   "


@pytest.mark.asyncio
async def test_uppercase_mixed_alphanumeric(workspace: Path):
    """Numbers and special characters are unaffected by uppercase."""
    f = workspace / "mixed.txt"
    f.write_text("test123!@#abc\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 13))
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "TEST123!@#ABC"


# ── Collapsed cursor word transform: matches VSCode ─────────────────────────
# VSCode L942-950: collapsed cursor auto-selects the word and transforms it.


@pytest.mark.asyncio
async def test_collapsed_cursor_uppercase_word(workspace: Path):
    """VSCode L942-945: collapsed cursor at col 2 in 'hello world' uppercases
    the word under cursor → 'HELLO world'.
    """
    f = workspace / "case.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.cursor_location = (0, 2)
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "HELLO world"


@pytest.mark.asyncio
async def test_collapsed_cursor_lowercase_word(workspace: Path):
    """VSCode L947-950: collapsed cursor at col 3 in 'HELLO world' lowercases
    the word under cursor → 'hello world'.
    """
    f = workspace / "case.txt"
    f.write_text("HELLO world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.cursor_location = (0, 3)
        ta.action_transform_lowercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "hello world"


# ── Title case ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_title_case_full_line(workspace: Path):
    """Title case: 'hello world' → 'Hello World'."""
    f = workspace / "case.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.selection = Selection((0, 0), (0, 11))
        ta.action_transform_title_case()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "Hello World"
        assert ta.selection == Selection((0, 0), (0, 11))


@pytest.mark.asyncio
async def test_title_case_collapsed_cursor(workspace: Path):
    """Title case with collapsed cursor auto-selects word."""
    f = workspace / "case.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_ta(app)
        ta.cursor_location = (0, 2)
        ta.action_transform_title_case()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "Hello world"


# ── Snake case unit tests: VSCode L972-1049 ──────────────────────────────────


class TestToSnakeCase:
    """Port of VSCode snake_case assertions from linesOperations.test.ts."""

    def test_camel_case(self):
        assert _to_snake_case("parseHTMLString") == "parse_html_string"

    def test_camel_case_2(self):
        assert _to_snake_case("getElementById") == "get_element_by_id"

    def test_leading_upper(self):
        assert _to_snake_case("insertHTML") == "insert_html"

    def test_pascal_case(self):
        assert _to_snake_case("PascalCase") == "pascal_case"

    def test_consecutive_upper(self):
        assert _to_snake_case("CSSSelectorsList") == "css_selectors_list"

    def test_two_char(self):
        assert _to_snake_case("iD") == "i_d"

    def test_upper_prefix(self):
        assert _to_snake_case("tEST") == "t_est"

    def test_unicode(self):
        assert _to_snake_case("öçşÖÇŞğüĞÜ") == "öçş_öç_şğü_ğü"

    def test_preserves_non_alpha(self):
        assert (
            _to_snake_case("audioConverter.convertM4AToMP3();")
            == "audio_converter.convert_m4a_to_mp3();"
        )

    def test_idempotent(self):
        assert _to_snake_case("snake_case") == "snake_case"

    def test_capital_snake(self):
        assert _to_snake_case("Capital_Snake_Case") == "capital_snake_case"

    def test_multiline(self):
        text = (
            "function helloWorld() {\n"
            'return someGlobalObject.printHelloWorld("en", "utf-8");\n'
            "}\n"
            "helloWorld();"
        )
        expected = (
            "function hello_world() {\n"
            'return some_global_object.print_hello_world("en", "utf-8");\n'
            "}\n"
            "hello_world();"
        )
        assert _to_snake_case(text) == expected

    def test_quoted(self):
        assert _to_snake_case("'JavaScript'") == "'java_script'"

    def test_digits(self):
        assert _to_snake_case("parseHTML4String") == "parse_html4_string"

    def test_leading_underscore(self):
        assert (
            _to_snake_case("_accessor: ServicesAccessor")
            == "_accessor: services_accessor"
        )


# ── Camel case unit tests: VSCode L1095-1148 ─────────────────────────────────


class TestToCamelCase:
    """Port of VSCode camelCase assertions from linesOperations.test.ts."""

    def test_from_words(self):
        assert _to_camel_case("camel from words") == "camelFromWords"

    def test_from_snake(self):
        assert _to_camel_case("from_snake_case") == "fromSnakeCase"

    def test_from_kebab(self):
        assert _to_camel_case("from-kebab-case") == "fromKebabCase"

    def test_already_camel(self):
        assert _to_camel_case("alreadyCamel") == "alreadyCamel"

    def test_retain_caps(self):
        assert (
            _to_camel_case("ReTain_some_CAPitalization") == "reTainSomeCAPitalization"
        )

    def test_preserves_non_alpha(self):
        assert _to_camel_case("my_var.test_function()") == "myVar.testFunction()"

    def test_unicode(self):
        assert _to_camel_case("öçş_öç_şğü_ğü") == "öçşÖçŞğüĞü"

    def test_already_upper_acronym(self):
        assert _to_camel_case("XMLHttpRequest") == "XMLHttpRequest"

    def test_multiline_with_tabs(self):
        text = "\tfunction hello_world() {\n\t\treturn some_global_object;\n\t}"
        expected = "\tfunction helloWorld() {\n\t\treturn someGlobalObject;\n\t}"
        assert _to_camel_case(text) == expected


# ── Kebab case unit tests: VSCode L1181-1253 ─────────────────────────────────


class TestToKebabCase:
    """Port of VSCode kebab-case assertions from linesOperations.test.ts."""

    def test_words_unchanged(self):
        assert _to_kebab_case("hello world") == "hello world"

    def test_unicode_unchanged(self):
        assert _to_kebab_case("öçşğü") == "öçşğü"

    def test_camel_case(self):
        assert _to_kebab_case("parseHTMLString") == "parse-html-string"

    def test_camel_case_2(self):
        assert _to_kebab_case("getElementById") == "get-element-by-id"

    def test_pascal_case(self):
        assert _to_kebab_case("PascalCase") == "pascal-case"

    def test_unicode_mixed(self):
        assert _to_kebab_case("öçşÖÇŞğüĞÜ") == "öçş-öç-şğü-ğü"

    def test_preserves_non_alpha(self):
        assert (
            _to_kebab_case("audioConverter.convertM4AToMP3();")
            == "audio-converter.convert-m4a-to-mp3();"
        )

    def test_from_snake(self):
        assert _to_kebab_case("Capital_Snake_Case") == "capital-snake-case"

    def test_digits(self):
        assert _to_kebab_case("parseHTML4String") == "parse-html4-string"

    def test_leading_underscore(self):
        assert (
            _to_kebab_case("_accessor: ServicesAccessor")
            == "_accessor: services-accessor"
        )

    def test_idempotent(self):
        assert _to_kebab_case("Kebab-Case") == "kebab-case"


# ── Pascal case unit tests: VSCode L1255-1363 ────────────────────────────────


class TestToPascalCase:
    """Port of VSCode PascalCase assertions from linesOperations.test.ts."""

    def test_from_words(self):
        assert _to_pascal_case("hello world") == "HelloWorld"

    def test_unicode_unchanged(self):
        assert _to_pascal_case("öçşğü") == "Öçşğü"

    def test_from_camel(self):
        assert _to_pascal_case("parseHTMLString") == "ParseHTMLString"

    def test_from_camel_2(self):
        assert _to_pascal_case("getElementById") == "GetElementById"

    def test_already_pascal(self):
        assert _to_pascal_case("PascalCase") == "PascalCase"

    def test_unicode_mixed(self):
        assert _to_pascal_case("öçşÖÇŞğüĞÜ") == "ÖçşÖÇŞğüĞÜ"

    def test_preserves_non_alpha(self):
        assert (
            _to_pascal_case("audioConverter.ConvertM4AToMP3();")
            == "AudioConverter.ConvertM4AToMP3();"
        )

    def test_from_capital_snake(self):
        assert _to_pascal_case("Capital_Snake_Case") == "CapitalSnakeCase"

    def test_digits(self):
        assert _to_pascal_case("parseHTML4String") == "ParseHTML4String"

    def test_from_kebab(self):
        assert _to_pascal_case("Kebab-Case") == "KebabCase"

    def test_all_caps_underscore(self):
        assert _to_pascal_case("FOO_BAR") == "FooBar"

    def test_all_caps_spaces(self):
        assert _to_pascal_case("FOO BAR A") == "FooBarA"

    def test_mixed_separators(self):
        assert _to_pascal_case("xML_HTTP-reQUEsT") == "XmlHttpReQUEsT"

    def test_unicode_ecole(self):
        assert _to_pascal_case("ÉCOLE") == "École"

    def test_unicode_omega(self):
        assert _to_pascal_case("ΩMEGA_CASE") == "ΩmegaCase"

    def test_unicode_cyrillic(self):
        assert _to_pascal_case("ДОМ_ТЕСТ") == "ДомТест"
