#!/usr/bin/env python3
"""
Run WizTree and wait for export to complete.

Usage:
    python run_wiztree.py <wiztree_path> <drive> <output_csv> [options]

Options:
    --timeout N     Maximum wait time in seconds (default: 600 = 10 minutes)

Example:
    python run_wiztree.py "C:/Program Files/WizTree/WizTree64.exe" "C:" "./disk_report.csv"
    python run_wiztree.py "C:/WizTree/WizTree64.exe" "D:" "./report.csv" --timeout 1800

WizTree runs asynchronously, so this script waits for the process to exit then checks the output.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def is_wiztree_running():
    """Check if any WizTree process is running."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq WizTree64.exe"],
            capture_output=True,
            text=True,
        )
        if "WizTree64.exe" in result.stdout:
            return True
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq WizTree.exe"],
            capture_output=True,
            text=True,
        )
        return "WizTree.exe" in result.stdout
    except Exception:
        return False


def run_wiztree(wiztree_path: str, drive: str, output_csv: str, timeout: int = 600):
    """
    Run WizTree export and wait for completion.

    Args:
        wiztree_path: Path to WizTree executable
        drive: Drive letter (e.g., "C:" or "C")
        output_csv: Output CSV file path
        timeout: Maximum wait time in seconds (default 10 minutes)

    Returns:
        True if successful, False otherwise
    """
    # Normalize drive letter
    drive = drive.rstrip(":/\\") + ":"

    # Resolve output path to absolute
    output_path = Path(output_csv).resolve()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing file if present (clean up previous runs)
    if output_path.exists():
        print(f"Removing previous report: {output_path}")
        output_path.unlink()

    # Build command
    # WizTree format: WizTree64.exe "C:" /export="output.csv" /admin=0
    cmd = [
        wiztree_path,
        drive,
        f'/export={output_path}',
        '/admin=0',  # Don't require admin (may limit some results)
    ]

    print(f"Running: {' '.join(cmd)}")

    try:
        # Start WizTree process
        subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for WizTree to finish (monitor process, not just file)
        start_time = time.time()
        last_size = -1

        while time.time() - start_time < timeout:
            # Show progress if file exists
            if output_path.exists():
                try:
                    current_size = output_path.stat().st_size
                    if current_size != last_size:
                        print(f"Exporting... {current_size:,} bytes", end='\r')
                        last_size = current_size
                except OSError:
                    pass  # File might be locked

            # Check if WizTree process has exited
            if not is_wiztree_running():
                print()  # New line after progress
                break

            time.sleep(1)
        else:
            # Timeout reached, but still check if file was created
            print(f"\nTimeout after {timeout} seconds, checking results...")

        # Final check: does the output file exist?
        if output_path.exists():
            size = output_path.stat().st_size
            if size > 0:
                print(f"Export complete: {output_path} ({size:,} bytes)")
                return True
            else:
                print("Error: Output file is empty", file=sys.stderr)
                return False
        else:
            print(f"Error: Output file not created: {output_path}", file=sys.stderr)
            return False

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run WizTree export and wait for completion."
    )
    parser.add_argument("wiztree_path", help="Path to WizTree executable")
    parser.add_argument("drive", help="Drive letter to scan (e.g. C: or D:)")
    parser.add_argument("output_csv", help="Output CSV file path")
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Maximum wait time in seconds (default: 600 = 10 minutes).",
    )
    args = parser.parse_args()

    if not Path(args.wiztree_path).exists():
        print(f"Error: WizTree not found at {args.wiztree_path}", file=sys.stderr)
        sys.exit(1)

    success = run_wiztree(args.wiztree_path, args.drive, args.output_csv, args.timeout)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
