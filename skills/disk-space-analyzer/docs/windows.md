# Disk Space Analyzer — Windows

**Use this document only when the current system is Windows.** Data source: WizTree. Scripts: `scripts/windows/` (Windows-only).

**Run all commands from the skill directory** (the folder that contains `scripts/windows/`). In Cursor, run from the skill folder or a workspace that includes it.

## Workflow Overview

```
1. Find/Setup WizTree → 2. Select Drive → 3. Export to CSV → 4. Analyze & Recommend
```

## Step 1: Find or Install WizTree

```bash
python scripts/windows/find_wiztree.py --auto-install
```

This will:
1. Search for existing WizTree installation
2. If not found, automatically download and install the portable version to `~/.wiztree/`
3. Return the path to the executable

The portable version requires no admin rights and doesn't modify system settings.

## Step 2: Select Target Drive

List available drives:
```bash
wmic logicaldisk get name,size,freespace
```

If user hasn't specified a drive, show them the list and ask which to analyze.
Recommend starting with the drive that has the least free space.

## Step 3: Export with WizTree

```bash
python scripts/windows/run_wiztree.py "<wiztree_path>" "<drive>" "<scratchpad>/disk_report.csv" [--timeout N]
```

**Options:**
- `--timeout N` — Maximum wait time in seconds (default: 600 = 10 minutes)

**Examples:**
```bash
python scripts/windows/run_wiztree.py "C:/WizTree/WizTree64.exe" "C:" "./disk_report.csv"
python scripts/windows/run_wiztree.py "C:/WizTree/WizTree64.exe" "D:" "./disk_report.csv" --timeout 1800
```

The script:
1. Removes any previous report file at the output path
2. Launches WizTree and waits for the process to exit
3. Verifies the output file was created successfully

## Step 4: Analyze Results

All commands output JSON for easy parsing. Use these scripts to avoid loading large data into context.

### Quick Start (Recommended Order)

```bash
# 1. Get overview
python scripts/windows/analyze_disk.py <csv> summary

# 2. Find quick wins - cleanable files with explanations
python scripts/windows/analyze_disk.py <csv> cleanable

# 3. If needed, explore largest files/folders
python scripts/windows/analyze_disk.py <csv> largest --limit 20
python scripts/windows/analyze_disk.py <csv> top-folders --depth 2
```

### Available Commands

#### `summary` - Disk overview
```bash
python scripts/windows/analyze_disk.py <csv> summary
```
Shows: total size, file count, top extensions by size.

#### `cleanable` - Find cleanable files with reasons
```bash
python scripts/windows/analyze_disk.py <csv> cleanable
```
Identifies temp files, caches, logs, dev artifacts, etc. with explanations and migration suggestions.

#### `largest` - Largest files
```bash
python scripts/windows/analyze_disk.py <csv> largest [--limit N]
```
Default: top 20 files by size.

#### `by-type` - Space by extension
```bash
python scripts/windows/analyze_disk.py <csv> by-type [--limit N]
```
Shows which file types consume most space.

#### `top-folders` - Largest folders by depth
```bash
python scripts/windows/analyze_disk.py <csv> top-folders [--depth N] [--limit N]
```
Shows largest folders at specified depth (default: 2). Useful for hierarchical exploration.

Example output:
```
Depth 1: C:\Users (450 GB), C:\Program Files (80 GB), ...
Depth 2: C:\Users\white (448 GB), C:\Program Files\Adobe (15 GB), ...
```

#### `folder` - Explore specific folder
```bash
python scripts/windows/analyze_disk.py <csv> folder "<path>" [--depth N]
```
Shows contents of a specific folder with size breakdown. Depth controls how many levels to show (default: 1).

Example:
```bash
python scripts/windows/analyze_disk.py <csv> folder "C:\Users\white\AppData" --depth 2
```

#### `search` - Search by pattern
```bash
python scripts/windows/analyze_disk.py <csv> search "<pattern>"
```
Glob-style pattern matching (*, ?). Examples:
- `*.tmp` - all .tmp files
- `node_modules` - all node_modules folders
- `*backup*` - anything with "backup" in name

#### `filter` - Advanced filtering
```bash
python scripts/windows/analyze_disk.py <csv> filter "<conditions>"
```
Conditions: `size>1GB`, `ext=.log`, `path~Downloads`, `name~backup`
Operators: `>`, `<`, `>=`, `<=`, `=`, `~` (contains)

Examples:
```bash
python scripts/windows/analyze_disk.py <csv> filter "size>1GB,ext=.log"
python scripts/windows/analyze_disk.py <csv> filter "path~AppData,size>100MB"
```

