#!/usr/bin/env python3
"""
Create comprehensive WASM stubs for all missing calibre modules.
Run from the extracted calibre-python directory.
"""
import os
import re

WORK_DIR = '/tmp/calibre-patch'

def empty_stub(name):
    return f'"""Stub for {name} — not available in WASM."""\n'

def empty_package(name):
    return f'"""Stub package {name} — not available in WASM."""\n'

STUBS = {}

STUBS['calibre/ebooks/chardet/__init__.py'] = '''\
"""calibre.ebooks.chardet — WASM stub using Python chardet or fallback."""
import codecs
import re

def detect(byte_str):
    """Detect encoding of byte string."""
    if not byte_str:
        return {'encoding': 'utf-8', 'confidence': 0.0}
    # Try common encodings
    for enc in ('utf-8', 'ascii', 'latin-1', 'utf-16'):
        try:
            byte_str.decode(enc)
            return {'encoding': enc, 'confidence': 0.9}
        except (UnicodeDecodeError, LookupError):
            continue
    return {'encoding': 'utf-8', 'confidence': 0.5}

def xml_to_unicode(raw, verbose=False, strip_encoding_pats=False,
                   resolve_entities=False, assume_utf8=False):
    """Convert XML bytes to unicode string."""
    if isinstance(raw, str):
        return raw

    # Check for BOM
    if raw[:3] == b'\\xef\\xbb\\xbf':
        return raw[3:].decode('utf-8', 'replace')
    if raw[:2] in (b'\\xff\\xfe', b'\\xfe\\xff'):
        return raw.decode('utf-16', 'replace')

    # Check XML declaration for encoding
    match = re.match(rb'<\\?xml[^>]+encoding=["\\'](.*?)["\\'\\s]', raw[:200])
    if match:
        enc = match.group(1).decode('ascii', 'replace')
        try:
            codecs.lookup(enc)
            return raw.decode(enc, 'replace')
        except LookupError:
            pass

    # Try UTF-8, then latin-1
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('latin-1', 'replace')

def strip_encoding_declarations(raw, limit=50):
    """Remove encoding declarations from XML/HTML."""
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', 'replace')
    # Remove XML encoding declaration
    raw = re.sub(r'<\\?xml[^>]+encoding=["\\'](.*?)["\\'\\s][^>]*\\?>', '', raw[:4096]) + raw[4096:]
    # Remove meta charset
    raw = re.sub(r'<meta[^>]+charset=[^>]+>', '', raw[:4096], flags=re.I) + raw[4096:]
    return raw

def force_encoding(raw, verbose=False, assume_utf8=False):
    """Force raw bytes to unicode."""
    return xml_to_unicode(raw, verbose=verbose, assume_utf8=assume_utf8)
'''

STUBS['calibre/customize/ui.py'] = '''\
"""calibre.customize.ui — WASM-compatible plugin loader."""
from calibre.customize.conversion import InputFormatPlugin, OutputFormatPlugin

_input_plugins = {}
_output_plugins = {}
_initialized = False

def _discover_plugins():
    """Discover conversion plugins from calibre.ebooks.conversion.plugins."""
    global _initialized, _input_plugins, _output_plugins
    if _initialized:
        return
    _initialized = True

    import importlib
    import os
    import pkgutil

    # Try to load conversion plugins
    try:
        import calibre.ebooks.conversion.plugins as pkg
        plugin_dir = os.path.dirname(pkg.__file__)

        for name in sorted(os.listdir(plugin_dir)):
            if not name.endswith('.py') or name.startswith('_'):
                continue
            module_name = f'calibre.ebooks.conversion.plugins.{name[:-3]}'
            try:
                mod = importlib.import_module(module_name)
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if isinstance(attr, type):
                        if issubclass(attr, InputFormatPlugin) and attr is not InputFormatPlugin:
                            for fmt in getattr(attr, 'file_types', []):
                                _input_plugins[fmt.lower()] = attr
                        elif issubclass(attr, OutputFormatPlugin) and attr is not OutputFormatPlugin:
                            fmt = getattr(attr, 'file_type', '')
                            if fmt:
                                _output_plugins[fmt.lower()] = attr
            except Exception as e:
                # Plugin couldn't load (missing deps) — skip it
                pass
    except Exception:
        pass

    # Register basic fallback plugins if discovery failed
    if not _input_plugins:
        _register_basic_plugins()

def _register_basic_plugins():
    """Register minimal built-in plugins for HTML and TXT."""
    global _input_plugins, _output_plugins

    class BasicHTMLInput(InputFormatPlugin):
        name = 'HTML Input'
        file_types = {'html', 'htm', 'xhtml', 'xhtm'}

    class BasicTXTInput(InputFormatPlugin):
        name = 'TXT Input'
        file_types = {'txt', 'text'}

    class BasicTXTOutput(OutputFormatPlugin):
        name = 'TXT Output'
        file_type = 'txt'

    class BasicHTMLOutput(OutputFormatPlugin):
        name = 'HTML Output'
        file_type = 'html'

    for fmt in BasicHTMLInput.file_types:
        _input_plugins[fmt] = BasicHTMLInput
    for fmt in BasicTXTInput.file_types:
        _input_plugins[fmt] = BasicTXTInput
    _output_plugins['txt'] = BasicTXTOutput
    _output_plugins['html'] = BasicHTMLOutput

def available_input_formats():
    _discover_plugins()
    return set(_input_plugins.keys())

def available_output_formats():
    _discover_plugins()
    return set(_output_plugins.keys())

def plugin_for_input_format(fmt):
    _discover_plugins()
    fmt = fmt.lower().lstrip('.')
    plugin_class = _input_plugins.get(fmt)
    if plugin_class is None:
        raise ValueError(f"No input plugin for format: {fmt}")
    return plugin_class('')

def plugin_for_output_format(fmt):
    _discover_plugins()
    fmt = fmt.lower().lstrip('.')
    plugin_class = _output_plugins.get(fmt)
    if plugin_class is None:
        raise ValueError(f"No output plugin for format: {fmt}")
    return plugin_class('')

def input_profiles():
    from calibre.customize.profiles import InputProfile
    return [InputProfile]

def output_profiles():
    from calibre.customize.profiles import OutputProfile
    return [OutputProfile]

def run_plugins_on_preprocess(infile, fmt):
    return infile

def run_plugins_on_postprocess(outfile, fmt):
    return outfile

def plugin_for_catalog_format(fmt):
    return None
'''

