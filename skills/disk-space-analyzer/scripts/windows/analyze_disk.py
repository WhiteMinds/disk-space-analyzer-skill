#!/usr/bin/env python3
"""
Analyze WizTree CSV export to find cleanable files.

Usage:
    python analyze_disk.py <csv_path> <command> [options]

Commands:
    summary                     Show disk usage summary
    largest [--limit N]         Show largest files (default: 20)
    by-type [--limit N]         Show space usage by file type
    cleanable                   Find potentially cleanable files with reasons
    top-folders [--depth N]     Show largest folders at each depth level
    folder <path> [--depth N]   Explore specific folder contents
    search <pattern>            Search files by name pattern
    filter <conditions>         Filter by conditions (see examples)

Examples:
    python analyze_disk.py disk.csv summary
    python analyze_disk.py disk.csv largest --limit 50
    python analyze_disk.py disk.csv top-folders --depth 3
    python analyze_disk.py disk.csv folder "C:\\Users\\name\\AppData" --depth 2
    python analyze_disk.py disk.csv cleanable
    python analyze_disk.py disk.csv search "*.tmp"
    python analyze_disk.py disk.csv filter "size>1GB,ext=.log"

CSV Format (WizTree):
    File Name,Size,Allocated,Modified,Attributes,Files,Folders
"""

import csv
import sys
import re
import json
from pathlib import Path, PureWindowsPath
from collections import defaultdict
from typing import List, Dict, Any, Tuple


