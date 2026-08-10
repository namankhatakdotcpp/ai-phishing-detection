"""Build a clean Chrome Web Store submission package from extension/.

Copies only the files Chrome actually needs into release/, validates
that nothing else (backend code, secrets, datasets, this repo's git
history) made it in, and zips the result.

Usage:
    python scripts/package_extension.py
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTENSION_SRC = REPO_ROOT / "extension"
RELEASE_DIR = REPO_ROOT / "release"
ZIP_PATH = REPO_ROOT / "phishshield-extension.zip"

# Only what Chrome needs to run the extension -- deliberately excludes
# extension/README.md (developer-facing docs, not needed at runtime) and
# anything from the rest of the repo (backend, tests, datasets, .git).
REQUIRED_FILES = [
    "manifest.json",
    "popup.html",
    "popup.css",
    "popup.js",
    "page_extractor.js",
    "page_overlay.js",
]
OPTIONAL_DIRS = ["icons"]  # copied if present; not required to exist yet

# Same secret-pattern check as .githooks/pre-commit, applied to the
# packaged output as a second, independent gate before anything is
# uploaded to the Web Store.
_SECRET_PATTERN = re.compile(
    r'[A-Za-z0-9_]*(API_KEY|TOKEN|SECRET)[A-Za-z0-9_]*[\s]*[:=][\s]*["\']?[A-Za-z0-9._-]{20,}'
)
_FORBIDDEN_SUBSTRINGS = [".py", "__pycache__", ".git", "data/raw", "data/generated", ".env"]


def build_release_dir() -> None:
    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)
    RELEASE_DIR.mkdir(parents=True)

    missing = [f for f in REQUIRED_FILES if not (EXTENSION_SRC / f).exists()]
    if missing:
        raise SystemExit(f"missing required extension files: {missing}")

    for filename in REQUIRED_FILES:
        shutil.copy2(EXTENSION_SRC / filename, RELEASE_DIR / filename)

    for dirname in OPTIONAL_DIRS:
        src_dir = EXTENSION_SRC / dirname
        if src_dir.is_dir():
            shutil.copytree(src_dir, RELEASE_DIR / dirname)


def validate_release_dir() -> list[str]:
    problems = []
    for path in RELEASE_DIR.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(RELEASE_DIR))
        for forbidden in _FORBIDDEN_SUBSTRINGS:
            if forbidden in rel:
                problems.append(f"forbidden path fragment {forbidden!r} in {rel}")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if _SECRET_PATTERN.search(text):
            problems.append(f"possible secret pattern found in {rel}")
    return problems


def zip_release_dir() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(RELEASE_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(RELEASE_DIR))


def main() -> None:
    print(f"Building release package from {EXTENSION_SRC} ...")
    build_release_dir()

    problems = validate_release_dir()
    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)
    print("Validation passed: no backend files, secrets, or dataset paths found.")

    zip_release_dir()
    files = sorted(p.relative_to(RELEASE_DIR) for p in RELEASE_DIR.rglob("*") if p.is_file())
    print(f"\nPackaged {len(files)} files into {RELEASE_DIR}/:")
    for f in files:
        print(f"  {f}")
    print(f"\nZipped: {ZIP_PATH} ({ZIP_PATH.stat().st_size} bytes)")

    if not (RELEASE_DIR / "icons").exists():
        print(
            "\nNOTE: no icons/ directory -- manifest.json has no custom icon. "
            "Chrome Web Store submission needs icon assets; see WEB_STORE_LISTING.md."
        )


if __name__ == "__main__":
    main()