STUBS['calibre/customize/profiles.py'] = '''\
"""calibre.customize.profiles — conversion profiles."""
from calibre.customize.conversion import OptionRecommendation

class InputProfile:
    name = 'Default Input Profile'
    short_name = 'default'
    description = 'Default input profile'
    screen_size = (1600, 1200)
    dpi = 167.0
    fbase = 16
    fsizes = [12, 12, 14, 16, 18, 20, 22, 24]
    fkey = 13
    output_profile = False
    comic_screen_size = (1600, 1200)

    @classmethod
    def __eq__(cls, other):
        if hasattr(other, 'short_name'):
            return cls.short_name == other.short_name
        return NotImplemented

class OutputProfile:
    name = 'Default Output Profile'
    short_name = 'default'
    description = 'Default output profile'
    screen_size = (1600, 1200)
    dpi = 167.0
    fbase = 16
    fsizes = [12, 12, 14, 16, 18, 20, 22, 24]
    fkey = 13
    output_profile = True
    comic_screen_size = (1600, 1200)
    minimum_font_size = 0
    mobi_file_type = 'both'

    @classmethod
    def __eq__(cls, other):
        if hasattr(other, 'short_name'):
            return cls.short_name == other.short_name
        return NotImplemented

input_profiles = [InputProfile]
output_profiles = [OutputProfile]
'''

STUBS['calibre/customize/builtins.py'] = '''\
"""calibre.customize.builtins — WASM stub."""
plugins = []
'''

STUBS['calibre/customize/zipplugin.py'] = '''\
"""calibre.customize.zipplugin — WASM stub."""
class CalibrePlugin:
    pass
'''

STUBS['calibre/ebooks/BeautifulSoup.py'] = '''\
"""calibre.ebooks.BeautifulSoup — redirect to html.parser."""
try:
    from html.parser import HTMLParser
except ImportError:
    pass

# Minimal BeautifulSoup-like API
class Tag:
    def __init__(self, name='', attrs=None):
        self.name = name
        self.attrs = attrs or {}
        self.contents = []
        self.string = ''

    def find(self, name=None, attrs=None):
        return None

    def find_all(self, name=None, attrs=None):
        return []

    def get_text(self, separator='', strip=False):
        return self.string

    @property
    def text(self):
        return self.string

class NavigableString(str):
    pass

class BeautifulSoup:
    def __init__(self, markup='', features=None, **kwargs):
        self.markup = markup if isinstance(markup, str) else markup.decode('utf-8', 'replace') if isinstance(markup, bytes) else str(markup)

    def find(self, name=None, attrs=None):
        return None

    def find_all(self, name=None, attrs=None):
        return []

    def get_text(self, separator='', strip=False):
        import re
        text = re.sub(r'<[^>]+>', '', self.markup)
        if strip:
            text = text.strip()
        return text

    @property
    def text(self):
        return self.get_text()

    def __str__(self):
        return self.markup
'''

