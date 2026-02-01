# Disk Space Analyzer — macOS

**Use this document only when the current system is macOS.** Data source: Python scan script. Scripts: `scripts/macos/` (macOS-only; do not use Windows scripts or WizTree).

**Run all commands from the skill directory** (the folder that contains `scripts/`). In Cursor, run from the skill folder or a workspace that includes it.

## Workflow Overview

```
1. Select volume/path → 2. Scan and export CSV → 3. Analyze and recommend
```

## Step 1: Choose target volume/path

List mounted volumes and usage:

```bash
df -h
```

Or list disks and volumes:

```bash
diskutil list
```

To get a JSON list of volumes (mount point, total/free space) for scripting:

```bash
python3 scripts/macos/list_volumes.py
```

Common choices:

- **`/`** — whole system volume (scan can be long)
- **`/Users/<username>`** — user home only (recommended first)
- **`/Volumes/<name>`** — other mounted volumes (e.g. external drive)

If the user has not specified a path, show the output of `df -h`, suggest starting with the volume that has the **least free space**, and recommend `/Users/<username>` for a quicker first run.

## Step 2: Scan and export CSV

### Permissions note

Scanning may trigger multiple macOS permission dialogs (e.g., Photos, iCloud Drive, Desktop, Documents). To avoid repeated prompts:

1. **One-time solution**: Grant **Full Disk Access** to your terminal app:
   - Open **System Settings → Privacy & Security → Full Disk Access**
   - Add your terminal app (Terminal, iTerm2, Warp, etc.) or IDE (Cursor, VS Code)
   - Restart the terminal after granting access

2. **Alternative**: Click "Allow" for each permission dialog as they appear during the scan.

Without Full Disk Access, some directories may be skipped or show 0 bytes.

From the **skill directory**:

```bash
python3 scripts/macos/scan_disk.py <root_path> <output_csv> [options]
```

**Arguments:**
- **root_path** — e.g. `/`, `/Users/username`, `/Volumes/Data`
- **output_csv** — e.g. `./disk_report.csv` or `<scratchpad>/disk_report.csv`

**Options:**
- **--skip-hidden** — skip files and directories whose name starts with `.` (reduces scan size; default is to include them so caches like `.cache` are analyzed)
- **--max-depth N** — limit scan to N levels deep (useful for quick overview of large directories)
- **--exclude PATTERN** — exclude paths matching pattern (can be used multiple times). Supports glob patterns: `node_modules`, `*.log`, `Library/Caches`

Scanning a large tree can take a long time. Progress is printed to stderr (e.g. every 10,000 entries and every 5 seconds).

**Examples:**

```bash
# Full scan of user home
python3 scripts/macos/scan_disk.py /Users/username ./disk_report.csv

# Quick scan (skip hidden files, limit depth)
python3 scripts/macos/scan_disk.py /Users/username ./disk_report.csv --skip-hidden --max-depth 5

# Skip node_modules and build directories
python3 scripts/macos/scan_disk.py /Users/username ./disk_report.csv --exclude node_modules --exclude build --exclude .git
```

## Step 3: Analyze results

All analysis commands output **JSON** to stdout. Use them to avoid loading large data into context.

### Quick start (recommended order)

```bash
# 1. Overview
python3 scripts/macos/analyze_disk.py <csv> summary

# 2. Quick wins — cleanable files with explanations
python3 scripts/macos/analyze_disk.py <csv> cleanable

# 3. If needed, explore largest files/folders
python3 scripts/macos/analyze_disk.py <csv> largest --limit 20
python3 scripts/macos/analyze_disk.py <csv> top-folders --depth 2
```

### Available commands

#### `summary` — disk overview

```bash
python3 scripts/macos/analyze_disk.py <csv> summary
```

Shows: total size, file count, directory count, top extensions by size.

#### `cleanable` — find cleanable files with reasons

```bash
python3 scripts/macos/analyze_disk.py <csv> cleanable
```

Identifies temp files, caches, logs, dev artifacts, etc., with explanations and migration suggestions.

#### `largest` — largest files

```bash
python3 scripts/macos/analyze_disk.py <csv> largest [--limit N]
```

Default: top 20 files by size.

#### `by-type` — space by extension

```bash
python3 scripts/macos/analyze_disk.py <csv> by-type [--limit N]
```

Shows which file types use the most space.

#### `top-folders` — largest folders by depth

```bash
python3 scripts/macos/analyze_disk.py <csv> top-folders [--depth N] [--limit N]
```

Shows largest folders at each depth level **relative to the scan root** (default depth: 2). Useful for hierarchical exploration.

Example (if scanned from `/`):

- Depth 1: `/Users` (450 GB), `/Applications` (80 GB), …
- Depth 2: `/Users/username` (448 GB), `/Applications/Xcode.app` (15 GB), …

Example (if scanned from `/Users/username`):

- Depth 1: `Library` (12 GB), `Projects` (5 GB), `Downloads` (2 GB), …
- Depth 2: `Library/Caches` (8 GB), `Library/Application Support` (3 GB), …

