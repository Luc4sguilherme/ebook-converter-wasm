"""
WASM-compatible replacement for calibre/__init__.py

Provides all public functions from the original calibre package,
with pure-Python fallbacks for C extensions that are unavailable in WASM.
"""

import builtins
import html
import os
import re
import sys
import time
import warnings
from functools import lru_cache, partial
from math import floor

from calibre.constants import (
    __appname__,
    __author__,
    __version__,
    config_dir,
    filesystem_encoding,
    isbsd,
    isfrozen,
    islinux,
    ismacos,
    iswindows,
    plugins,
    preferred_encoding,
)

def _is_debugging():
    return os.getenv('CALIBRE_DEBUG') is not None

is_debugging = _is_debugging

if not os.environ.get('CALIBRE_SHOW_DEPRECATION_WARNINGS'):
    warnings.simplefilter('ignore', DeprecationWarning)

def _initialize_calibre():
    if hasattr(_initialize_calibre, 'initialized'):
        return
    _initialize_calibre.initialized = True
    builtins.__dict__.setdefault('_', lambda s: s)
    builtins.__dict__.setdefault('__', lambda s: s)
    builtins.__dict__.setdefault('dynamic_property', lambda func: func(None))

_initialize_calibre()

def prints(*a, **kw):
    """Print to stream (text or binary)."""
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

def safe_chr(num):
    try:
        return chr(num)
    except (ValueError, OverflowError):
        return '?'

_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

def P(name, data=False, allow_user_override=True):
    """Stub for calibre.utils.resources.get_path."""
    path = os.path.join(_data_dir, name)
    if os.path.exists(path):
        if data:
            with open(path, 'rb') as f:
                return f.read()
        return path

    return path

_mt_inited = False

def _init_mimetypes():
    global _mt_inited
    import mimetypes
    mimetypes.init()

    _extra_types = {
        '.epub': 'application/epub+zip',
        '.xhtml': 'application/xhtml+xml',
        '.ncx': 'application/x-dtbncx+xml',
        '.opf': 'application/oebps-package+xml',
        '.otf': 'font/otf',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.ttf': 'font/ttf',
        '.mobi': 'application/x-mobipocket-ebook',
        '.azw': 'application/vnd.amazon.ebook',
        '.azw3': 'application/vnd.amazon.ebook',
        '.fb2': 'application/x-fictionbook+xml',
        '.lrf': 'application/x-lrf',
        '.pdb': 'application/vnd.palm',
        '.lit': 'application/x-ms-reader',
        '.cbz': 'application/x-cbz',
        '.cbr': 'application/x-cbr',
        '.pml': 'application/x-pml',
        '.rb': 'application/x-rocket-ebook',
        '.snb': 'application/x-snb',
        '.tcr': 'application/x-tcr',
        '.lrx': 'application/x-lrf',
        '.htmlz': 'application/x-htmlz',
        '.txtz': 'application/x-txtz',
        '.svg': 'image/svg+xml',
        '.webp': 'image/webp',
    }
    for ext, mt in _extra_types.items():
        if ext not in mimetypes.types_map:
            mimetypes.add_type(mt, ext)
    _mt_inited = True

@lru_cache(4096)
def guess_type(*args, **kwargs):
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.guess_type(*args, **kwargs)

def guess_all_extensions(*args, **kwargs):
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.guess_all_extensions(*args, **kwargs)

def guess_extension(*args, **kwargs):
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    ext = mimetypes.guess_extension(*args, **kwargs)
    if not ext and args and args[0] == 'application/x-palmreader':
        ext = '.pdb'
    return ext

def get_types_map():
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.types_map

def isbytestring(obj):
    return isinstance(obj, bytes)

def force_unicode(obj, enc=preferred_encoding):
    if isbytestring(obj):
        try:
            obj = obj.decode(enc)
        except Exception:
            try:
                obj = obj.decode(filesystem_encoding if enc ==
                        preferred_encoding else preferred_encoding)
            except Exception:
                try:
                    obj = obj.decode('utf-8')
                except Exception:
                    obj = repr(obj)
                    if isbytestring(obj):
                        obj = obj.decode('utf-8')
    return obj

def as_unicode(obj, enc=preferred_encoding):
    if not isbytestring(obj):
        try:
            obj = str(obj)
        except Exception:
            obj = repr(obj)
    return force_unicode(obj, enc=enc)

def to_unicode(raw, encoding='utf-8', errors='strict'):
    if isinstance(raw, str):
        return raw
    return raw.decode(encoding, errors)

def patheq(p1, p2):
    p = os.path
    def d(x):
        return p.normcase(p.normpath(p.realpath(p.normpath(x))))
    if not p1 or not p2:
        return False
    return d(p1) == d(p2)