EMPTY_STUBS = [
    'calibre/db/__init__.py',
    'calibre/db/categories.py',
    'calibre/db/write.py',
    'calibre/devices/__init__.py',
    'calibre/devices/interface.py',
    'calibre/ebooks/azw4/__init__.py',
    'calibre/ebooks/azw4/reader.py',
    'calibre/ebooks/comic/__init__.py',
    'calibre/ebooks/comic/input.py',
    'calibre/ebooks/compression/__init__.py',
    'calibre/ebooks/compression/palmdoc.py',
    'calibre/ebooks/compression/tcr.py',
    'calibre/ebooks/covers.py',
    'calibre/ebooks/djvu/__init__.py',
    'calibre/ebooks/djvu/djvu.py',
    'calibre/ebooks/fb2/__init__.py',
    'calibre/ebooks/fb2/fb2ml.py',
    'calibre/ebooks/html_transform_rules.py',
    'calibre/ebooks/lrf/__init__.py',
    'calibre/ebooks/lrf/html/__init__.py',
    'calibre/ebooks/lrf/html/convert_from.py',
    'calibre/ebooks/lrf/input.py',
    'calibre/ebooks/lrf/lrfparser.py',
    'calibre/ebooks/lrf/pylrs/__init__.py', 
    'calibre/ebooks/lrf/pylrs/pylrs.py',
    'calibre/ebooks/markdown/__init__.py',
    'calibre/ebooks/metadata/book/formatter.py',
    'calibre/ebooks/metadata/book/serialize.py',
    'calibre/ebooks/metadata/fb2.py',
    'calibre/ebooks/metadata/html.py',
    'calibre/ebooks/metadata/meta.py',
    'calibre/ebooks/metadata/odt.py',
    'calibre/ebooks/metadata/opf2.py',
    'calibre/ebooks/metadata/opf3.py',
    'calibre/ebooks/metadata/sources/__init__.py',
    'calibre/ebooks/metadata/sources/base.py',
    'calibre/ebooks/metadata/sources/identify.py',
    'calibre/ebooks/metadata/toc.py',
    'calibre/ebooks/oeb/iterator/book.py',
    'calibre/ebooks/oeb/normalize_css.py',
    'calibre/ebooks/oeb/polish/container.py',
    'calibre/ebooks/oeb/polish/cover.py',
    'calibre/ebooks/oeb/polish/css.py',
    'calibre/ebooks/oeb/polish/parsing.py',
    'calibre/ebooks/oeb/polish/pretty.py',
    'calibre/ebooks/oeb/polish/split.py',
    'calibre/ebooks/oeb/polish/toc.py',
    'calibre/ebooks/oeb/polish/upgrade.py',
    'calibre/ebooks/oeb/polish/utils.py',
    'calibre/ebooks/oeb/stylizer.py',
    'calibre/ebooks/oeb/transforms/data_url.py',
    'calibre/ebooks/oeb/transforms/embed_fonts.py',
    'calibre/ebooks/oeb/transforms/filenames.py',
    'calibre/ebooks/oeb/transforms/guide.py',
    'calibre/ebooks/oeb/transforms/linearize_tables.py',
    'calibre/ebooks/oeb/transforms/rescale.py',
    'calibre/ebooks/pdb/__init__.py',
    'calibre/ebooks/pdb/header.py',
    'calibre/ebooks/pdf/__init__.py',
    'calibre/ebooks/pdf/html_writer.py',
    'calibre/ebooks/pdf/image_writer.py',
    'calibre/ebooks/pdf/pdftohtml.py',
    'calibre/ebooks/pdf/reflow.py',
    'calibre/ebooks/pdf/render/__init__.py',
    'calibre/ebooks/pdf/render/common.py',
    'calibre/ebooks/pml/__init__.py',
    'calibre/ebooks/pml/pmlconverter.py',
    'calibre/ebooks/pml/pmlml.py',
    'calibre/ebooks/rb/__init__.py',
    'calibre/ebooks/rb/reader.py',
    'calibre/ebooks/rb/writer.py',
    'calibre/ebooks/rtf2xml/__init__.py',
    'calibre/ebooks/rtf2xml/ParseRtf.py',
    'calibre/ebooks/snb/__init__.py',
    'calibre/ebooks/snb/snbfile.py',
    'calibre/ebooks/snb/snbml.py',
    'calibre/ebooks/textile/__init__.py',
    'calibre/ebooks/textile/unsmarten.py',
    'calibre/gui2/convert/__init__.py',
    'calibre/gui2/convert/gui_conversion.py',
    'calibre/gui2/tweak_book/__init__.py',
    'calibre/gui2/tweak_book/diff/__init__.py',
    'calibre/gui2/tweak_book/diff/main.py',
    'calibre/library/__init__.py',
    'calibre/library/comments.py',
    'calibre/library/field_metadata.py',
    'calibre/libunzip.py',
    'calibre/scraper/__init__.py',
    'calibre/scraper/simple.py',
    'calibre/translations/__init__.py',
    'calibre/translations/dynamic.py',
    'calibre/utils/config.py',
    'calibre/utils/fonts/__init__.py',
    'calibre/utils/fonts/scanner.py',
    'calibre/utils/fonts/subset.py',
    'calibre/utils/fonts/utils.py',
    'calibre/utils/formatter_functions.py',
    'calibre/utils/html2text.py',
    'calibre/utils/imghdr.py',
    'calibre/utils/ipc/__init__.py',
    'calibre/utils/ipc/simple_worker.py',
    'calibre/utils/iso8601.py',
    'calibre/utils/localunzip.py',
    'calibre/utils/lock.py',
    'calibre/utils/mreplace.py',
    'calibre/utils/shared_file.py',
    'calibre/utils/smartypants.py',
    'calibre/utils/speedups.py',
    'calibre/utils/terminal.py',
    'calibre/utils/unsmarten.py',
    'calibre/utils/webengine.py',
    'calibre/utils/wmf/__init__.py',
    'calibre/utils/wmf/emf.py',
    'calibre/utils/wmf/parse.py',
    'calibre/utils/wordcount.py',
    'calibre/utils/xml_parse.py',
    'calibre/web/__init__.py',
    'calibre/web/feeds/__init__.py',
    'calibre/web/feeds/recipes/__init__.py',
    'calibre/web/feeds/recipes/collection.py',
]

