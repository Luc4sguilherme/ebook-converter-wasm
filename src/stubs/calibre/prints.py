"""
WASM stub for calibre.prints
"""

import sys

def prints(*a, **kw):
    stream = kw.get('file', sys.stdout)
    if stream is None:
        return
    sep = kw.get('sep', ' ')
    end = kw.get('end', '\n')
    for i, x in enumerate(a):
        if sep and i != 0:
            stream.write(sep)
        stream.write(str(x))
    if end:
        stream.write(end)

def debug_print(*args, **kw):
    pass
