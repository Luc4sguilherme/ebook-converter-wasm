#!/usr/bin/env python3
"""
Find all missing modules by iteratively trying to import calibre.ebooks.conversion.cli
and recording what's missing.
"""
import zipfile
import os

ZIP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dist', 'calibre-python.zip')

with zipfile.ZipFile(ZIP_PATH) as z:
    all_files = set(z.namelist())

ebook_files = sorted(f for f in all_files if f.startswith('calibre/ebooks/') and f.endswith('.py'))
print(f"Total ebook files: {len(ebook_files)}")
for f in ebook_files:
    print(f"  {f}")

print("\n=== All __init__.py files ===")
init_files = sorted(f for f in all_files if f.endswith('__init__.py'))
for f in init_files:
    print(f"  {f}")
