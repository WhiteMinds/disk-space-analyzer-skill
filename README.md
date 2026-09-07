# Disk Space Analyzer

Analyze disk space and find cleanable files. Works with Claude Code, other AI assistants, or standalone.

## Features

- **Smart Detection** - Identifies temp files, caches, logs, dev artifacts (node_modules, __pycache__, .vs, obj)
- **Safety Levels** - Categorizes files as safe / check first / admin required; protects Git and IDE metadata
- **Migration Hints** - Suggests how to relocate large caches (npm, pip, uv, HuggingFace, Docker)
- **Flexible Analysis** - Search, filter, explore folders at any depth
- **Cross-Platform** - Supports Windows (via WizTree) and macOS

## Demo

https://github.com/user-attachments/assets/b559c502-a1ad-4e1b-98bf-1bf0b550d65e

## Requirements

- Python 3.8+
- **Windows**: [WizTree](https://diskanalyzer.com/) (free, portable version works)
- **macOS**: No additional tools required

## Installation

### Claude Code

#### Option 1: From Marketplace (Recommended)

```
/plugin marketplace add WhiteMinds/disk-space-analyzer-skill
/plugin install disk-space-analyzer@disk-space-analyzer-skill
```

#### Option 2: From GitHub

```
/plugin install https://github.com/WhiteMinds/disk-space-analyzer-skill
```

#### Option 3: Manual - Global Installation

**macOS/Linux:**
```bash
git clone https://github.com/WhiteMinds/disk-space-analyzer-skill.git /tmp/disk-space-analyzer-temp
mkdir -p ~/.claude/skills
cp -r /tmp/disk-space-analyzer-temp/skills/disk-space-analyzer ~/.claude/skills/
rm -rf /tmp/disk-space-analyzer-temp
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/WhiteMinds/disk-space-analyzer-skill.git $env:TEMP\disk-space-analyzer-temp
New-Item -ItemType Directory -Force -Path $env:USERPROFILE\.claude\skills
Copy-Item -Recurse $env:TEMP\disk-space-analyzer-temp\skills\disk-space-analyzer $env:USERPROFILE\.claude\skills\
Remove-Item -Recurse -Force $env:TEMP\disk-space-analyzer-temp
```

#### Option 4: Manual - Project-Specific Installation

**macOS/Linux:**
```bash
git clone https://github.com/WhiteMinds/disk-space-analyzer-skill.git /tmp/disk-space-analyzer-temp
mkdir -p .claude/skills
cp -r /tmp/disk-space-analyzer-temp/skills/disk-space-analyzer .claude/skills/
rm -rf /tmp/disk-space-analyzer-temp
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/WhiteMinds/disk-space-analyzer-skill.git $env:TEMP\disk-space-analyzer-temp
New-Item -ItemType Directory -Force -Path .claude\skills
Copy-Item -Recurse $env:TEMP\disk-space-analyzer-temp\skills\disk-space-analyzer .claude\skills\
Remove-Item -Recurse -Force $env:TEMP\disk-space-analyzer-temp
```

### Cursor

Copy the `skills/disk-space-analyzer/` folder to your Cursor skills directory:

- **macOS/Linux**: `~/.cursor/skills/disk-space-analyzer/`
- **Windows**: `%USERPROFILE%\.cursor\skills\disk-space-analyzer\`

### Standalone / Other AI Tools

```bash
git clone https://github.com/WhiteMinds/disk-space-analyzer-skill
cd disk-space-analyzer-skill/skills/disk-space-analyzer
```

No dependencies required - uses Python standard library only.

## Usage

### With AI Assistants

Once installed, just ask naturally:
- "clean my disk"
- "what's taking up space on C:?"
- "find large files"
- "analyze disk usage"

The AI will automatically detect your OS and use the appropriate workflow.

<details>
<summary><b>Example Session (Windows)</b></summary>

```
❯ /disk-space-analyzer C:

● I'll analyze your C: drive disk space. Let me first check the OS and then read the Windows workflow documentation.

● Bash(python3 -c "import sys; print(sys.platform)")
  ⎿  win32

● Read 1 file (ctrl+o to expand)

● You're on Windows. Let me set up WizTree and start the disk analysis.

● Bash(cd "...\disk-space-analyzer" && python scripts/windows/find_wiztree.…)
  ⎿  C:\Users\white\.wiztree\WizTree64.exe

● WizTree is available. Now let me run it to scan your C: drive and export the data.

● Bash(cd "...\disk-space-analyzer" && python scripts/windows/run_wiztree.p…)
  ⎿ Running: C:\Users\white\.wiztree\WizTree64.exe C: /export=...\disk_report.csv /admin=0
    Exporting... 32,616,892 bytes
    Exporting... 71,684,470 bytes
    … +7 lines (ctrl+o to expand)

● Scan complete. Now let me analyze the disk space usage.

● C: Drive Disk Space Analysis

  Overview
  ┌─────────────────────┬───────────┐
  │       Metric        │   Value   │
  ├─────────────────────┼───────────┤
  │ Total Used          │ 846.5 GB  │
  ├─────────────────────┼───────────┤
  │ Total Files         │ 3,935,901 │
  ├─────────────────────┼───────────┤
  │ Potential Cleanable │ ~247 GB   │
  └─────────────────────┴───────────┘

  Top Space Consumers by Folder
  ┌───────────────────────────┬──────────┐
  │         Location          │   Size   │
  ├───────────────────────────┼──────────┤
  │ C:\Users\white\           │ 458.9 GB │
  ├───────────────────────────┼──────────┤
  │ C:\ProgramData\Microsoft\ │ 136.8 GB │
  ├───────────────────────────┼──────────┤
  │ C:\Windows\System32\      │ 20.6 GB  │
  └───────────────────────────┴──────────┘

  Cleanable Files by Category

  ✅ SAFE to Delete (~122 GB)
  ┌──────────┬──────────┬────────────────────────────────────────────────────────┐
  │ Category │   Size   │                        Details                         │
  ├──────────┼──────────┼────────────────────────────────────────────────────────┤
  │ Cache    │ 101.0 GB │ HuggingFace models (~40 GB), uv cache, npm/yarn cache  │
  ├──────────┼──────────┼────────────────────────────────────────────────────────┤
  │ Temp     │ 9.8 GB   │ Docker scout tars, old disk reports, VS installer temp │
  ├──────────┼──────────┼────────────────────────────────────────────────────────┤
  │ Dev      │ 8.1 GB   │ node_modules CUDA libs, build artifacts                │
  ├──────────┼──────────┼────────────────────────────────────────────────────────┤
  │ Browser  │ 3.4 GB   │ Firefox/Chrome cache                                   │
  └──────────┴──────────┴────────────────────────────────────────────────────────┘

  ⚠️ Check Before Deleting (~30 GB)
  ┌───────────┬──────────┬───────────────────────────────────────────────────────────────┐
  │ Category  │   Size   │                            Details                            │
  ├───────────┼──────────┼───────────────────────────────────────────────────────────────┤
  │ Logs      │ 16.8 GB  │ AMD crash dump (7.6 GB!), Clash Verge logs (5+ GB), game logs │
  ├───────────┼──────────┼───────────────────────────────────────────────────────────────┤
  │ Downloads │ 12.8 GB  │ Old installers: IDA Pro, Warcraft 3, BurpSuite                │
  └───────────┴──────────┴───────────────────────────────────────────────────────────────┘

  🔒 Admin Required (~95 GB)
  ┌──────────────┬─────────┬───────────────────────────────────────────────┐
  │   Category   │  Size   │                    Details                    │
  ├──────────────┼─────────┼───────────────────────────────────────────────┤
  │ pagefile.sys │ 70.0 GB │ Virtual memory (can reduce but not eliminate) │
  ├──────────────┼─────────┼───────────────────────────────────────────────┤
  │ hiberfil.sys │ 25.3 GB │ Hibernation file (can disable if not used)    │
  └──────────────┴─────────┴───────────────────────────────────────────────┘

  Top Recommendations

  Quick Wins (Safe, Immediate)

  1. Clear HuggingFace cache (~40+ GB):
     Remove-Item "C:\Users\white\.cache\huggingface\hub\models--..." -Recurse -Force

  2. Clear temp files (~10 GB):
     Remove-Item "C:\Users\white\AppData\Local\Temp\*" -Recurse -Force

  3. Clear browser caches (~3.4 GB):
     - Firefox: Settings → Privacy → Clear Data
     - Chrome: Settings → Privacy → Clear browsing data

  Cache Migration Suggestions

  Move these caches to another drive if you have space:
  - HuggingFace: set HF_HOME=D:\cache\huggingface
  - uv: set UV_CACHE_DIR=D:\cache\uv
  - npm: npm config set cache D:\cache\npm

  Would you like me to help you clean any specific category?
```

</details>

### Standalone Usage (Windows)

```bash
cd skills/disk-space-analyzer

# 1. Find WizTree
python scripts/windows/find_wiztree.py

# 2. Export with WizTree
python scripts/windows/run_wiztree.py "<wiztree_path>" "C:" "./disk_report.csv"

# 3. Analyze
python scripts/windows/analyze_disk.py disk_report.csv summary
python scripts/windows/analyze_disk.py disk_report.csv cleanable
python scripts/windows/analyze_disk.py disk_report.csv largest --limit 20
python scripts/windows/analyze_disk.py disk_report.csv top-folders --depth 2
python scripts/windows/analyze_disk.py disk_report.csv folder "C:\Users\name\AppData" --depth 2
python scripts/windows/analyze_disk.py disk_report.csv search "*.tmp"
python scripts/windows/analyze_disk.py disk_report.csv filter "size>1GB,ext=.log"
```

### Standalone Usage (macOS)

```bash
cd skills/disk-space-analyzer

# See docs/macos.md for detailed workflow
python scripts/macos/analyze_disk.py
```

## Cleanable Categories

| Category | Examples | Safety |
|----------|----------|--------|
| temp | .tmp, .temp, ~files | Safe |
| cache | pip/npm/uv cache, app caches, AI models | Check first |
| log | .log, rotated logs | Check first |
| dev | node_modules, __pycache__, .vs, obj | Check first |
| browser | Chrome/Firefox/Edge cache | Safe |
| windows | Update cache, hiberfil.sys | Admin required |

## Integration

The scripts output JSON - any AI can parse and use them. Point your AI at the `skills/disk-space-analyzer/` folder and ask it to analyze your disk.

## License

MIT
