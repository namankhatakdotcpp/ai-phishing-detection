"""Runs tests_js/popup_behavior_test.mjs, which loads the ACTUAL
extension/popup.html + config.js + popup.js (unmodified) into jsdom with
chrome.* and fetch mocked, and exercises real state transitions: initial
tab-info load (enabled/disabled), successful LOW/HIGH result rendering
(including that a HIGH verdict triggers exactly one overlay injection
call), the distinct offline/503 failure states from this project's
Phase 7 work, and the Retry button.

Skipped gracefully if Node/jsdom aren't set up -- see
tests/test_js_parity.py's docstring and LOCAL_SETUP.md for setup.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
TEST_SCRIPT = REPO_ROOT / "tests_js" / "popup_behavior_test.mjs"
NODE_MODULES = REPO_ROOT / "tests_js" / "node_modules"

_NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(
    _NODE is None or not NODE_MODULES.exists(),
    reason="Node.js and/or tests_js/node_modules (jsdom) not set up -- see LOCAL_SETUP.md",
)


def test_popup_behavior_suite_passes():
    result = subprocess.run(
        [_NODE, str(TEST_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"popup_behavior_test.mjs failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "ALL PASSED" in result.stdout