STUBS['calibre/utils/config.py'] = '''\
"""calibre.utils.config — WASM stub."""
import optparse
from calibre.utils.config_base import Config, DynamicConfig, OptionSet, OptionValues, StringConfig, tweaks, prefs

class OptionParser(optparse.OptionParser):
    def __init__(self, usage='', gui_mode=False, conflict_handler='resolve', **kwargs):
        optparse.OptionParser.__init__(self, usage=usage, conflict_handler=conflict_handler, **kwargs)
        self.gui_mode = gui_mode
'''

STUBS['calibre/ptempfile.py'] = '''\
"""calibre.ptempfile — WASM-compatible temp file handling."""
import os
import shutil
import tempfile

_base_dir = os.environ.get('CALIBRE_TEMP_DIR', '/tmp/calibre-convert')

def base_dir():
    os.makedirs(_base_dir, exist_ok=True)
    return _base_dir

class PersistentTemporaryFile:
    def __init__(self, suffix='', prefix='calibre_', dir=None, mode='w+b'):
        if dir is None:
            dir = base_dir()
        os.makedirs(dir, exist_ok=True)
        fd, self.name = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
        self._fd = os.fdopen(fd, mode)

    def write(self, data):
        return self._fd.write(data)

    def read(self, *args):
        return self._fd.read(*args)

    def seek(self, *args):
        return self._fd.seek(*args)

    def tell(self):
        return self._fd.tell()

    def close(self):
        self._fd.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

class PersistentTemporaryDirectory:
    def __init__(self, suffix='', prefix='calibre_', dir=None):
        if dir is None:
            dir = base_dir()
        os.makedirs(dir, exist_ok=True)
        self.tdir = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        self.name = self.tdir

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __enter__(self):
        return self.name

    def __exit__(self, *args):
        try:
            shutil.rmtree(self.tdir)
        except Exception:
            pass

class TemporaryFile(PersistentTemporaryFile):
    def __del__(self):
        try:
            os.unlink(self.name)
        except Exception:
            pass

class TemporaryDirectory(PersistentTemporaryDirectory):
    def __del__(self):
        try:
            shutil.rmtree(self.tdir)
        except Exception:
            pass

def PersistentTemporaryDirectory(suffix='', prefix='calibre_', dir=None):
    if dir is None:
        dir = base_dir()
    os.makedirs(dir, exist_ok=True)
    return tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)

class SpooledTemporaryFile:
    def __init__(self, max_size=50*1024*1024, suffix='', prefix='', dir=None, mode='w+b'):
        if dir is None:
            dir = base_dir()
        os.makedirs(dir, exist_ok=True)
        self._f = tempfile.SpooledTemporaryFile(max_size=max_size, suffix=suffix, prefix=prefix, dir=dir, mode=mode)
        self.name = getattr(self._f, 'name', 'spooled')

    def __getattr__(self, name):
        return getattr(self._f, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._f.close()
'''

STUBS['calibre/utils/xml_parse.py'] = '''\
"""calibre.utils.xml_parse — WASM stub using lxml or stdlib."""
try:
    from lxml import etree
    def safe_xml_fromstring(raw, recover=True):
        if isinstance(raw, str):
            raw = raw.encode('utf-8')
        parser = etree.XMLParser(recover=recover, no_network=True)
        return etree.fromstring(raw, parser=parser)
except ImportError:
    import xml.etree.ElementTree as ET
    def safe_xml_fromstring(raw, recover=True):
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8', 'replace')
        return ET.fromstring(raw)
'''

STUBS['calibre/utils/iso8601.py'] = '''\
"""calibre.utils.iso8601 — WASM stub."""
from datetime import datetime, timezone

def parse_iso8601(date_string, assume_utc=True):
    """Parse ISO 8601 date string."""
    if not date_string:
        return datetime.now(timezone.utc)
    try:
        # Python 3.7+ fromisoformat
        return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)
'''

