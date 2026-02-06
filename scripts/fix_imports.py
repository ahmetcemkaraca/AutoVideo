#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import Fix Script for AutoVideo Project

This script automatically fixes identified import issues in the codebase.
"""

import re
from pathlib import Path


def fix_main_py_subprocess_import(file_path: Path) -> bool:
    """
    Fix missing subprocess import in video_renderer/main.py

    Args:
        file_path: Path to main.py file

    Returns:
        True if file was modified, False otherwise
    """
    content = file_path.read_text(encoding="utf-8")

    # Check if subprocess is already imported at module level
    if re.search(r'^import subprocess\s*$', content, re.MULTILINE):
        print(f"  [OK] subprocess already imported in {file_path.name}")
        return False

    # Find the imports section (after shebang and docstring)
    # Look for the pattern: import json, import sys, etc.
    imports_end_match = re.search(
        r'^(from typing import .*?)\n',
        content,
        re.MULTILINE
    )

    if not imports_end_match:
        print(f"  [ERROR] Could not find import section in {file_path.name}")
        return False

    insert_pos = imports_end_match.end()

    # Insert subprocess import
    new_content = content[:insert_pos] + "import subprocess\n" + content[insert_pos:]

    # Write back
    file_path.write_text(new_content, encoding="utf-8")
    print(f"  [OK] Added subprocess import to {file_path.name}")
    return True


def remove_duplicate_subprocess_imports_audio(file_path: Path) -> bool:
    """
    Remove redundant subprocess imports from video_renderer/audio.py

    Args:
        file_path: Path to audio.py file

    Returns:
        True if file was modified, False otherwise
    """
    content = file_path.read_text(encoding="utf-8")

    # Check if subprocess is imported at module level
    module_import = re.search(r'^import subprocess\s*$', content, re.MULTILINE)
    if not module_import:
        print(f"  [ERROR] subprocess not found at module level in {file_path.name}")
        return False

    # Find all local subprocess imports (inside functions)
    # Pattern: 4+ spaces followed by "import subprocess"
    local_imports = list(re.finditer(r'(\s{4,})import subprocess\s*\n', content))

    if not local_imports:
        print(f"  [OK] No redundant subprocess imports in {file_path.name}")
        return False

    # Remove local imports (in reverse order to preserve positions)
    modified = False
    for match in reversed(local_imports):
        content = content[:match.start()] + content[match.end():]
        modified = True

    if modified:
        file_path.write_text(content, encoding="utf-8")
        print(f"  [OK] Removed {len(local_imports)} redundant subprocess import(s) from {file_path.name}")

    return modified


def validate_imports(file_path: Path) -> list:
    """
    Validate imports in a Python file

    Args:
        file_path: Path to Python file

    Returns:
        List of (line_number, error_message) tuples
    """
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    errors = []

    # Find all import statements
    imports = {}
    for i, line in enumerate(lines, 1):
        match = re.match(r'^(?:from (\S+) )?import (\S+)', line.strip())
        if match:
            module = match.group(1) or match.group(2)
            imports[module] = i

    # Check for usage of modules without imports
    # This is a simple heuristic - full analysis would require AST parsing

    return errors


def main():
    """Main entry point"""
    base_dir = Path.cwd()

    print("=" * 60)
    print("AutoVideo Import Fix Script")
    print("=" * 60)
    print()

    # Fix video_renderer/main.py
    print("[1/2] Fixing video_renderer/main.py...")
    main_py = base_dir / "video_renderer" / "main.py"
    if main_py.exists():
        fix_main_py_subprocess_import(main_py)
    else:
        print(f"  [ERROR] File not found: {main_py}")

    print()

    # Fix video_renderer/audio.py
    print("[2/2] Optimizing video_renderer/audio.py...")
    audio_py = base_dir / "video_renderer" / "audio.py"
    if audio_py.exists():
        remove_duplicate_subprocess_imports_audio(audio_py)
    else:
        print(f"  [ERROR] File not found: {audio_py}")

    print()
    print("=" * 60)
    print("Import fixes complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Test imports: python -c 'import video_renderer'")
    print("  2. Run tests: python -m pytest tests/ -v")
    print()


if __name__ == "__main__":
    main()
