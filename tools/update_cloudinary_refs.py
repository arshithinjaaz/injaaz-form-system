#!/usr/bin/env python3
"""
Safe updater: replace occurrences of `get_cloudinary_version()` with `get_cloudinary_version()`
and add the import `from module_site_visit.utils.cloudinary_version import get_cloudinary_version`
to files that need it.

Backups: creates <filename>.bak before modifying.
Run from project root with the venv active.
"""
import re
from pathlib import Path

ROOT = Path.cwd()
EXCLUDE_DIRS = {'venv', '.venv', '__pycache__', '.git', 'node_modules', 'generated'}
IMPORT_LINE = 'from module_site_visit.utils.cloudinary_version import get_cloudinary_version'
PATTERN = re.compile(r'\bcloudinary\.version\b')

def should_skip(path: Path):
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    return False

def process_file(path: Path):
    text = path.read_text(encoding='utf-8')
    if 'get_cloudinary_version()' not in text:
        return False
    new_text = text
    # Add import if not present
    if IMPORT_LINE not in text:
        lines = new_text.splitlines()
        insert_at = 0
        for i, ln in enumerate(lines):
            if ln.strip().startswith('import ') or ln.strip().startswith('from '):
                insert_at = i + 1
        lines.insert(insert_at, IMPORT_LINE)
        new_text = '\n'.join(lines)
    # Replace occurrences
    new_text = PATTERN.sub('get_cloudinary_version()', new_text)
    if new_text != text:
        bak = path.with_suffix(path.suffix + '.bak')
        bak.write_text(text, encoding='utf-8')   # create backup
        path.write_text(new_text, encoding='utf-8')
        print(f'Modified: {path} (backup: {bak})')
        return True
    return False

def main():
    modified = []
    for py in ROOT.rglob('*.py'):
        if should_skip(py):
            continue
        try:
            if process_file(py):
                modified.append(py)
        except Exception as e:
            print(f'Error processing {py}: {e}')
    if not modified:
        print('No occurrences of get_cloudinary_version() found.')
    else:
        print('Done. Please review the .bak files for backups.')

if __name__ == '__main__':
    main()