# Cleanable file patterns with reasons and migration info
# Format: (pattern, category, reason, migration_hint)
CLEANABLE_PATTERNS = [
    # Temporary files
    (r'\.tmp$', 'temp', 'Temporary file', None),
    (r'\.temp$', 'temp', 'Temporary file', None),
    (r'~$', 'temp', 'Temporary/backup file', None),
    (r'\.bak$', 'backup', 'Backup file', None),
    (r'\.old$', 'backup', 'Old version backup', None),
    (r'\.orig$', 'backup', 'Original backup', None),

    # Package manager caches (with migration hints)
    (r'\\\.uv\\cache\\', 'cache', 'uv (Python) cache', 'Set UV_CACHE_DIR env var to relocate'),
    (r'\\uv\\cache\\', 'cache', 'uv (Python) cache', 'Set UV_CACHE_DIR env var to relocate'),
    (r'\\pip\\cache\\', 'cache', 'pip cache', 'Set PIP_CACHE_DIR env var to relocate'),
    (r'\\npm-cache\\', 'cache', 'npm cache', 'npm config set cache D:\\cache\\npm'),
    (r'\\\.npm\\', 'cache', 'npm cache', 'npm config set cache D:\\cache\\npm'),
    (r'\\yarn\\cache\\', 'cache', 'Yarn cache', 'yarn config set cache-folder D:\\cache\\yarn'),
    (r'\\pnpm\\store\\', 'cache', 'pnpm store', 'pnpm config set store-dir D:\\cache\\pnpm'),
    (r'\\\.cargo\\registry\\', 'cache', 'Cargo (Rust) cache', 'Set CARGO_HOME env var'),
    (r'\\\.gradle\\caches\\', 'cache', 'Gradle cache', 'Set GRADLE_USER_HOME env var'),
    (r'\\\.m2\\repository\\', 'cache', 'Maven cache', 'Set in settings.xml localRepository'),
    (r'\\\.nuget\\packages\\', 'cache', 'NuGet cache', 'Set NUGET_PACKAGES env var'),
    (r'\\go\\pkg\\mod\\', 'cache', 'Go modules cache', 'Set GOMODCACHE env var'),

    # AI/ML caches
    (r'\\\.cache\\huggingface\\', 'cache', 'HuggingFace models', 'Set HF_HOME env var to relocate'),
    (r'\\\.cache\\torch\\', 'cache', 'PyTorch cache', 'Set TORCH_HOME env var'),
    (r'\\\.ollama\\models\\', 'cache', 'Ollama models', 'Set OLLAMA_MODELS env var'),

    # General cache patterns
    (r'\\cache\\', 'cache', 'Cache directory', None),
    (r'\\caches\\', 'cache', 'Cache directory', None),
    (r'\.cache$', 'cache', 'Cache file', None),

    # Log files
    (r'\.log$', 'log', 'Log file', None),
    (r'\.log\.\d+$', 'log', 'Rotated log file', None),
    (r'\.log\.gz$', 'log', 'Compressed log file', None),

    # Thumbnails and previews
    (r'thumbs\.db$', 'system', 'Windows thumbnail cache', None),
    (r'desktop\.ini$', 'system', 'Windows folder settings', None),
    (r'\.ds_store$', 'system', 'macOS folder settings', None),

    # Development artifacts
    (r'\\node_modules\\', 'dev', 'Node.js dependencies', 'Run npm install to recreate'),
    (r'\\.git\\objects\\', 'dev', 'Git objects', 'Run git gc to optimize'),
    (r'\\__pycache__\\', 'dev', 'Python bytecode cache', 'Regenerates automatically'),
    (r'\.pyc$', 'dev', 'Python compiled file', None),
    (r'\\\.vs\\', 'dev', 'Visual Studio cache', None),
    (r'\\\.idea\\', 'dev', 'JetBrains IDE cache', None),
    (r'\\bin\\Debug\\', 'dev', 'Debug build output', 'Run build to recreate'),
    (r'\\bin\\Release\\', 'dev', 'Release build output', 'Run build to recreate'),
    (r'\\obj\\', 'dev', '.NET build intermediates', None),
    (r'\\target\\debug\\', 'dev', 'Rust debug build', 'cargo build recreates'),
    (r'\\target\\release\\', 'dev', 'Rust release build', 'cargo build --release recreates'),

    # Downloads (old installers)
    (r'\\downloads\\.*\.(exe|msi|zip|7z|rar)$', 'download', 'Downloaded installer/archive', None),

    # Browser data
    (r'\\chrome\\.*\\cache', 'browser', 'Chrome cache', None),
    (r'\\firefox\\.*\\cache2\\', 'browser', 'Firefox cache', None),
    (r'\\edge\\.*\\cache', 'browser', 'Edge cache', None),
    (r'\\brave.*\\cache', 'browser', 'Brave cache', None),

    # System temp
    (r'\\windows\\temp\\', 'temp', 'Windows temp directory', None),
    (r'\\appdata\\local\\temp\\', 'temp', 'User temp directory', None),

    # Docker
    (r'\\docker\\.*\\cache', 'cache', 'Docker build cache', 'docker builder prune'),

    # Windows specific
    (r'\\windows\\softwaredistribution\\download\\', 'windows', 'Windows Update downloads', 'Run Disk Cleanup as admin'),
    (r'\\\$recycle\.bin\\', 'recycle', 'Recycle bin', 'Empty recycle bin'),
    (r'hiberfil\.sys$', 'windows', 'Hibernation file', 'powercfg /h off (admin) to disable'),
    (r'pagefile\.sys$', 'windows', 'Page file', 'Reduce in System Properties > Performance'),
    (r'swapfile\.sys$', 'windows', 'Swap file', 'Managed by Windows'),

    # Large media duplicates patterns
    (r'\s*\(\d+\)\.(jpg|png|mp4|mkv|avi|mov)$', 'duplicate', 'Possible duplicate (numbered)', None),
    (r'\s*-\s*copy\.(jpg|png|mp4|mkv)$', 'duplicate', 'Possible duplicate (copy)', None),
]


def parse_size(size_str: str) -> int:
    """Parse size string to bytes."""
    size_str = size_str.strip().replace(',', '').replace(' ', '')
    if not size_str:
        return 0

    # Already a number
    try:
        return int(size_str)
    except ValueError:
        pass

    # Has unit suffix
    units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
    for unit, multiplier in units.items():
        if size_str.upper().endswith(unit):
            try:
                return int(float(size_str[:-len(unit)]) * multiplier)
            except ValueError:
                return 0
    return 0


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def _parse_int(s: str) -> int:
    """Safely parse string to int, returning 0 on failure."""
    try:
        return int(s) if s and s.isdigit() else 0
    except (ValueError, TypeError):
        return 0


def get_path_depth(path: str) -> int:
    """Get depth of a path (number of components after drive letter)."""
    # Normalize path and count parts
    p = PureWindowsPath(path)
    parts = p.parts
    # First part is drive (e.g., 'C:\\'), rest are directories
    return len(parts) - 1 if parts else 0