def unicode_path(path, abs=False):
    if isinstance(path, bytes):
        path = path.decode(filesystem_encoding)
    if abs:
        path = os.path.abspath(path)
    return path

_filename_sanitize_unicode = frozenset(
    ('\\', '|', '?', '*', '<', '"', ':', '>', '+', '/')
    + tuple(map(chr, range(32)))
)

def sanitize_file_name(name, substitute='_'):
    if isbytestring(name):
        name = name.decode(filesystem_encoding, 'replace')
    if isbytestring(substitute):
        substitute = substitute.decode(filesystem_encoding, 'replace')
    chars = (substitute if c in _filename_sanitize_unicode else c for c in name)
    one = ''.join(chars)
    one = re.sub(r'\s', ' ', one).strip()
    bname, ext = os.path.splitext(one)
    one = re.sub(r'^\.+$', '_', bname)
    one = one.replace('..', substitute)
    one += ext
    if one and one[-1] in ('.', ' '):
        one = one[:-1] + '_'
    if one.startswith('.'):
        one = '_' + one[1:]
    return one

sanitize_file_name2 = sanitize_file_name_unicode = sanitize_file_name

def confirm_config_name(name):
    return name + '_again'

relpath = os.path.relpath

def walk(dir):
    for record in os.walk(dir):
        for f in record[-1]:
            yield os.path.join(record[0], f)

def url_slash_cleaner(url):
    return re.sub(r'(?<!:)/{2,}', '/', url)

_entity_re = re.compile(r'&(#?[a-zA-Z0-9]+);')
_XML_UNSAFE = frozenset('<>&"\'')

def _replace_all_entities_python(raw, xml_replace=False):
    """Pure-Python replacement for calibre_extensions.fast_html_entities.replace_all_entities

    When xml_replace=True (i.e. keep_xml_entities=True in the C extension),
    replace HTML entities EXCEPT those whose resolved character is one of the
    five XML-special characters (<, >, &, ", ').  The original C code leaves
    such entities untouched so that surrounding XML markup is never corrupted.
    """
    if not xml_replace:
        return html.unescape(raw)

    def _replace_entity(m):
        entity = m.group(0)           
        resolved = html.unescape(entity)
        if resolved in _XML_UNSAFE:
            return entity             
        return resolved

    return _entity_re.sub(_replace_entity, raw)

def my_unichr(num):
    try:
        return safe_chr(num)
    except (ValueError, OverflowError):
        return '?'

XML_ENTITIES = {
    '"': '&quot;',
    "'": '&apos;',
    '<': '&lt;',
    '>': '&gt;',
    '&': '&amp;'
}

def entity_to_unicode(match, exceptions=(), encoding=None, result_exceptions={}):
    """
    Convert an HTML entity match to its unicode character.
    Provides a pure Python fallback for calibre_extensions.fast_html_entities.
    """
    try:
        from calibre.ebooks.html_entities import entity_to_unicode_in_python
        if not encoding and not exceptions and (not result_exceptions or result_exceptions is XML_ENTITIES):
            return _replace_all_entities_python(match.group(), result_exceptions is XML_ENTITIES)
        return entity_to_unicode_in_python(match, exceptions, encoding, result_exceptions)
    except ImportError:

        return _replace_all_entities_python(match.group(), result_exceptions is XML_ENTITIES)

xml_entity_to_unicode = partial(entity_to_unicode, result_exceptions=XML_ENTITIES)

@lru_cache(2)
def entity_regex():
    return re.compile(r'&(\S+?);')

def replace_entities(raw, encoding=None):
    return _replace_all_entities_python(raw)

def xml_replace_entities(raw, encoding=None):
    return _replace_all_entities_python(raw, True)

def prepare_string_for_xml(raw, attribute=False):
    raw = replace_entities(raw)
    raw = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if attribute:
        raw = raw.replace('"', '&quot;').replace("'", '&apos;')
    return raw

def strftime(fmt, t=None):
    if not fmt:
        return ''
    if t is None:
        t = time.localtime()
    if hasattr(t, 'timetuple'):
        t = t.timetuple()
    early_year = t[0] < 1900
    if early_year:
        replacement = 1900 if t[0] % 4 == 0 else 1901
        fmt = fmt.replace('%Y', '_early year hack##')
        t = list(t)
        orig_year = t[0]
        t[0] = replacement
        t = time.struct_time(t)
    if isinstance(fmt, bytes):
        fmt = fmt.decode('utf-8', 'replace')
    ans = time.strftime(fmt, t)
    if early_year:
        ans = ans.replace('_early year hack##', str(orig_year))
    return ans

