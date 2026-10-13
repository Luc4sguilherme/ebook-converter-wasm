"""
WASM-compatible replacement for calibre.utils.localization

Provides locale/language utilities without pkg_resources dependency.
"""
import json
import os

def get_lang():
    return os.environ.get('CALIBRE_OVERRIDE_LANG') or 'en'

def is_rtl():
    return get_lang()[:2].lower() in {'he', 'ar'}

def is_rtl_lang(lang):
    lang = canonicalize_lang(lang)
    # Aramaic, Arabic, Azeri, Hebrew, Dhivehi, Sorani, Urdu, Farsi
    return lang and lang in ('ara', 'heb', 'aze', 'div', 'arc', 'syc', 'myz', 'ckb', 'urd', 'fas')

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
_extra_lang_codes = {
        'pt_BR': 'Brazilian Portuguese',
        'zh_CN': 'Simplified Chinese',
        'zh_TW': 'Traditional Chinese',
        'bn_IN': 'Indian Bengali',
        'bn_BD': 'Bangladeshi Bengali',
        'en'   : 'English',
        'und'  : 'Unknown'
        }
_lcase_map = {k.lower(): k for k in _extra_lang_codes}

def _load_iso639():
    # Generated at build time by scripts/generate-iso639.py from the iso-codes
    # project, with the same algorithm calibre uses to create
    # localization/iso639.calibre_msgpack
    global _iso639
    if _iso639 is None:
        from calibre.utils.resources import get_path as P
        try:
            _iso639 = json.loads(P('localization/iso639.json', allow_user_override=False, data=True))
        except ValueError:
            _iso639 = {}
        for k in ('by_2', 'by_3', '2to3', '3to2', 'name_map'):
            _iso639.setdefault(k, {})
        _iso639['codes2'] = frozenset(_iso639['by_2'])
        _iso639['codes3'] = frozenset(_iso639['by_3'])
    return _iso639

def get_iso_language(lang_trans, lang):
    iso639 = _load_iso639()
    ans = lang
    lang = lang.split('_')[0].lower()
    if len(lang) == 2:
        ans = iso639['by_2'].get(lang, ans)
    elif len(lang) == 3:
        if lang in iso639['by_3']:
            ans = iso639['by_3'][lang]
    return lang_trans(ans)

def get_language(lang, gettext_func=None):
    translate = gettext_func or _
    lang = _lcase_map.get(lang, lang)
    if lang in _extra_lang_codes:
        return translate(_extra_lang_codes[lang])
    return get_iso_language(translate, lang)

def canonicalize_lang(raw):
    if not raw:
        return None
    if not isinstance(raw, str):
        raw = raw.decode('utf-8', 'ignore')
    raw = raw.lower().strip()
    if not raw:
        return None
    raw = raw.replace('_', '-').partition('-')[0].strip()
    if not raw:
        return None
    iso639 = _load_iso639()
    m2to3 = iso639['2to3']

    if len(raw) == 2:
        ans = m2to3.get(raw, None)
        if ans is not None:
            return ans
    elif len(raw) == 3:
        if raw in iso639['by_3']:
            return raw

    return iso639['name_map'].get(raw, None)

_lang_map = None

def lang_map():
    ' Return mapping of ISO 639 3 letter codes to language names '
    global _lang_map
    if _lang_map is None:
        _lang_map = dict(_load_iso639()['by_3'])
    return _lang_map

def lang_as_iso639_1(name_or_code):
    code = canonicalize_lang(name_or_code)
    if code is not None:
        iso639 = _load_iso639()
        return iso639['3to2'].get(code, None)

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

def calibre_langcode_to_name(lc, localize=True):
    iso639 = _load_iso639()
    try:
        return iso639['by_3'][lc]
    except Exception:
        pass
    return lc

langcode_to_name = calibre_langcode_to_name

def ui_language_as_english():
    return calibre_langcode_to_name(canonicalize_lang(get_lang()) or 'eng', localize=False) or 'English'

def langnames_to_langcodes(names):
    '''
    Given a list of language names return a mapping of the names to 3
    letter ISO 639 language codes. If a name is not recognized, it is mapped to
    None.
    '''
    iso639 = _load_iso639()
    ans = {}
    names = set(names)
    for k, v in iso639['by_3'].items():
        if v in names:
            names.remove(v)
            ans[v] = k
        if not names:
            break
    for x in names:
        ans[x] = None
    return ans

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
