"""Runs tests_js/overlay_behavior_test.mjs, which exercises the ACTUAL
extension/page_overlay.js source (not a reimplementation) via jsdom:
initial focus, the Tab focus trap, Escape-to-dismiss, "Continue anyway"
session persistence, and re-invocation replacing a prior overlay.

Skipped gracefully if Node/jsdom aren't set up -- see
tests/test_js_parity.py's docstring and LOCAL_SETUP.md for setup.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
TEST_SCRIPT = REPO_ROOT / "tests_js" / "overlay_behavior_test.mjs"
NODE_MODULES = REPO_ROOT / "tests_js" / "node_modules"

_NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(
    _NODE is None or not NODE_MODULES.exists(),
    reason="Node.js and/or tests_js/node_modules (jsdom) not set up -- see LOCAL_SETUP.md",
)


def test_overlay_behavior_suite_passes():
    result = subprocess.run(
        [_NODE, str(TEST_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"overlay_behavior_test.mjs failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "ALL PASSED" in result.stdout