STUBS['calibre/utils/imghdr.py'] = '''\
"""calibre.utils.imghdr — WASM stub."""
def what(file=None, h=None):
    """Identify image type."""
    if h is None:
        if hasattr(file, 'read'):
            h = file.read(32)
            file.seek(0)
        elif isinstance(file, str):
            with open(file, 'rb') as f:
                h = f.read(32)
        else:
            return None

    if h[:8] == b'\\x89PNG\\r\\n\\x1a\\n':
        return 'png'
    if h[:2] in (b'\\xff\\xd8', b'\\xff\\xe0', b'\\xff\\xe1'):
        return 'jpeg'
    if h[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'
    if h[:4] == b'RIFF' and h[8:12] == b'WEBP':
        return 'webp'
    if h[:2] == b'BM':
        return 'bmp'
    if h[:4] in (b'II\\x2a\\x00', b'MM\\x00\\x2a'):
        return 'tiff'
    if h[:4] == b'\\x00\\x00\\x01\\x00':
        return 'ico'
    return None

def identify(src):
    """Identify image from bytes or file."""
    if isinstance(src, bytes):
        return what(h=src)
    return what(file=src)
'''

STUBS['calibre/utils/html2text.py'] = '''\
"""calibre.utils.html2text — WASM stub."""
import re

def html2text(html, single_line_break=False):
    """Convert HTML to plain text."""
    if not html:
        return ''
    # Remove scripts and styles
    text = re.sub(r'<(script|style)[^>]*>.*?</\\1>', '', html, flags=re.S|re.I)
    # Convert common tags
    text = re.sub(r'<br[^>]*/?>', '\\n', text, flags=re.I)
    text = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\\n', text, flags=re.I)
    text = re.sub(r'<(p|div|h[1-6])\\b[^>]*>', '\\n', text, flags=re.I)
    # Strip remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode entities
    import html as html_mod
    text = html_mod.unescape(text)
    # Clean whitespace
    text = re.sub(r'[ \\t]+', ' ', text)
    text = re.sub(r'\\n{3,}', '\\n\\n', text)
    return text.strip()
'''

STUBS['calibre/utils/mreplace.py'] = '''\
"""calibre.utils.mreplace — WASM stub."""
import re

class MReplace:
    def __init__(self, pat_repl):
        self.pat_repl = pat_repl
    def mreplace(self, text):
        for pat, repl in self.pat_repl:
            text = text.replace(pat, repl)
        return text
'''

STUBS['calibre/utils/wordcount.py'] = '''\
"""calibre.utils.wordcount — WASM stub."""

def wordcount(text):
    if not text:
        return 0
    return len(text.split())
'''

STUBS['calibre/utils/smartypants.py'] = '''\
"""calibre.utils.smartypants — WASM stub."""

def smartyPants(text, attr='1'):
    return text
'''

STUBS['calibre/utils/unsmarten.py'] = '''\
"""calibre.utils.unsmarten — WASM stub."""
REPLACEMENTS = {
    '\\u201c': '"', '\\u201d': '"',
    '\\u2018': "'", '\\u2019': "'",
    '\\u2014': '--', '\\u2013': '-',
    '\\u2026': '...',
}

def unsmarten(text):
    for smart, plain in REPLACEMENTS.items():
        text = text.replace(smart, plain)
    return text
'''

STUBS['calibre/utils/terminal.py'] = '''\
"""calibre.utils.terminal — WASM stub."""

class ANSIStream:
    def __init__(self, stream=None):
        import sys
        self.stream = stream or sys.stdout
    def write(self, text):
        self.stream.write(text)
    def flush(self):
        self.stream.flush()

class ColoredStream:
    def __init__(self, stream=None, fg=None, bg=None, bold=False):
        import sys
        self.stream = stream or sys.stdout
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass

def geometry():
    return 80, 24
'''

STUBS['calibre/utils/lock.py'] = '''\
"""calibre.utils.lock — WASM stub."""
import threading

class ExclusiveFile:
    def __init__(self, path, timeout=15):
        self.path = path
        self._lock = threading.Lock()
    def __enter__(self):
        self._lock.acquire()
        return open(self.path, 'r+b') if __import__('os').path.exists(self.path) else open(self.path, 'w+b')
    def __exit__(self, *args):
        self._lock.release()
'''

STUBS['calibre/utils/shared_file.py'] = '''\
"""calibre.utils.shared_file — WASM stub."""
import builtins

def share_open(path, mode='rb', **kwargs):
    return builtins.open(path, mode, **kwargs)
'''

STUBS['calibre/utils/speedups.py'] = '''\
"""calibre.utils.speedups — WASM stub using calibre_extensions.speedup."""
try:
    from calibre_extensions.speedup import clean_xml_chars
except ImportError:
    import re
    def clean_xml_chars(s):
        return re.sub(r'[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]', '', s) if isinstance(s, str) else s
'''

