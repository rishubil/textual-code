"""Tests for the license-checking script (scripts/check-licenses.sh)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="bash not available on Windows"
)


@pytest.fixture(scope="module")
def license_check_result() -> subprocess.CompletedProcess[str]:
    """Run check-licenses.sh once and share the result across tests."""
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run(
        ["bash", "scripts/check-licenses.sh"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=120,
    )


def test_rich_pixels_not_unknown(
    license_check_result: subprocess.CompletedProcess[str],
) -> None:
    """rich-pixels should be classified as allowed, not unknown."""
    assert "rich-pixels" not in license_check_result.stdout, (
        "rich-pixels should be allowed, but appears in output (likely unknown)"
    )


def test_exit_code_zero(
    license_check_result: subprocess.CompletedProcess[str],
) -> None:
    """Script exits 0 when no blocked licenses are found."""
    assert license_check_result.returncode == 0, (
        f"Expected exit 0, got {license_check_result.returncode}. "
        f"stderr: {license_check_result.stderr}"
    )


def test_no_unknown_packages(
    license_check_result: subprocess.CompletedProcess[str],
) -> None:
    """All packages should be classified (no unknowns)."""
    assert "Unknown packages" not in license_check_result.stdout, (
        f"Found unknown packages in output:\n{license_check_result.stdout}"
    )
