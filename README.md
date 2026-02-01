# Disk Space Analyzer

Analyze disk space and find cleanable files. Works with Claude Code, other AI assistants, or standalone.

## Features

- **Smart Detection** - Identifies temp files, caches, logs, dev artifacts (node_modules, __pycache__, .vs, obj)
- **Safety Levels** - Categorizes files as safe / check first / admin required
- **Migration Hints** - Suggests how to relocate large caches (npm, pip, uv, HuggingFace, Docker)
- **Flexible Analysis** - Search, filter, explore folders at any depth
- **Cross-Platform** - Supports Windows (via WizTree) and macOS

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
| cache | pip/npm/uv cache, app caches | Safe |
| log | .log, rotated logs | Check first |
| dev | node_modules, __pycache__, .vs, obj | Safe |
| browser | Chrome/Firefox/Edge cache | Safe |
| windows | Update cache, hiberfil.sys | Admin required |

## Integration

The scripts output JSON - any AI can parse and use them. Point your AI at the `skills/disk-space-analyzer/` folder and ask it to analyze your disk.

## License

MIT
