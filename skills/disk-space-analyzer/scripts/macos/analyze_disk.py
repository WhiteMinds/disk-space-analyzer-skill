#!/usr/bin/env python3
"""
Analyze macOS scan CSV to find cleanable files and disk usage.

Usage:
    python3 scripts/macos/analyze_disk.py <csv_path> <command> [options]

Commands:
    summary                     Show disk usage summary
    largest [--limit N]         Show largest files (default: 20)
    by-type [--limit N]         Show space usage by file type
    cleanable                   Find potentially cleanable files with reasons
    top-folders [--depth N]     Show largest folders at each depth level
    folder <path> [--depth N]   Explore specific folder contents
    search <pattern>            Search files by name pattern
    filter <conditions>         Filter by conditions (see examples)

CSV format (from scan_disk.py): path,size,allocated,modified,is_dir,files_count,folders_count
Paths are POSIX (e.g. /Users/jane/...). Run from the skill directory.
"""

import csv
import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Tuple


# macOS cleanable patterns: (regex, category, reason, migration_hint). Use / for path sep.
CLEANABLE_PATTERNS = [
    # Temp / backup
    (r"\.tmp$", "temp", "Temporary file", None),
    (r"\.temp$", "temp", "Temporary file", None),
    (r"~$", "temp", "Temporary/backup file", None),
    (r"\.bak$", "backup", "Backup file", None),
    (r"\.old$", "backup", "Old version backup", None),
    (r"\.orig$", "backup", "Original backup", None),
    # Cache
    (r"Library/Caches", "cache", "Application caches", None),
    (r"\.cache/", "cache", "Cache directory", None),
    (r"\.npm/", "cache", "npm cache", "npm config set cache ~/cache/npm"),
    (r"npm-cache", "cache", "npm cache", "npm config set cache ~/cache/npm"),
    (r"\.yarn/cache", "cache", "Yarn cache", "yarn config set cache-folder ~/cache/yarn"),
    (r"\.pnpm/store", "cache", "pnpm store", "pnpm config set store-dir ~/cache/pnpm"),
    (r"\.cargo/registry/", "cache", "Cargo (Rust) cache", "Set CARGO_HOME env var"),
    (r"\.gradle/caches", "cache", "Gradle cache", "Set GRADLE_USER_HOME env var"),
    (r"\.m2/repository", "cache", "Maven cache", "Set in settings.xml localRepository"),
    (r"\.cache/pip", "cache", "pip cache", "Set PIP_CACHE_DIR env var"),
    (r"\.cache/uv", "cache", "uv (Python) cache", "Set UV_CACHE_DIR env var"),
    (r"\.cache/huggingface", "cache", "HuggingFace models", "Set HF_HOME env var"),
    (r"\.cache/torch", "cache", "PyTorch cache", "Set TORCH_HOME env var"),
    (r"\.ollama/models", "cache", "Ollama models", "Set OLLAMA_MODELS env var"),
    (r"\.cache/go-build", "cache", "Go build cache", "Set GOCACHE env var"),
    # Logs
    (r"\.log$", "log", "Log file", None),
    (r"Library/Logs", "log", "Application logs", None),
    # Dev
    (r"node_modules/", "dev", "Node.js dependencies", "Run npm install to recreate"),
    (r"__pycache__/", "dev", "Python bytecode cache", "Regenerates automatically"),
    (r"\.pyc$", "dev", "Python compiled file", None),
    (r"\.venv/", "dev", "Python virtual env", "Recreate with python -m venv"),
    (r"\.idea/", "dev", "JetBrains IDE cache", None),
    (r"\.vs/", "dev", "Visual Studio cache", None),
    (r"/(build|dist|out)/(debug|release|bin|obj|classes)/", "dev", "Build output", "Run build to recreate"),
    (r"/projects?/.*/build/", "dev", "Project build output", "Run build to recreate"),
    (r"target/debug", "dev", "Rust debug build", "cargo build recreates"),
    (r"target/release", "dev", "Rust release build", "cargo build --release recreates"),
    (r"\.git/objects/", "dev", "Git objects", "Run git gc to optimize"),
    # System / local
    (r"\.DS_Store", "system", "macOS folder settings", None),
    (r"Library/Application Support/.*/Cache", "system", "App support cache", None),
    (r"Library/Safari", "browser", "Safari data", None),
    (r"Library/Caches/CloudKit", "system", "CloudKit cache", None),
    # Trash
    (r"\.Trash/", "recycle", "Trash", "Empty Trash in Finder"),
    # Downloads
    (r"Downloads/.*\.(dmg|pkg|zip|tar\.gz|iso)$", "download", "Downloaded installer/archive", None),
    # Duplicates
    (r"\s*\(\d+\)\.(jpg|png|mp4|mov)$", "duplicate", "Possible duplicate (numbered)", None),
    (r"\s*-?\s*copy\.(jpg|png|mp4|mov)$", "duplicate", "Possible duplicate (copy)", None),
]