STUBS['calibre/utils/formatter_functions.py'] = '''\
"""calibre.utils.formatter_functions — WASM stub."""

class FormatterFunction:
    pass

formatter_functions = {}

def load_user_template_functions(*args, **kwargs):
    pass
'''

STUBS['calibre/library/comments.py'] = '''\
"""calibre.library.comments — WASM stub."""
import re

def comments_to_html(comments):
    if not comments:
        return ''
    return comments

def markdown(text):
    return text
'''

STUBS['calibre/library/field_metadata.py'] = '''\
"""calibre.library.field_metadata — WASM stub."""

class FieldMetadata(dict):
    pass

def fm_as_dict():
    return {}
'''

STUBS['calibre/ebooks/markdown/__init__.py'] = '''\
"""calibre.ebooks.markdown — WASM stub."""
def markdown(text, **kwargs):
    return text
'''

STUBS['calibre/ebooks/compression/palmdoc.py'] = '''\
"""calibre.ebooks.compression.palmdoc — WASM stub."""
def decompress_doc(data):
    raise NotImplementedError("PalmDoc decompression not available in WASM")

def compress_doc(data):
    raise NotImplementedError("PalmDoc compression not available in WASM")
'''

STUBS['calibre/ebooks/compression/tcr.py'] = '''\
"""calibre.ebooks.compression.tcr — WASM stub."""
def decompress(data):
    raise NotImplementedError("TCR decompression not available in WASM")
'''

STUBS['calibre/ebooks/covers.py'] = '''\
"""calibre.ebooks.covers — WASM stub."""
def generate_cover(mi=None, *args, **kwargs):
    return None

def create_cover(title='', authors=None, *args, **kwargs):
    return None
'''

STUBS['calibre/ebooks/html_transform_rules.py'] = '''\
"""calibre.ebooks.html_transform_rules — WASM stub."""
def transform_html(container, name, rules):
    pass
'''

STUBS['calibre/ebooks/metadata/meta.py'] = '''\
"""calibre.ebooks.metadata.meta — WASM stub."""
from calibre.ebooks.metadata.book.base import Metadata

def get_metadata(stream, stream_type='html', use_libprs_metadata=True, force_read_metadata=False, pattern=None):
    """Return metadata from stream."""
    return Metadata('Unknown')

def metadata_from_filename(filename, pat=None, fallback_pat=None):
    import os
    name = os.path.splitext(os.path.basename(filename))[0]
    return Metadata(name)
'''

STUBS['calibre/ebooks/metadata/html.py'] = '''\
"""calibre.ebooks.metadata.html — WASM stub."""
import re
from calibre.ebooks.metadata.book.base import Metadata

def get_metadata(stream):
    """Extract metadata from HTML."""
    src = stream.read() if hasattr(stream, 'read') else stream
    if isinstance(src, bytes):
        src = src.decode('utf-8', 'replace')
    title = 'Unknown'
    m = re.search(r'<title[^>]*>(.*?)</title>', src, re.I|re.S)
    if m:
        title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return Metadata(title or 'Unknown')
'''

STUBS['calibre/ebooks/metadata/opf2.py'] = '''\
"""calibre.ebooks.metadata.opf2 — WASM stub."""
from calibre.ebooks.metadata.book.base import Metadata

class OPF:
    def __init__(self, stream, basedir=None, unquote_urls=True, populate_spine=True):
        self.metadata = Metadata('Unknown')

    def to_book_metadata(self):
        return self.metadata
'''

STUBS['calibre/ebooks/metadata/opf3.py'] = '''\
"""calibre.ebooks.metadata.opf3 — WASM stub."""
from calibre.ebooks.metadata.book.base import Metadata

def read_metadata(root, ver=None, return_extra_data=False):
    mi = Metadata('Unknown')
    if return_extra_data:
        return mi, {}
    return mi
'''

STUBS['calibre/ebooks/metadata/toc.py'] = '''\
"""calibre.ebooks.metadata.toc — WASM stub."""

class TOC:
    def __init__(self, title='', href='', id=''):
        self.title = title
        self.href = href
        self.id = id
        self.children = []

    def __iter__(self):
        return iter(self.children)

    def __len__(self):
        return len(self.children)

    def add(self, title='', href='', id=''):
        child = TOC(title, href, id)
        self.children.append(child)
        return child
'''