def fit_image(width, height, pwidth, pheight):
    if height < 1 or width < 1:
        return False, int(width), int(height)
    scaled = height > pheight or width > pwidth
    if height > pheight:
        corrf = pheight / float(height)
        width, height = floor(corrf * width), pheight
    if width > pwidth:
        corrf = pwidth / float(width)
        width, height = pwidth, floor(corrf * height)
    if height > pheight:
        corrf = pheight / float(height)
        width, height = floor(corrf * width), pheight
    return scaled, int(width), int(height)

class CurrentDir:
    def __init__(self, path):
        self.path = path
        self.cwd = None

    def __enter__(self, *args):
        self.cwd = os.getcwd()
        os.chdir(self.path)
        return self.cwd

    def __exit__(self, *args):
        try:
            os.chdir(self.cwd)
        except OSError:
            pass

_ncpus = None

def detect_ncpus():
    global _ncpus
    if _ncpus is None:
        _ncpus = max(1, os.cpu_count() or 1)
    return _ncpus

class CommandLineError(Exception):
    pass

def setup_cli_handlers(logger, level):
    import logging
    if os.environ.get('CALIBRE_WORKER') and logger.handlers:
        return
    logger.setLevel(level)
    if level == logging.WARNING:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        handler.setLevel(logging.WARNING)
    elif level == logging.INFO:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter())
        handler.setLevel(logging.INFO)
    elif level == logging.DEBUG:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(filename)s:%(lineno)s: %(message)s'))
    logger.addHandler(handler)

def human_readable(size, sep=' '):
    divisor, suffix = 1, 'B'
    for i, candidate in enumerate(('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB')):
        if size < (1 << ((i + 1) * 10)):
            divisor, suffix = (1 << (i * 10)), candidate
            break
    size = str(float(size) / divisor)
    if size.find('.') > -1:
        size = size[:size.find('.') + 2]
    size = size.removesuffix('.0')
    return size + sep + suffix

def extract(path, dir):
    """Extract archive (zip/rar/7z) to directory."""
    extractor = None
    with open(path, 'rb') as f:
        id_ = f.read(3)
    if id_.startswith(b'PK'):
        import zipfile
        def zipextract(p, d):
            with zipfile.ZipFile(p) as zf:
                zf.extractall(d)
        extractor = zipextract
    if extractor is None:
        ext = os.path.splitext(path)[1][1:].lower()
        if ext in ('zip', 'cbz', 'epub', 'oebzip'):
            import zipfile
            def zipextract2(p, d):
                with zipfile.ZipFile(p) as zf:
                    zf.extractall(d)
            extractor = zipextract2
    if extractor is None:
        raise Exception('Unknown archive type')
    extractor(path, dir)

def get_proxies(debug=True):
    from urllib.request import getproxies
    proxies = getproxies()
    for key, proxy in list(proxies.items()):
        if not proxy or '..' in proxy or key == 'auto':
            del proxies[key]
            continue
        if proxy.startswith(key + '://'):
            proxy = proxy[len(key) + 3:]
        if key == 'https' and proxy.startswith('http://'):
            proxy = proxy[7:]
        proxy = proxy.removesuffix('/')
        if len(proxy) > 4:
            proxies[key] = proxy
        else:
            del proxies[key]
    return proxies

def get_parsed_proxy(typ='http', debug=True):
    proxies = get_proxies(debug)
    proxy = proxies.get(typ, None)
    if proxy:
        pattern = re.compile(
            (r'(?:ptype://)?'
             r'(?:(?P<user>\w+):(?P<pass>.*)@)?'
             r'(?P<host>[\w\-\.]+)'
             r'(?::(?P<port>\d+))?').replace('ptype', typ)
        )
        match = pattern.match(proxies[typ])
        if match:
            try:
                ans = {
                    'host': match.group('host'),
                    'port': match.group('port'),
                    'user': match.group('user'),
                    'pass': match.group('pass'),
                }
                if ans['port']:
                    ans['port'] = int(ans['port'])
            except Exception:
                pass
            else:
                return ans

def get_proxy_info(proxy_scheme, proxy_string):
    from urllib.parse import urlparse
    try:
        proxy_url = f'{proxy_scheme}://{proxy_string}'
        urlinfo = urlparse(proxy_url)
        return {
            'scheme': urlinfo.scheme,
            'hostname': urlinfo.hostname,
            'port': urlinfo.port,
            'username': urlinfo.username,
            'password': urlinfo.password,
        }
    except Exception:
        return None

def random_user_agent(choose=None, allow_ie=True):
    return 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'

def browser(**kw):
    raise NotImplementedError('browser() not available in WASM')

def osx_version():
    return None

def load_library(name, cdll):
    raise NotImplementedError('load_library() not available in WASM')

def ipython(user_ns=None):
    raise NotImplementedError('ipython() not available in WASM')

def fsync(fileobj):
    fileobj.flush()

def is_mobile_ua(ua):
    return 'Mobile/' in ua or 'Mobile ' in ua
