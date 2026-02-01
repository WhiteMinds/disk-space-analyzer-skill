#!/usr/bin/env python3
"""
Find WizTree executable on the system, with optional auto-install of portable version.

Usage:
    python find_wiztree.py [--auto-install]

Options:
    --auto-install    Automatically download and install portable WizTree if not found

Returns the path to WizTree executable if found/installed, or exits with error code 1.
"""

import os
import sys
import zipfile
import urllib.request
import tempfile
from pathlib import Path

WIZTREE_DOWNLOAD_URL = "https://diskanalyzer.com/files/wiztree_4_21_portable.zip"
WIZTREE_INSTALL_DIR = Path.home() / ".wiztree"


def find_wiztree():
    """Search for WizTree executable in common locations."""
    candidates = [
        # Our portable install location (check first)
        WIZTREE_INSTALL_DIR / "WizTree64.exe",
        WIZTREE_INSTALL_DIR / "WizTree.exe",
        # Program Files
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "WizTree" / "WizTree64.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "WizTree" / "WizTree.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "WizTree" / "WizTree.exe",
        # Common install locations
        Path("C:/Program Files/WizTree/WizTree64.exe"),
        Path("C:/Program Files/WizTree/WizTree.exe"),
        Path("C:/Program Files (x86)/WizTree/WizTree.exe"),
        # Portable locations
        Path.home() / "WizTree" / "WizTree64.exe",
        Path.home() / "WizTree" / "WizTree.exe",
        Path.home() / "Downloads" / "WizTree" / "WizTree64.exe",
        Path.home() / "Desktop" / "WizTree" / "WizTree64.exe",
    ]

    # Also check PATH
    for exe_name in ["WizTree64.exe", "WizTree.exe"]:
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for dir_path in path_dirs:
            candidate = Path(dir_path) / exe_name
            if candidate.exists():
                return str(candidate)

    # Check candidate locations
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None


def download_and_install_wiztree():
    """Download and install WizTree portable version."""
    print(f"Downloading WizTree portable from {WIZTREE_DOWNLOAD_URL}...", file=sys.stderr)

    # Create install directory
    WIZTREE_INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    # Download to temp file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        # Download with progress
        def report_progress(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100, block_num * block_size * 100 // total_size)
                print(f"\rDownloading: {percent}%", end="", file=sys.stderr)

        urllib.request.urlretrieve(WIZTREE_DOWNLOAD_URL, tmp_path, report_progress)
        print(file=sys.stderr)  # New line after progress

        # Extract zip
        print(f"Extracting to {WIZTREE_INSTALL_DIR}...", file=sys.stderr)
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            zip_ref.extractall(WIZTREE_INSTALL_DIR)

        # Find the executable
        exe_path = WIZTREE_INSTALL_DIR / "WizTree64.exe"
        if not exe_path.exists():
            exe_path = WIZTREE_INSTALL_DIR / "WizTree.exe"

        if exe_path.exists():
            print(f"WizTree installed successfully: {exe_path}", file=sys.stderr)
            return str(exe_path)
        else:
            print("Error: WizTree executable not found after extraction", file=sys.stderr)
            return None

    except urllib.error.URLError as e:
        print(f"Download failed: {e}", file=sys.stderr)
        return None
    except zipfile.BadZipFile:
        print("Error: Downloaded file is not a valid zip", file=sys.stderr)
        return None
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def main():
    auto_install = "--auto-install" in sys.argv

    result = find_wiztree()
    if result:
        print(result)
        sys.exit(0)

    if auto_install:
        result = download_and_install_wiztree()
        if result:
            print(result)
            sys.exit(0)
        else:
            print("Failed to install WizTree", file=sys.stderr)
            sys.exit(1)
    else:
        print("WizTree not found. Use --auto-install to download portable version.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