#### `folder` — explore a specific folder

```bash
python3 scripts/macos/analyze_disk.py <csv> folder "<path>" [--depth N]
```

Shows contents of a folder with size breakdown. Depth controls how many levels to show (default: 1).

Example:

```bash
python3 scripts/macos/analyze_disk.py disk_report.csv folder "/Users/username/Library/Caches" --depth 2
```

#### `search` — search by pattern

```bash
python3 scripts/macos/analyze_disk.py <csv> search "<pattern>"
```

Glob-style pattern (`*`, `?`). Examples:

- `*.log` — all .log files
- `node_modules` — all node_modules directories
- `*backup*` — names containing "backup"

#### `filter` — advanced filtering

```bash
python3 scripts/macos/analyze_disk.py <csv> filter "<conditions>"
```

Conditions: `size>1GB`, `ext=.log`, `path~Downloads`, `name~backup`  
Operators: `>`, `<`, `>=`, `<=`, `=`, `~` (contains)

Examples:

```bash
python3 scripts/macos/analyze_disk.py disk_report.csv filter "size>1GB,ext=.log"
python3 scripts/macos/analyze_disk.py disk_report.csv filter "path~Downloads,size>100MB"
```

## Cleanable categories (macOS)

| Category   | Examples                                      | Safety   | Notes                          |
|-----------|------------------------------------------------|----------|--------------------------------|
| temp      | .tmp, .temp, ~files                            | Safe     | Regenerates on demand          |
| cache     | ~/Library/Caches, .cache, .npm, pip/uv/HF      | Safe     | Often relocatable              |
| log       | .log, ~/Library/Logs                           | Check    | Check if needed for debugging  |
| backup    | .bak, .old, .orig                              | Check    | May be important backups       |
| dev       | node_modules, __pycache__, .venv, .idea, build | Safe     | Recreate with install/build    |
| browser   | Safari, app caches                             | Safe     | Regenerates                    |
| system    | .DS_Store, CloudKit cache                      | Check    | System/cloud caches            |
| recycle   | .Trash                                         | Check    | Empty Trash in Finder          |
| download  | .dmg, .pkg, .zip in Downloads                  | Check    | Review before deleting         |
| duplicate | (1).jpg, copy.png                             | Check    | Verify before deleting         |

## Cache migration suggestions (macOS)

Many caches can be moved to another volume. The `cleanable` command suggests these when detected:

| Cache     | Default location (macOS)           | How to relocate                          |
|-----------|------------------------------------|------------------------------------------|
| npm      | `~/.npm` / npm-cache               | `npm config set cache ~/cache/npm`       |
| pip      | `~/.cache/pip`                     | Set `PIP_CACHE_DIR` env var              |
| uv       | `~/.cache/uv`                      | Set `UV_CACHE_DIR` env var              |
| Yarn     | `~/.yarn/cache`                    | `yarn config set cache-folder ~/cache/yarn` |
| pnpm     | `~/.pnpm/store`                    | `pnpm config set store-dir ~/cache/pnpm` |
| Cargo    | `~/.cargo/registry`                | Set `CARGO_HOME` env var                 |
| HuggingFace | `~/.cache/huggingface`           | Set `HF_HOME` env var                    |
| Docker   | Docker Desktop data                | Docker Desktop → Settings → Resources    |

## System / special files (macOS)

These are **not** removed by the skill; manage them via system settings or documentation.

- **sleepimage** — hibernation image (e.g. under `/var/vm`). Size ~ RAM. Managed by system; avoid deleting by hand.
- **swapfile** — swap files. Managed by macOS.
- **Time Machine local snapshots** — `tmutil listlocalsnapshots`; remove with `tmutil deletelocalsnapshots <date>` or System Settings → General → Storage.
- **System volumes** — avoid deleting files in `/System`, `/Library`, or other system paths; use System Settings or official tools.

## Workflow tips

1. **Start with `cleanable`** — low-risk quick wins.
2. **Use `top-folders --depth 2`** — see where space is used.
3. **Drill down with `folder`** — inspect specific directories.
4. **Use `filter`** — find specific patterns (size, extension, path).

## Cleanup

After analysis is complete, remind the user to delete the temporary CSV file:

```bash
rm <output_csv>
# e.g. rm ./disk_report.csv
```

The CSV can be large (tens to hundreds of MB) and is no longer needed once analysis is done.

## Deletion guidelines

**Do not delete files automatically.** Instead:

1. Present results with clear explanations and safety levels.
2. Let the user decide what to delete.
3. For batch deletion, provide **bash/zsh** commands they can run themselves, for example:

   ```bash
   # Example: remove .tmp files in a directory
   find /path/to/dir -name "*.tmp" -type f -delete

   # Example: clear npm cache
   npm cache clean --force

   # Example: remove a cache directory (review path first)
   rm -rf ~/Library/Caches/SomeApp
   ```

4. Warn about system directories and permissions (e.g. `sudo`, `/System`, `/Library`). Prefer user-level paths like `~/Library/Caches` and app-specific cleanup commands.