SAFETY_LEVELS = {
    "temp": "safe",
    "cache": "safe",
    "log": "check",
    "backup": "check",
    "dev": "safe",
    "browser": "safe",
    "system": "check",
    "recycle": "check",
    "download": "check",
    "duplicate": "check",
}

# Pre-compile patterns for better performance
CLEANABLE_PATTERNS_COMPILED = [
    (re.compile(pattern), category, reason, hint)
    for pattern, category, reason, hint in CLEANABLE_PATTERNS
]


def parse_size(size_str: str) -> int:
    try:
        return int(size_str.strip().replace(",", "").replace(" ", "") or 0)
    except (ValueError, TypeError):
        return 0


def format_size(size_bytes: int) -> str:
    size_bytes = abs(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def get_path_depth(path: str) -> int:
    """Depth = number of path segments (POSIX)."""
    p = path.strip("/")
    if not p:
        return 0
    return len(p.split("/"))


def read_csv(csv_path: str) -> List[Dict[str, Any]]:
    """Read scan_disk.py CSV. Header: path,size,allocated,modified,is_dir,files_count,folders_count."""
    files = []
    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip().lower(): v for k, v in row.items()} if row else {}
            try:
                path = (row.get("path") or "").strip()
                if not path:
                    continue
                size = parse_size(row.get("size") or "0")
                allocated = parse_size(row.get("allocated") or "0")
                modified = (row.get("modified") or "").strip()
                is_dir = (row.get("is_dir") or "0").strip() in ("1", "true", "yes")
                files_count = int(row.get("files_count") or 0) if row.get("files_count") else 0
                folders_count = int(row.get("folders_count") or 0) if row.get("folders_count") else 0
                depth = get_path_depth(path)
                name = path.rstrip("/").split("/")[-1] if path else ""
                ext = Path(path).suffix.lower() if not is_dir else ""
                entry = {
                    "path": path,
                    "size": size,
                    "allocated": allocated,
                    "modified": modified,
                    "is_dir": is_dir,
                    "files_count": files_count,
                    "folders_count": folders_count,
                    "depth": depth,
                    "name": name,
                    "ext": ext,
                }
                files.append(entry)
            except (ValueError, TypeError):
                continue
    return files