def read_csv(csv_path: str) -> List[Dict[str, Any]]:
    """Read WizTree CSV file.

    WizTree CSV format:
        Line 1: "Generated by WizTree..." (skip)
        Line 2: "File Name,Size,Allocated,Modified,Attributes,Files,Folders" (header)
        Line 3+: Data rows

    Directory detection: A row is a directory if Files or Folders count > 0,
    or if the path ends with backslash.
    """
    files = []
    with open(csv_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
        reader = csv.reader(f)

        for row in reader:
            if not row or len(row) < 2:
                continue

            # Skip header/info rows
            first_cell = row[0].lower()
            if first_cell.startswith('generated') or first_cell in ('file name', 'filename', 'name'):
                continue

            try:
                path = row[0]
                size = parse_size(row[1]) if len(row) > 1 else 0

                # Directory detection: has Files/Folders count > 0, or path ends with \
                files_count = _parse_int(row[5]) if len(row) > 5 else 0
                folders_count = _parse_int(row[6]) if len(row) > 6 else 0
                is_dir = files_count > 0 or folders_count > 0 or path.endswith('\\')

                entry = {
                    'path': path,
                    'size': size,
                    'allocated': parse_size(row[2]) if len(row) > 2 else 0,
                    'modified': row[3] if len(row) > 3 else '',
                    'is_dir': is_dir,
                    'files_count': files_count,
                    'folders_count': folders_count,
                    'depth': get_path_depth(path),
                }
                entry['ext'] = Path(path).suffix.lower() if not is_dir else ''
                entry['name'] = Path(path).name if not path.endswith('\\') else path.rstrip('\\').split('\\')[-1]
                files.append(entry)
            except Exception:
                continue

    return files


def cmd_summary(files: List[Dict]) -> Dict:
    """Generate disk usage summary."""
    total_size = sum(f['size'] for f in files if not f['is_dir'])
    total_files = sum(1 for f in files if not f['is_dir'])
    total_dirs = sum(1 for f in files if f['is_dir'])

    # By extension
    by_ext = defaultdict(lambda: {'count': 0, 'size': 0})
    for f in files:
        if not f['is_dir'] and f['ext']:
            by_ext[f['ext']]['count'] += 1
            by_ext[f['ext']]['size'] += f['size']

    top_extensions = sorted(by_ext.items(), key=lambda x: x[1]['size'], reverse=True)[:10]

    result = {
        'total_size': format_size(total_size),
        'total_size_bytes': total_size,
        'total_files': total_files,
        'total_directories': total_dirs,
        'top_extensions': [
            {'ext': ext, 'count': data['count'], 'size': format_size(data['size'])}
            for ext, data in top_extensions
        ]
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_largest(files: List[Dict], limit: int = 20) -> List[Dict]:
    """Find largest files."""
    file_only = [f for f in files if not f['is_dir']]
    sorted_files = sorted(file_only, key=lambda x: x['size'], reverse=True)[:limit]

    result = [
        {'path': f['path'], 'size': format_size(f['size']), 'size_bytes': f['size']}
        for f in sorted_files
    ]

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_by_type(files: List[Dict], limit: int = 30) -> List[Dict]:
    """Show space usage by file type."""
    by_ext = defaultdict(lambda: {'count': 0, 'size': 0})

    for f in files:
        if not f['is_dir']:
            ext = f['ext'] if f['ext'] else '(no extension)'
            by_ext[ext]['count'] += 1
            by_ext[ext]['size'] += f['size']

    sorted_types = sorted(by_ext.items(), key=lambda x: x[1]['size'], reverse=True)[:limit]

    result = [
        {'extension': ext, 'count': data['count'], 'size': format_size(data['size']), 'size_bytes': data['size']}
        for ext, data in sorted_types
    ]

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_top_folders(files: List[Dict], max_depth: int = 2, limit: int = 10) -> Dict:
    """Show largest folders at each depth level."""
    # Group directories by depth
    by_depth = defaultdict(list)
    for f in files:
        if f['is_dir']:
            by_depth[f['depth']].append(f)

    result = {'depths': {}}
    for depth in range(1, max_depth + 1):
        if depth in by_depth:
            sorted_dirs = sorted(by_depth[depth], key=lambda x: x['size'], reverse=True)[:limit]
            result['depths'][depth] = [
                {
                    'path': d['path'],
                    'size': format_size(d['size']),
                    'size_bytes': d['size'],
                    'files_count': d.get('files_count', 0),
                    'folders_count': d.get('folders_count', 0)
                }
                for d in sorted_dirs
            ]

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_folder(files: List[Dict], target_path: str, depth: int = 1) -> Dict:
    """Explore contents of a specific folder."""
    # Normalize target path
    target = target_path.rstrip('\\').lower() + '\\'
    target_depth = get_path_depth(target_path)

    # Find direct children and nested items up to specified depth
    children = []
    for f in files:
        path_lower = f['path'].lower()
        if not path_lower.startswith(target):
            continue

        # Calculate relative depth
        rel_depth = f['depth'] - target_depth
        if rel_depth < 1 or rel_depth > depth:
            continue

        # For depth > 1, only show directories at intermediate levels
        if rel_depth < depth and not f['is_dir']:
            continue

        children.append({
            'path': f['path'],
            'name': f['name'] or f['path'].rstrip('\\').split('\\')[-1],
            'size': format_size(f['size']),
            'size_bytes': f['size'],
            'is_dir': f['is_dir'],
            'depth': rel_depth,
            'files_count': f.get('files_count', 0),
            'folders_count': f.get('folders_count', 0)
        })

    # Sort by size
    children = sorted(children, key=lambda x: x['size_bytes'], reverse=True)[:50]

    # Separate dirs and files
    dirs = [c for c in children if c['is_dir']]
    files_list = [c for c in children if not c['is_dir']]

    result = {
        'path': target_path,
        'depth': depth,
        'directories': dirs[:30],
        'files': files_list[:20],
        'total_items': len(children)
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_cleanable(files: List[Dict]) -> Dict:
    """Find potentially cleanable files with reasons and suggestions."""
    cleanable = defaultdict(lambda: {
        'files': [],
        'total_size': 0,
        'reason': '',
        'migration_hints': set(),
        'safety': 'safe'
    })

    # Define safety levels
    safety_levels = {
        'temp': 'safe',
        'cache': 'safe',
        'log': 'check',
        'backup': 'check',
        'dev': 'safe',
        'browser': 'safe',
        'system': 'safe',
        'windows': 'admin',
        'recycle': 'check',
        'download': 'check',
        'duplicate': 'check',
    }

    for f in files:
        if f['is_dir']:
            continue

        path_lower = f['path'].lower()
        for pattern, category, reason, migration_hint in CLEANABLE_PATTERNS:
            if re.search(pattern, path_lower, re.IGNORECASE):
                cleanable[category]['files'].append({
                    'path': f['path'],
                    'size': format_size(f['size']),
                    'size_bytes': f['size']
                })
                cleanable[category]['total_size'] += f['size']
                cleanable[category]['reason'] = reason
                cleanable[category]['safety'] = safety_levels.get(category, 'check')
                if migration_hint:
                    cleanable[category]['migration_hints'].add(migration_hint)
                break

    # Sort files within each category by size
    for category in cleanable:
        cleanable[category]['files'] = sorted(
            cleanable[category]['files'],
            key=lambda x: x['size_bytes'],
            reverse=True
        )[:50]

    # Build result with migration hints
    result = {
        'categories': {
            cat: {
                'reason': data['reason'],
                'safety': data['safety'],
                'total_size': format_size(data['total_size']),
                'total_size_bytes': data['total_size'],
                'file_count': len(data['files']),
                'migration_hints': list(data['migration_hints']) if data['migration_hints'] else None,
                'sample_files': data['files'][:10]
            }
            for cat, data in sorted(cleanable.items(), key=lambda x: x[1]['total_size'], reverse=True)
        },
        'by_safety': {
            'safe': [],
            'check': [],
            'admin': []
        },
        'total_cleanable_size': format_size(sum(d['total_size'] for d in cleanable.values())),
        'total_cleanable_bytes': sum(d['total_size'] for d in cleanable.values())
    }

    # Group by safety level
    for cat, data in cleanable.items():
        safety = data['safety']
        result['by_safety'][safety].append({
            'category': cat,
            'size': format_size(data['total_size']),
            'size_bytes': data['total_size']
        })

    # Sort each safety group by size
    for safety in result['by_safety']:
        result['by_safety'][safety] = sorted(
            result['by_safety'][safety],
            key=lambda x: x['size_bytes'],
            reverse=True
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_search(files: List[Dict], pattern: str) -> List[Dict]:
    """Search files by name pattern (supports glob-like wildcards)."""
    # Convert glob pattern to regex
    regex_pattern = pattern.replace('.', r'\.').replace('*', '.*').replace('?', '.')

    matches = []
    for f in files:
        if re.search(regex_pattern, f['name'], re.IGNORECASE):
            matches.append({
                'path': f['path'],
                'size': format_size(f['size']),
                'size_bytes': f['size'],
                'is_dir': f['is_dir']
            })

    # Sort by size
    matches = sorted(matches, key=lambda x: x['size_bytes'], reverse=True)[:100]

    result = {'pattern': pattern, 'matches': matches, 'count': len(matches)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_filter(files: List[Dict], conditions: str) -> List[Dict]:
    """
    Filter files by conditions.

    Conditions format: "size>1GB,ext=.log,path~Downloads"
    Operators: > < = ~ (contains)
    """
    def parse_condition(cond: str) -> Tuple[str, str, str]:
        for op in ['>=', '<=', '>', '<', '=', '~']:
            if op in cond:
                parts = cond.split(op, 1)
                return parts[0].strip(), op, parts[1].strip()
        return cond, '=', 'true'

    def matches_condition(f: Dict, field: str, op: str, value: str) -> bool:
        if field == 'size':
            file_size = f['size']
            cmp_size = parse_size(value)
            if op == '>': return file_size > cmp_size
            if op == '>=': return file_size >= cmp_size
            if op == '<': return file_size < cmp_size
            if op == '<=': return file_size <= cmp_size
            if op == '=': return file_size == cmp_size
        elif field == 'ext':
            file_ext = f['ext'].lower()
            cmp_ext = value.lower() if value.startswith('.') else '.' + value.lower()
            return file_ext == cmp_ext
        elif field == 'path':
            if op == '~':
                return value.lower() in f['path'].lower()
            return f['path'].lower() == value.lower()
        elif field == 'name':
            if op == '~':
                return value.lower() in f['name'].lower()
            return f['name'].lower() == value.lower()
        elif field == 'depth':
            file_depth = f.get('depth', 0)
            cmp_depth = int(value)
            if op == '>': return file_depth > cmp_depth
            if op == '>=': return file_depth >= cmp_depth
            if op == '<': return file_depth < cmp_depth
            if op == '<=': return file_depth <= cmp_depth
            if op == '=': return file_depth == cmp_depth
        return True

    # Parse all conditions
    cond_list = [parse_condition(c.strip()) for c in conditions.split(',')]

    matches = []
    for f in files:
        if f['is_dir']:
            continue
        if all(matches_condition(f, field, op, val) for field, op, val in cond_list):
            matches.append({
                'path': f['path'],
                'size': format_size(f['size']),
                'size_bytes': f['size']
            })

    matches = sorted(matches, key=lambda x: x['size_bytes'], reverse=True)[:100]

    result = {'conditions': conditions, 'matches': matches, 'count': len(matches)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    csv_path = sys.argv[1]
    command = sys.argv[2].lower()

    if not Path(csv_path).exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    # Parse common options
    def get_option(name: str, default: int) -> int:
        if name in sys.argv:
            idx = sys.argv.index(name)
            if idx + 1 < len(sys.argv):
                return int(sys.argv[idx + 1])
        return default

    files = read_csv(csv_path)

    if command == 'summary':
        cmd_summary(files)
    elif command == 'largest':
        limit = get_option('--limit', 20)
        cmd_largest(files, limit)
    elif command == 'by-type':
        limit = get_option('--limit', 30)
        cmd_by_type(files, limit)
    elif command == 'top-folders':
        depth = get_option('--depth', 2)
        limit = get_option('--limit', 10)
        cmd_top_folders(files, depth, limit)
    elif command == 'folder':
        if len(sys.argv) < 4:
            print("Usage: analyze_disk.py <csv> folder <path> [--depth N]", file=sys.stderr)
            sys.exit(1)
        target_path = sys.argv[3]
        depth = get_option('--depth', 1)
        cmd_folder(files, target_path, depth)
    elif command == 'cleanable':
        cmd_cleanable(files)
    elif command == 'search':
        if len(sys.argv) < 4:
            print("Usage: analyze_disk.py <csv> search <pattern>", file=sys.stderr)
            sys.exit(1)
        cmd_search(files, sys.argv[3])
    elif command == 'filter':
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