STUBS['calibre/utils/img.py'] = '''\
"""calibre.utils.img — WASM stub using PIL."""
import io
import os

def null_image():
    return b''

def image_from_data(data):
    try:
        from PIL import Image
        return Image.open(io.BytesIO(data))
    except Exception:
        return None

def image_to_data(img, fmt='PNG'):
    try:
        from PIL import Image
        if isinstance(img, Image.Image):
            buf = io.BytesIO()
            img.save(buf, format=fmt)
            return buf.getvalue()
    except Exception:
        pass
    return b''

def scale_image(data, width=0, height=0, compression_quality=70):
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        if width and height:
            img.thumbnail((width, height), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue(), img.width, img.height
    except Exception:
        return data, 0, 0

def image_from_path(path):
    with open(path, 'rb') as f:
        return image_from_data(f.read())

def save_image(img, path, fmt='PNG'):
    data = image_to_data(img, fmt)
    with open(path, 'wb') as f:
        f.write(data)

def add_borders_to_image(data, *args, **kwargs):
    return data

def resize_image(img, width, height):
    return img

def clone_image(img):
    return img

def image_has_transparent_pixels(data):
    return False

def set_image_allocation_limit(limit=0):
    pass

def Canvas(width, height, bgcolor='#ffffff'):
    try:
        from PIL import Image
        return Image.new('RGBA', (width, height), bgcolor)
    except Exception:
        return None
'''

STUBS['calibre/utils/serialize.py'] = '''\
"""calibre.utils.serialize — WASM stub."""
import json

def json_dumps(obj, **kwargs):
    return json.dumps(obj, ensure_ascii=False, **kwargs)

def json_loads(data, **kwargs):
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    return json.loads(data, **kwargs)

def msgpack_dumps(obj):
    return json.dumps(obj).encode('utf-8')

def msgpack_loads(data):
    return json.loads(data if isinstance(data, str) else data.decode('utf-8'))
'''

STUBS['calibre/utils/short_uuid.py'] = '''\
"""calibre.utils.short_uuid — WASM stub."""
import uuid

def uuid4():
    return str(uuid.uuid4())

def short_uuid():
    return str(uuid.uuid4()).replace('-', '')[:22]
'''

STUBS['calibre/utils/formatter.py'] = '''\
"""calibre.utils.formatter — WASM stub."""

class EvalFormatter:
    def __init__(self):
        pass
    def safe_format(self, fmt, kwargs, error_value='', book=None, column_name=None, template_cache=None):
        try:
            return fmt.format(**kwargs)
        except Exception:
            return error_value

class TemplateFormatter(EvalFormatter):
    pass
'''

STUBS['calibre/utils/webengine.py'] = '''\
"""calibre.utils.webengine — WASM stub (no Qt)."""
raise ImportError("WebEngine not available in WASM")
'''

STUBS['calibre/utils/filenames.py'] = '''\
"""calibre.utils.filenames — WASM-compatible version."""
import os
import re
import shutil

def ascii_filename(orig, substitute='_'):
    """Convert filename to ASCII."""
    if not orig:
        return substitute
    ans = []
    for ch in orig:
        if ord(ch) < 128 and ch not in '\\\\/:*?"<>|':
            ans.append(ch)
        else:
            ans.append(substitute)
    return ''.join(ans).strip() or substitute

def shorten_components_to(length, components, last_has_extension=True):
    return components

def find_executable_in_path(name, path=None):
    return None

def is_case_sensitive(path):
    return True

def case_preserving_open_file(path, mode='rb'):
    return open(path, mode)

def samefile(a, b):
    return os.path.abspath(a) == os.path.abspath(b)

def nlinks_file(path):
    return 1

def WindowsAtomicFolderMove(path):
    raise NotImplementedError("Windows-only")

def hardlink_file(src, dest):
    shutil.copy2(src, dest)

def copytree_using_links(src, dest, dest_is_parent=True):
    if dest_is_parent:
        dest = os.path.join(dest, os.path.basename(src))
    shutil.copytree(src, dest)

def atomic_rename(src, dest):
    os.rename(src, dest)

def make_long_path_useable(path):
    return path

def format_permissions(st_mode):
    return ''
'''

STUBS['calibre/utils/encoding.py'] = '''\
"""calibre.utils.encoding — WASM stub."""

def force_unicode(raw, encoding='utf-8'):
    if isinstance(raw, str):
        return raw
    if isinstance(raw, bytes):
        return raw.decode(encoding, 'replace')
    return str(raw)

def xml_replace_entities(raw, encoding='utf-8'):
    return raw
'''