def cmd_summary(files: List[Dict]) -> Dict:
    total_size = sum(f["size"] for f in files if not f["is_dir"])
    total_files = sum(1 for f in files if not f["is_dir"])
    total_dirs = sum(1 for f in files if f["is_dir"])
    by_ext = defaultdict(lambda: {"count": 0, "size": 0})
    for f in files:
        if not f["is_dir"] and f["ext"]:
            by_ext[f["ext"]]["count"] += 1
            by_ext[f["ext"]]["size"] += f["size"]
    top_extensions = sorted(by_ext.items(), key=lambda x: x[1]["size"], reverse=True)[:10]
    result = {
        "total_size": format_size(total_size),
        "total_size_bytes": total_size,
        "total_files": total_files,
        "total_directories": total_dirs,
        "top_extensions": [
            {"ext": ext, "count": data["count"], "size": format_size(data["size"])}
            for ext, data in top_extensions
        ],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_largest(files: List[Dict], limit: int = 20) -> List[Dict]:
    file_only = [f for f in files if not f["is_dir"]]
    sorted_files = sorted(file_only, key=lambda x: x["size"], reverse=True)[:limit]
    result = [
        {"path": f["path"], "size": format_size(f["size"]), "size_bytes": f["size"]}
        for f in sorted_files
    ]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_by_type(files: List[Dict], limit: int = 30) -> List[Dict]:
    by_ext = defaultdict(lambda: {"count": 0, "size": 0})
    for f in files:
        if not f["is_dir"]:
            ext = f["ext"] if f["ext"] else "(no extension)"
            by_ext[ext]["count"] += 1
            by_ext[ext]["size"] += f["size"]
    sorted_types = sorted(by_ext.items(), key=lambda x: x[1]["size"], reverse=True)[:limit]
    result = [
        {
            "extension": ext,
            "count": data["count"],
            "size": format_size(data["size"]),
            "size_bytes": data["size"],
        }
        for ext, data in sorted_types
    ]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_top_folders(files: List[Dict], max_depth: int = 2, limit: int = 10) -> Dict:
    # Find minimum depth (scan root depth) to calculate relative depths
    min_depth = min((f["depth"] for f in files if f["is_dir"]), default=0)

    by_rel_depth = defaultdict(list)
    for f in files:
        if f["is_dir"]:
            rel_depth = f["depth"] - min_depth
            if rel_depth > 0:  # Exclude the root itself (rel_depth=0)
                by_rel_depth[rel_depth].append(f)

    result = {"depths": {}, "scan_root_depth": min_depth}
    for rel_depth in range(1, max_depth + 1):
        if rel_depth in by_rel_depth:
            sorted_dirs = sorted(by_rel_depth[rel_depth], key=lambda x: x["size"], reverse=True)[:limit]
            result["depths"][rel_depth] = [
                {
                    "path": d["path"],
                    "size": format_size(d["size"]),
                    "size_bytes": d["size"],
                    "files_count": d.get("files_count", 0),
                    "folders_count": d.get("folders_count", 0),
                }
                for d in sorted_dirs
            ]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_folder(files: List[Dict], target_path: str, depth: int = 1) -> Dict:
    prefix = target_path.rstrip("/")
    target = prefix + "/"
    target_depth = get_path_depth(prefix)
    seen_paths = set()
    children = []
    for f in files:
        p = f["path"].rstrip("/")
        if p == prefix:
            continue
        if not (p + "/").startswith(target):
            continue
        # Deduplicate by path
        if p in seen_paths:
            continue
        seen_paths.add(p)
        rel_depth = f["depth"] - target_depth
        if rel_depth < 1 or rel_depth > depth:
            continue
        if rel_depth < depth and not f["is_dir"]:
            continue
        children.append({
            "path": f["path"],
            "name": f["name"],
            "size": format_size(f["size"]),
            "size_bytes": f["size"],
            "is_dir": f["is_dir"],
            "depth": rel_depth,
            "files_count": f.get("files_count", 0),
            "folders_count": f.get("folders_count", 0),
        })
    children = sorted(children, key=lambda x: x["size_bytes"], reverse=True)[:50]
    result = {
        "path": target_path.rstrip("/"),
        "depth": depth,
        "directories": [c for c in children if c["is_dir"]][:30],
        "files": [c for c in children if not c["is_dir"]][:20],
        "total_items": len(children),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_cleanable(files: List[Dict]) -> Dict:
    cleanable = defaultdict(
        lambda: {"files": [], "total_size": 0, "reason": "", "migration_hints": set(), "safety": "safe"}
    )
    for f in files:
        if f["is_dir"]:
            continue
        path_lower = f["path"].lower()
        for pattern_re, category, reason, migration_hint in CLEANABLE_PATTERNS_COMPILED:
            if pattern_re.search(path_lower):
                cleanable[category]["files"].append({
                    "path": f["path"],
                    "size": format_size(f["size"]),
                    "size_bytes": f["size"],
                })
                cleanable[category]["total_size"] += f["size"]
                cleanable[category]["reason"] = reason
                cleanable[category]["safety"] = SAFETY_LEVELS.get(category, "check")
                if migration_hint:
                    cleanable[category]["migration_hints"].add(migration_hint)
                break
    for category in cleanable:
        # Save actual file count before truncating
        cleanable[category]["actual_file_count"] = len(cleanable[category]["files"])
        cleanable[category]["files"] = sorted(
            cleanable[category]["files"], key=lambda x: x["size_bytes"], reverse=True
        )[:50]
    result = {
        "categories": {
            cat: {
                "reason": data["reason"],
                "safety": data["safety"],
                "total_size": format_size(data["total_size"]),
                "total_size_bytes": data["total_size"],
                "file_count": data["actual_file_count"],
                "migration_hints": list(data["migration_hints"]) if data["migration_hints"] else None,
                "sample_files": data["files"][:10],
            }
            for cat, data in sorted(
                cleanable.items(), key=lambda x: x[1]["total_size"], reverse=True
            )
        },
        "by_safety": {"safe": [], "check": [], "admin": []},
        "total_cleanable_size": format_size(sum(d["total_size"] for d in cleanable.values())),
        "total_cleanable_bytes": sum(d["total_size"] for d in cleanable.values()),
    }
    for cat, data in cleanable.items():
        safety = data["safety"]
        result["by_safety"].setdefault(safety, []).append({
            "category": cat,
            "size": format_size(data["total_size"]),
            "size_bytes": data["total_size"],
        })
    for safety in result["by_safety"]:
        result["by_safety"][safety] = sorted(
            result["by_safety"][safety], key=lambda x: x["size_bytes"], reverse=True
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_search(files: List[Dict], pattern: str) -> List[Dict]:
    # Escape special regex chars, then convert glob wildcards
    escaped = re.escape(pattern)
    regex = escaped.replace(r"\*", ".*").replace(r"\?", ".")
    matches = []
    for f in files:
        if re.search(regex, f["name"]):
            matches.append({
                "path": f["path"],
                "size": format_size(f["size"]),
                "size_bytes": f["size"],
                "is_dir": f["is_dir"],
            })
    matches = sorted(matches, key=lambda x: x["size_bytes"], reverse=True)[:100]
    result = {"pattern": pattern, "matches": matches, "count": len(matches)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_filter(files: List[Dict], conditions: str) -> List[Dict]:
    def parse_condition(cond: str) -> Tuple[str, str, str]:
        for op in [">=", "<=", ">", "<", "=", "~"]:
            if op in cond:
                parts = cond.split(op, 1)
                return parts[0].strip(), op, parts[1].strip()
        return cond, "=", "true"

    def matches_condition(f: Dict, field: str, op: str, value: str) -> bool:
        if field == "size":
            cmp_size = parse_size(value)
            if op == ">": return f["size"] > cmp_size
            if op == ">=": return f["size"] >= cmp_size
            if op == "<": return f["size"] < cmp_size
            if op == "<=": return f["size"] <= cmp_size
            if op == "=": return f["size"] == cmp_size
        elif field == "ext":
            cmp_ext = value.lower() if value.startswith(".") else "." + value.lower()
            return (f["ext"] or "").lower() == cmp_ext
        elif field == "path":
            if op == "~":
                return value.lower() in f["path"].lower()
            return f["path"].lower() == value.lower()
        elif field == "name":
            if op == "~":
                return value.lower() in (f["name"] or "").lower()
            return (f["name"] or "").lower() == value.lower()
        elif field == "depth":
            cmp_depth = int(value)
            if op == ">": return f.get("depth", 0) > cmp_depth
            if op == ">=": return f.get("depth", 0) >= cmp_depth
            if op == "<": return f.get("depth", 0) < cmp_depth
            if op == "<=": return f.get("depth", 0) <= cmp_depth
            if op == "=": return f.get("depth", 0) == cmp_depth
        return True

    cond_list = [parse_condition(c.strip()) for c in conditions.split(",")]
    matches = []
    for f in files:
        if f["is_dir"]:
            continue
        if all(matches_condition(f, field, op, val) for field, op, val in cond_list):
            matches.append({
                "path": f["path"],
                "size": format_size(f["size"]),
                "size_bytes": f["size"],
            })
    matches = sorted(matches, key=lambda x: x["size_bytes"], reverse=True)[:100]
    result = {"conditions": conditions, "matches": matches, "count": len(matches)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def get_option(name: str, default: int) -> int:
    if name in sys.argv:
        idx = sys.argv.index(name)
        if idx + 1 < len(sys.argv):
            try:
                return int(sys.argv[idx + 1])
            except ValueError:
                pass
    return default


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    csv_path = sys.argv[1]
    command = sys.argv[2].lower()
    if not Path(csv_path).exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    files = read_csv(csv_path)
    if command == "summary":
        cmd_summary(files)
    elif command == "largest":
        cmd_largest(files, get_option("--limit", 20))
    elif command == "by-type":
        cmd_by_type(files, get_option("--limit", 30))
    elif command == "top-folders":
        cmd_top_folders(
            files,
            get_option("--depth", 2),
            get_option("--limit", 10),
        )
    elif command == "folder":
        if len(sys.argv) < 4:
            print("Usage: analyze_disk.py <csv> folder <path> [--depth N]", file=sys.stderr)
            sys.exit(1)
        cmd_folder(files, sys.argv[3], get_option("--depth", 1))
    elif command == "cleanable":
        cmd_cleanable(files)
    elif command == "search":
        if len(sys.argv) < 4:
            print("Usage: analyze_disk.py <csv> search <pattern>", file=sys.stderr)
            sys.exit(1)
        cmd_search(files, sys.argv[3])
    elif command == "filter":
        if len(sys.argv) < 4:
            print("Usage: analyze_disk.py <csv> filter <conditions>", file=sys.stderr)
            sys.exit(1)
        cmd_filter(files, sys.argv[3])
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Commands: summary, largest, by-type, top-folders, folder, cleanable, search, filter")
        sys.exit(1)


if __name__ == "__main__":
    main()
