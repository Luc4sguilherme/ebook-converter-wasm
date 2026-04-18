"""
WASM-compatible replacement for calibre.constants

Provides runtime constants, plugin loading, and config directory setup
for the WebAssembly environment.
"""
import atexit
import collections.abc
import importlib
import os
import sys
import tempfile

__appname__ = 'calibre'
numeric_version = (9, 7, 0)
__version__ = '.'.join([str(x) for x in numeric_version])
__author__ = "Kovid Goyal <kovid@kovidgoyal.net>"

FAKE_PROTOCOL = 'calibre'
preferred_encoding = 'utf-8'
filesystem_encoding = 'utf-8'
islinux = False
iswindows = False
ismacos = False
isosx = False
isfreebsd = False
isnetbsd = False
isdragonflybsd = False
isbsd = False
isfrozen = False
is64bit = True
isportable = False
ispy3 = True
DEBUG = os.getenv('CALIBRE_DEBUG') is not None
dark_link_color = '#6cb4ee'
DOWNLOADS_URL = 'https://calibre-ebook.com/download'
XHTML_NS = 'http://www.w3.org/1999/xhtml'

def debug():
    global DEBUG
    DEBUG = True

class Plugins(collections.abc.Mapping):
    """Plugin loader that returns None for unavailable native plugins in WASM."""

    def __init__(self):
        self._plugins = {}
        self.plugins = frozenset([])

    def load_plugin(self, name):
        if name in self._plugins:
            return
        try:
            del sys.modules[name]
        except KeyError:
            pass
        plugin_err = ''
        try:
            p = importlib.import_module(name)
        except Exception as err:
            p = None
            plugin_err = str(err)
        self._plugins[name] = p, plugin_err

    def __iter__(self):
        return iter(self.plugins)

    def __len__(self):
        return len(self.plugins)

    def __contains__(self, name):
        return name in self.plugins

    def __getitem__(self, name):
        if name not in self.plugins:
            return None, f'Plugin {name!r} not available in WASM'
        self.load_plugin(name)
        return self._plugins[name]

plugins = Plugins()

plugins_loc = '/tmp/calibre-plugins'
system_plugins_loc = '/tmp/calibre-system-plugins'

CONFIG_DIR_MODE = 0o700
config_dir = os.environ.get('CALIBRE_CONFIG_DIR', '/tmp/calibre-config')

try:
    os.makedirs(config_dir, mode=CONFIG_DIR_MODE, exist_ok=True)
except OSError:
    config_dir = tempfile.mkdtemp(prefix='calibre-config-')

    def cleanup_cdir():
        import shutil
        try:
            shutil.rmtree(config_dir)
        except OSError:
            pass
    atexit.register(cleanup_cdir)

def get_version():
    v = __version__
    if numeric_version[-1] == 0:
        v = v[:-2]
    return v

def get_appname_for_display():
    return __appname__

def cache_dir():
    d = os.environ.get('CALIBRE_CACHE_DIR', '/tmp/calibre-cache')
    os.makedirs(d, exist_ok=True)
    return d

def get_windows_temp_path():
    return tempfile.gettempdir()

def bundled_binaries_dir():
    """Return None in WASM - no bundled native binaries."""
    return None

def get_windows_username():
    """Return empty string in WASM."""
    return ''