STUBS['calibre/utils/date.py'] = '''\
"""calibre.utils.date — WASM-compatible version."""
import time as _time
from datetime import datetime, timezone, timedelta
from functools import lru_cache

UNDEFINED_DATE = datetime(101, 1, 1, tzinfo=timezone.utc)
DEFAULT_DATE = datetime(2000, 1, 1, tzinfo=timezone.utc)

try:
    from calibre_extensions.usbobserver import date_format as _date_format
except ImportError:
    def _date_format():
        return 'MMM d yyyy'

def now():
    return datetime.now(timezone.utc)

def utcnow():
    return datetime.now(timezone.utc)

def local_tz():
    return timezone(timedelta(seconds=-_time.timezone))

def as_local_time(dt, assume_utc=True):
    if dt is None:
        return now()
    if not hasattr(dt, 'tzinfo') or dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc if assume_utc else local_tz())
    return dt.astimezone(local_tz())

def dt_as_local(dt):
    return as_local_time(dt)

def as_utc(dt, assume_utc=True):
    if dt is None:
        return now()
    if not hasattr(dt, 'tzinfo') or dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc if assume_utc else local_tz())
    return dt.astimezone(timezone.utc)

def isoformat(dt, as_utc=True, sep='T'):
    if dt is None:
        dt = now()
    if as_utc:
        dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return dt.isoformat(sep=sep)

def parse_date(date_string, assume_utc=True, as_utc=True):
    """Parse a date string."""
    if not date_string:
        return UNDEFINED_DATE
    if isinstance(date_string, datetime):
        return date_string
    try:
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        try:
            # Try common formats
            for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%d/%m/%Y', '%m/%d/%Y',
                        '%B %d, %Y', '%b %d, %Y', '%Y'):
                try:
                    dt = datetime.strptime(date_string.strip(), fmt)
                    break
                except ValueError:
                    continue
            else:
                return UNDEFINED_DATE
        except Exception:
            return UNDEFINED_DATE

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc if assume_utc else local_tz())
    return dt

def format_date(dt, format='dd MMM yyyy', assume_utc=True):
    """Format a date."""
    if dt is None or dt == UNDEFINED_DATE:
        return ''
    if isinstance(dt, str):
        dt = parse_date(dt)
    try:
        return dt.strftime('%d %b %Y')
    except Exception:
        return str(dt)

def is_date_undefined(dt):
    if dt is None:
        return True
    if hasattr(dt, 'year') and dt.year < 200:
        return True
    return False

def clean_date_for_sort(dt, default=None):
    if is_date_undefined(dt):
        return default or UNDEFINED_DATE
    return dt

def strftime(fmt, t=None):
    if t is None:
        t = _time.localtime()
    return _time.strftime(fmt, t)
'''

STUBS['calibre/utils/zipfile.py'] = '''\
"""calibre.utils.zipfile — WASM stub using stdlib zipfile."""
from zipfile import ZipFile, BadZipFile, ZipInfo, ZIP_STORED, ZIP_DEFLATED, is_zipfile

__all__ = ['ZipFile', 'BadZipFile', 'ZipInfo', 'ZIP_STORED', 'ZIP_DEFLATED', 'is_zipfile']
'''

STUBS['calibre/libunzip.py'] = '''\
"""calibre.libunzip — WASM stub."""
import zipfile
import os

def extract(path, dir=''):
    if not dir:
        dir = os.path.dirname(path)
    with zipfile.ZipFile(path) as zf:
        zf.extractall(dir)
    return dir
'''

for relpath, content in STUBS.items():
    fullpath = os.path.join(WORK_DIR, relpath)
    os.makedirs(os.path.dirname(fullpath), exist_ok=True)
    with open(fullpath, 'w') as f:
        f.write(content)
    print(f"  Wrote {relpath}")

for relpath in EMPTY_STUBS:
    fullpath = os.path.join(WORK_DIR, relpath)
    if os.path.exists(fullpath):
        continue  
    os.makedirs(os.path.dirname(fullpath), exist_ok=True)
    module_name = relpath.replace('/', '.').replace('.py', '').replace('.__init__', '')
    with open(fullpath, 'w') as f:
        f.write(f'"""Stub for {module_name} — not available in WASM."""\n')
    print(f"  Wrote (empty) {relpath}")

print(f"\nTotal stubs created: {len(STUBS) + len(EMPTY_STUBS)}")

init_path = os.path.join(WORK_DIR, 'calibre/__init__.py')
with open(init_path, 'r') as f:
    content = f.read()

if 'def extract(' not in content:
    content += '''

def extract(path, dir=''):
    """Extract a zip/rar archive."""
    import zipfile
    import os
    if not dir:
        dir = os.path.dirname(path) or '.'
    with zipfile.ZipFile(path) as zf:
        zf.extractall(dir)
    return dir
'''
    with open(init_path, 'w') as f:
        f.write(content)
    print("  Updated calibre/__init__.py with extract()")

import zipfile as zf_mod
import shutil

ZIP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dist', 'calibre-python.zip')

print(f"\nRebuilding {ZIP_PATH}...")
with zf_mod.ZipFile(ZIP_PATH, 'w', zf_mod.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(WORK_DIR):
        for fname in sorted(files):
            if fname.endswith('.pyc') or '__pycache__' in root:
                continue
            fullpath = os.path.join(root, fname)
            arcname = os.path.relpath(fullpath, WORK_DIR)
            zf.write(fullpath, arcname)

size = os.path.getsize(ZIP_PATH)
with zf_mod.ZipFile(ZIP_PATH) as zf:
    count = len(zf.namelist())
print(f"Size: {size:,} bytes, Files: {count}")
print("Done!")
