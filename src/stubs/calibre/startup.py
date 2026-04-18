"""
WASM stub for calibre.startup

The original initialize_calibre() adjusts tempfile, resource limits,
and multiprocessing — none of which apply in WASM.
"""

import builtins

def initialize_calibre():
    if hasattr(initialize_calibre, 'initialized'):
        return
    initialize_calibre.initialized = True
    builtins.__dict__.setdefault('_', lambda s: s)
    builtins.__dict__.setdefault('__', lambda s: s)
    builtins.__dict__.setdefault('dynamic_property', lambda func: func(None))

def get_debug_executable(headless=False, exe_name='calibre-debug'):
    return [exe_name]

def connect_lambda(*a, **kw):
    pass