## WizTree Command Line Reference

For advanced usage, WizTree supports these command line options:

### Basic Export
```bash
WizTree64.exe "<drive_or_folder>" /export="<output.csv>" [options]
```

### Common Options

| Option | Description |
|--------|-------------|
| `/export="file.csv"` | Export to CSV file |
| `/admin=0` | Run without admin (default in script) |
| `/admin=1` | Run as admin (more complete results) |
| `/exportfolders=1` | Include folders in export (default) |
| `/exportfiles=1` | Include files in export (default) |
| `/sortby=1` | Sort by size descending |

### Filtering Options

| Option | Description |
|--------|-------------|
| `/filter="*.mp3\|*.wav"` | Only include matching files |
| `/filterexclude="*.tmp"` | Exclude matching files |
| `/filterfullpath=1` | Apply filter to full path, not just filename |

### Examples

```bash
# Scan specific folder only
WizTree64.exe "C:\Users\name" /export="users.csv"

# Filter to only large files (apply manually after export)
WizTree64.exe "C:" /export="disk.csv" /sortby=1

# Exclude temp files from scan
WizTree64.exe "C:" /export="disk.csv" /filterexclude="*.tmp|*.temp"
```

Full documentation: https://diskanalyzer.com/guide

## Cleanable Categories (Windows)

| Category | Examples | Safety | Notes |
|----------|----------|--------|-------|
| temp | .tmp, .temp, ~files | Safe | Regenerates on demand |
| cache | App caches, pip/npm cache | Safe | Can often be relocated |
| log | .log, rotated logs | Usually safe | Check if needed for debugging |
| backup | .bak, .old, .orig | Check first | May contain important backups |
| dev | node_modules, __pycache__, .vs, obj | Safe | `npm install` / `pip install` recreates |
| browser | Chrome/Firefox/Edge cache | Safe | Regenerates automatically |
| windows | WinSxS backup, Update cache | Admin required | Use Disk Cleanup instead |
| system | hiberfil.sys, pagefile.sys | Special | See notes below |
| download | Old installers in Downloads | User discretion | Review before deleting |
| duplicate | Files with (1), - Copy | Verify first | May be intentional copies |

## Cache Migration Suggestions (Windows)

Many caches can be moved to a larger drive. The `cleanable` command will suggest these when detected:

| Cache | Default Location | How to Relocate |
|-------|------------------|-----------------|
| npm | `%AppData%\npm-cache` | `npm config set cache D:\cache\npm` |
| pip | `%LocalAppData%\pip\cache` | Set `PIP_CACHE_DIR` env var |
| uv | `%LocalAppData%\uv\cache` | Set `UV_CACHE_DIR` env var |
| Docker | `%LocalAppData%\Docker` | Docker Desktop Settings → Resources |
| HuggingFace | `%UserProfile%\.cache\huggingface` | Set `HF_HOME` env var |
| VS Code extensions | `%UserProfile%\.vscode` | Use `--extensions-dir` flag |

## System Files Notes (Windows)

**hiberfil.sys** (hibernation file):
- Size: ~75% of RAM
- Disable: `powercfg /h off` (admin cmd)
- Re-enable: `powercfg /h on`

**pagefile.sys** (virtual memory):
- Reduce via: System Properties → Advanced → Performance Settings → Virtual Memory
- Don't disable completely, reduce to 1-2x RAM if needed

**swapfile.sys** (UWP apps swap):
- Usually small (16-256 MB)
- Managed by Windows, not recommended to touch

## Workflow Tips

1. **Start with `cleanable`** - Quick wins without risk
2. **Use `top-folders --depth 2`** - Find where space is used
3. **Drill down with `folder`** - Explore suspicious folders
4. **Use `filter`** - Find specific patterns

## Cleanup

After analysis is complete, remind the user to delete the temporary CSV file:

```powershell
Remove-Item <output_csv>
# e.g. Remove-Item .\disk_report.csv
```

The CSV can be large (tens to hundreds of MB) and is no longer needed once analysis is done.

## Deletion Guidelines

**DO NOT delete files automatically.** Instead:

1. Present findings with clear explanations
2. Group by safety level (safe / check first / admin required)
3. Let user confirm what to delete
4. For batch deletion, provide safe commands:
   ```powershell
   # Example: Delete all .tmp files in a folder
   Remove-Item "C:\path\*.tmp" -Recurse -Force

   # Example: Clear npm cache
   npm cache clean --force
   ```
5. Warn about system files requiring special handling
