#!/usr/bin/env python3
"""
Scan a directory tree and export disk usage to CSV (macOS / POSIX).

Usage:
    python3 scripts/macos/scan_disk.py <root_path> <output_csv> [options]

Options:
    --skip-hidden       Skip files/directories starting with .
    --max-depth N       Limit scan to N levels deep (default: unlimited)
    --exclude PATTERN   Exclude paths matching pattern (can be used multiple times)
                        Supports glob patterns: node_modules, *.log, Library/Caches

Output CSV columns: path,size,allocated,modified,is_dir,files_count,folders_count
Paths are absolute, POSIX style. Run from the skill directory (containing scripts/).
"""

import argparse
import csv
import fnmatch
import os
import sys
import time
from pathlib import Path
from typing import List, Optional


def norm_path(p: Path) -> str:
    """Return absolute POSIX path string."""
    return p.resolve().as_posix()


def matches_exclude(path: str, name: str, exclude_patterns: List[str]) -> bool:
    """Check if path or name matches any exclude pattern."""
    for pattern in exclude_patterns:
        # Match against full path or just the name
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(path, f"*{pattern}*"):
            return True
    return False


def scan(
    root_path: str,
    output_csv: str,
    skip_hidden: bool = False,
    progress_interval: int = 10000,
    max_depth: Optional[int] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> None:
    root = Path(root_path).resolve()
    if not root.is_dir():
        print(f"Error: not a directory: {root_path}", file=sys.stderr)
        sys.exit(1)

    exclude_patterns = exclude_patterns or []
    root_depth = len(root.parts)

    rows = []
    seen_paths = set()  # Track seen paths to avoid duplicates (hardlinks/firmlinks)
    count = 0
    last_progress = time.monotonic()

    try:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            dir_path = Path(dirpath)
            current_depth = len(dir_path.parts) - root_depth

            # Check max depth - prune subdirectories if at max depth
            if max_depth is not None and current_depth >= max_depth:
                dirnames[:] = []  # Don't descend further

            # Optional: skip hidden dirs from being entered
            if skip_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                filenames = [f for f in filenames if not f.startswith(".")]

            # Apply exclude patterns to directories
            if exclude_patterns:
                dir_posix_temp = norm_path(dir_path)
                dirnames[:] = [
                    d for d in dirnames
                    if not matches_exclude(f"{dir_posix_temp}/{d}", d, exclude_patterns)
                ]

            dir_posix = norm_path(dir_path)

            # Skip if already seen (can happen with firmlinks on macOS)
            if dir_posix in seen_paths:
                continue
            seen_paths.add(dir_posix)

            # Use already-filtered lists (filtered at lines 74-75 if skip_hidden)
            subdirs = dirnames
            subfiles = filenames

            # Directory row
            try:
                mtime = dir_path.stat().st_mtime
                mod_str = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime))
            except OSError:
                mod_str = ""

            rows.append({
                "path": dir_posix,
                "size": 0,
                "allocated": 0,
                "modified": mod_str,
                "is_dir": 1,
                "files_count": len(subfiles),
                "folders_count": len(subdirs),
            })
            count += 1

            # File rows
            for name in filenames:
                if skip_hidden and name.startswith("."):
                    continue
                fp = dir_path / name
                fp_posix = norm_path(fp)
                # Skip if already seen (hardlinks/firmlinks)
                if fp_posix in seen_paths:
                    continue
                seen_paths.add(fp_posix)
                # Apply exclude patterns to files
                if exclude_patterns and matches_exclude(fp_posix, name, exclude_patterns):
                    continue
                try:
                    if fp.is_symlink():
                        st = os.lstat(fp)
                    else:
                        st = fp.stat()
                    size = st.st_size
                    mod_str = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))
                except OSError:
                    size = 0
                    mod_str = ""

                rows.append({
                    "path": fp_posix,
                    "size": size,
                    "allocated": size,
                    "modified": mod_str,
                    "is_dir": 0,
                    "files_count": 0,
                    "folders_count": 0,
                })
                count += 1

            if count >= progress_interval and (count % progress_interval) < len(filenames) + 1:
                now = time.monotonic()
                if now - last_progress >= 5.0:
                    print(f"Progress: {count} entries, current: {dir_posix}", file=sys.stderr)
                    last_progress = now

    except PermissionError as e:
        print(f"Warning: permission denied: {e}", file=sys.stderr)
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Aggregate directory sizes: for each dir, sum sizes of all files under it
    dir_sizes = {}
    for r in rows:
        if r["is_dir"] == 0:
            path = r["path"]
            size = r["size"]
            parts = path.strip("/").split("/")
            for i in range(1, len(parts)):
                parent = "/" + "/".join(parts[:i])
                dir_sizes[parent] = dir_sizes.get(parent, 0) + size
    for r in rows:
        if r["is_dir"] == 1:
            p = r["path"].rstrip("/")
            r["size"] = dir_sizes.get(p, 0)
            r["allocated"] = r["size"]

    # Write CSV
    fieldnames = ["path", "size", "allocated", "modified", "is_dir", "files_count", "folders_count"]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_csv}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Scan directory tree and export to CSV for disk analysis."
    )
    parser.add_argument("root_path", help="Root directory to scan (e.g. /, /Users/username)")
    parser.add_argument("output_csv", help="Output CSV path")
    parser.add_argument(
        "--skip-hidden",
        action="store_true",
        help="Skip files and directories whose name starts with .",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=10000,
        help="Print progress to stderr every N entries (default 10000)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Maximum depth to scan (default: unlimited)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        dest="exclude_patterns",
        default=[],
        help="Exclude paths matching pattern (can be used multiple times). "
             "Supports glob: node_modules, *.log, Library/Caches",
    )
    args = parser.parse_args()
    scan(
        args.root_path,
        args.output_csv,
        args.skip_hidden,
        args.progress_interval,
        args.max_depth,
        args.exclude_patterns,
    )


if __name__ == "__main__":
    main()
