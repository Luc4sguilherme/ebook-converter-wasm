"""
WASM-compatible replacement for calibre.utils.localization

Provides locale/language utilities without pkg_resources dependency.
"""
import json
import os

def get_lang():
    return 'en_US'

def is_rtl():
    return get_lang()[:2].lower() in {'he', 'ar'}

_RTL_LANGS = frozenset('ar he fa ur yi'.split())

def is_rtl_lang(lang):
    if lang:
        lang = lang.split('_')[0].split('-')[0].lower()
        return lang in _RTL_LANGS
    return False

lcdata = {'abday': ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'),
          'abmon': ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                    'Sep', 'Oct', 'Nov', 'Dec'),
          'd_fmt': '%m/%d/%Y',
          'd_t_fmt': '%a %d %b %Y %r %Z',
          'day': ('Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday',
                  'Friday', 'Saturday'),
          'mon': ('January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November',
                  'December'),
          'noexpr': '^[nN].*',
          'radixchar': '.',
          't_fmt': '%r',
          't_fmt_ampm': '%I:%M:%S %p',
          'thousep': ',',
          'yesexpr': '^[yY].*'}

_iso639 = None

def _load_iso639():
    global _iso639
    if _iso639 is None:

        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        src = os.path.join(data_dir, 'iso_639-3.json')

        if not os.path.exists(src):
            _iso639 = {'by_2': {}, 'by_3': {}, 'codes2': {}, 'codes3': {},
                        'by_name': {}}
            return _iso639

        with open(src, 'rb') as f:
            root = json.load(f)

        entries = root['639-3']
        by_2 = {}
        by_3 = {}
        codes2 = {}
        codes3 = {}
        by_name = {}

        for entry in entries:
            alpha3 = entry.get('alpha_3', '')
            alpha2 = entry.get('alpha_2', '')
            name = entry.get('name', '')
            inverted_name = entry.get('inverted_name', '')

            if alpha3:
                by_3[alpha3] = entry
                codes3[alpha3] = name
            if alpha2:
                by_2[alpha2] = entry
                codes2[alpha2] = name
            if name:
                by_name[name.lower()] = entry
            if inverted_name:
                by_name[inverted_name.lower()] = entry

        _iso639 = {
            'by_2': by_2,
            'by_3': by_3,
            'codes2': codes2,
            'codes3': codes3,
            'by_name': by_name,
        }
    return _iso639

def canonicalize_lang(raw):
    if not raw:
        return None
    raw = raw.strip().lower()
    if not raw:
        return None
    raw = raw.replace('-', '_')
    if '_' in raw:
        raw = raw.split('_')[0]
    if len(raw) == 2:
        data = _load_iso639()
        if raw in data['by_2']:
            return raw
    elif len(raw) == 3:
        data = _load_iso639()
        if raw in data['by_3']:
            entry = data['by_3'][raw]
            a2 = entry.get('alpha_2', '')
            return a2 if a2 else raw
    return raw if len(raw) <= 3 else None

def lang_as_iso639_1(raw):
    if not raw:
        return None
    raw = raw.strip().lower().replace('-', '_')
    if '_' in raw:
        raw = raw.split('_')[0]
    if len(raw) == 2:
        return raw
    if len(raw) == 3:
        data = _load_iso639()
        if raw in data['by_3']:
            return data['by_3'][raw].get('alpha_2', raw)
    return raw

def lang_as_iso639_3(raw):
    if not raw:
        return None
    raw = raw.strip().lower().replace('-', '_')
    if '_' in raw:
        raw = raw.split('_')[0]
    if len(raw) == 3:
        return raw
    if len(raw) == 2:
        data = _load_iso639()
        if raw in data['by_2']:
            return data['by_2'][raw].get('alpha_3', raw)
    return raw

def get_udc():
    """Return a Unihandecoder instance. Fallback to simple ASCII transliterator."""
    try:
        from calibre.ebooks.unihandecode import Unihandecoder
        return Unihandecoder(lang='en')
    except Exception:
        pass

    class _FallbackUDC:
        def decode(self, text):
            import unicodedata
            return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

    return _FallbackUDC()

_ = lambda x: x
__ = lambda x: x
ngettext = lambda s, p, n: s if n == 1 else p
pgettext = lambda c, m: m

def get_available_translations():
    return ['en']

def calibre_langcode_to_name(lc, localize=False):
    data = _load_iso639()
    if lc in data['codes2']:
        return data['codes2'][lc]
    if lc in data['codes3']:
        return data['codes3'][lc]
    return lc

langcode_to_name = calibre_langcode_to_name

def langnames_to_langcodes(names):
    data = _load_iso639()
    result = {}
    for name in names:
        key = name.lower()
        if key in data['by_name']:
            entry = data['by_name'][key]
            a2 = entry.get('alpha_2', '')
            a3 = entry.get('alpha_3', '')
            result[name] = {a2} if a2 else ({a3} if a3 else set())
        else:
            result[name] = set()
    return result

def localize_user_manual_link(url):
    """Return URL unchanged in WASM."""
    return url

_iso3166 = None

def load_iso3166():
    global _iso3166
    if _iso3166 is not None:
        return _iso3166
    codes = {}
    three_map = {}
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    src = os.path.join(data_dir, 'iso_3166-1.json')
    if os.path.exists(src):
        with open(src, 'rb') as f:
            root = json.load(f)
        for entry in root.get('3166-1', []):
            a2 = entry.get('alpha_2', '')
            a3 = entry.get('alpha_3', '')
            name = entry.get('name', '')
            if a2:
                codes[a2] = name
            if a3 and a2:
                three_map[a3] = a2
    _iso3166 = {'codes': codes, 'three_map': three_map}
    return _iso3166
