"""Tests for encoding safety on non-UTF-8 locales (e.g. Windows cp949).

These tests verify that file I/O with explicit encoding="utf-8" works correctly
even when the system locale defaults to a narrow encoding like cp949.  They
serve as regression guards so that encoding bugs caught in issue #177 do not
recur on CI environments where the locale is already UTF-8.

Mechanism: monkeypatch ``io.text_encoding`` so that ``None`` (the default when
no encoding is specified) resolves to ``"cp949"`` instead of ``"locale"``.
Because ``pathlib.Path.write_text`` / ``read_text`` call
``io.text_encoding(encoding)`` before opening the file, this faithfully
simulates what happens on a Korean-locale Windows machine.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Non-ASCII content patterns taken from the failing tests in issue #177
# ---------------------------------------------------------------------------

NON_ASCII_CONTENTS = [
    pytest.param("öçşğü\n", id="turkish-lower"),
    pytest.param("ÖÇŞĞÜ\n", id="turkish-upper"),
    pytest.param("'👁'", id="emoji-eye"),
    pytest.param("    Third Line\U0001f436\n", id="emoji-dog"),
    pytest.param(
        "    \tMy First Line\t \n\tMy Second Line\n    Third Line\U0001f436\n\n1\n",
        id="mixed-with-emoji",
    ),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def simulate_cp949(monkeypatch: pytest.MonkeyPatch):
    """Simulate a cp949 locale by patching ``io.text_encoding``.

    After this patch, any ``Path.write_text()`` / ``Path.read_text()`` call
    that omits the ``encoding`` parameter will behave as if the system
    default encoding is cp949.
    """
    original = io.text_encoding

    def cp949_text_encoding(encoding, _stacklevel=2):
        if encoding is None:
            return "cp949"
        return original(encoding, _stacklevel)

    monkeypatch.setattr(io, "text_encoding", cp949_text_encoding)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCp949CannotEncodeNonAscii:
    """Verify that cp949 encoding rejects the content used in our tests."""

    def test_cp949_cannot_encode_emoji(self):
        """cp949 cannot represent emoji characters — the root cause of #177."""
        with pytest.raises(UnicodeEncodeError):
            "🐶".encode("cp949")

    def test_cp949_cannot_encode_turkish(self):
        """cp949 cannot represent Turkish special characters (ş, ğ)."""
        with pytest.raises(UnicodeEncodeError):
            "şğ".encode("cp949")


class TestWriteReadWithUtf8OnCp949:
    """write_text + read_text with explicit encoding='utf-8' must work."""

    @pytest.mark.parametrize("content", NON_ASCII_CONTENTS)
    def test_write_read_roundtrip(self, tmp_path: Path, simulate_cp949, content: str):
        """Round-trip: write with utf-8, read with utf-8 — content intact."""
        f = tmp_path / "test.txt"
        f.write_text(content, encoding="utf-8")
        assert f.read_text(encoding="utf-8") == content


class TestReadWithoutUtf8FailsOnCp949:
    """Reading UTF-8 emoji bytes as cp949 must fail."""

    def test_read_emoji_bytes_as_cp949_raises(self, tmp_path: Path):
        """UTF-8 emoji bytes are invalid cp949 — UnicodeDecodeError expected."""
        f = tmp_path / "emoji.txt"
        f.write_bytes("🐶".encode())
        with pytest.raises(UnicodeDecodeError):
            f.read_text(encoding="cp949")


class TestSvgContentOnCp949:
    """Simulate the test_app.py screenshot scenario."""

    def test_svg_with_multibyte_chars(self, tmp_path: Path, simulate_cp949):
        """SVG content with multi-byte UTF-8 can be written and read back."""
        svg = '<svg class="test"><!-- multi-byte \u00e9\u00f6\u00fc 🎨 --></svg>'
        f = tmp_path / "screenshot.svg"
        f.write_text(svg, encoding="utf-8")
        content = f.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "🎨" in content
