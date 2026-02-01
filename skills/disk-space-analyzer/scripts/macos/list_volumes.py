#!/usr/bin/env python3
"""
List mounted volumes (macOS). Outputs JSON: name, mount_point, total, free, etc.

Usage:
    python scripts/macos/list_volumes.py

Run from the skill directory. Uses df output; no admin required.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    try:
        out = subprocess.check_output(
            ["df", "-k"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: list common mount points
        volumes = []
        for p in ["/", "/Users", "/Volumes"]:
            if Path(p).exists():
                try:
                    st = os.statvfs(p)
                    total = st.f_blocks
                    free = st.f_bavail
                    block_size = st.f_frsize
                    volumes.append({
                        "mount_point": p,
                        "name": p.split("/")[-1] or "root",
                        "total_bytes": total * block_size,
                        "free_bytes": free * block_size,
                        "used_bytes": (total - free) * block_size,
                    })
                except OSError:
                    pass
        print(json.dumps({"volumes": volumes}, indent=2))
        return

    volumes = []
    lines = out.strip().split("\n")
    if not lines:
        print(json.dumps({"volumes": []}, indent=2))
        return
    # Skip header
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        # macOS df -k: Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted on
        # Index:       0          1           2    3         4        5      6     7      8+
        try:
            total_1k = int(parts[1])
            used_1k = int(parts[2])
            avail_1k = int(parts[3])
            # Mount point starts at index 8 and may contain spaces
            mount = " ".join(parts[8:])
        except (ValueError, IndexError):
            continue
        total_bytes = total_1k * 1024
        free_bytes = avail_1k * 1024
        used_bytes = used_1k * 1024
        name = mount.rstrip("/").split("/")[-1] or "root"
        volumes.append({
            "mount_point": mount,
            "name": name,
            "total_bytes": total_bytes,
            "free_bytes": free_bytes,
            "used_bytes": used_bytes,
            "total_1k": total_1k,
            "free_1k": avail_1k,
            "used_1k": used_1k,
        })

    # Sort by free space ascending (least free first)
    volumes.sort(key=lambda v: v["free_bytes"])
    print(json.dumps({"volumes": volumes}, indent=2))


if __name__ == "__main__":
    main()
