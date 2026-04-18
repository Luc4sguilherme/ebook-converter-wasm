"""Stub for calibre.libunzip — pure Python zip extraction for WASM."""
import zipfile
import os

def extract(path, dir=''):
    """Extract a zip file to a directory."""
    if not dir:
        dir = os.path.dirname(path)
    with zipfile.ZipFile(path, 'r') as zf:
        zf.extractall(dir)
    return dir
