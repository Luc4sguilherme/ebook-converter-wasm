"""
WASM-compatible replacement for calibre.utils.icu

Provides pure Python fallbacks for ICU text operations.
No native ICU library needed.
"""
import re
import sys
import unicodedata

_locale = 'en'

def collator():
    return _PythonCollator()

def primary_collator():
    return _PythonCollator(strength='primary')

def sort_collator():
    return _PythonCollator(strength='secondary')

def numeric_collator():
    return _PythonCollator(strength='secondary', numeric=True)

def case_sensitive_collator():
    return _PythonCollator(upper_first=True)

class _PythonCollator:
    """Pure Python collator that mimics ICU behavior."""

    def __init__(self, strength='secondary', numeric=False, upper_first=False):
        self.strength = strength
        self.numeric = numeric
        self.upper_first = upper_first

    def sort_key(self, text):
        if text is None:
            return ''
        if isinstance(text, bytes):
            text = text.decode('utf-8', 'replace')

        key = unicodedata.normalize('NFD', text).casefold()
        if self.numeric:

            parts = re.split(r'(\d+)', key)
            return [int(p) if p.isdigit() else p for p in parts]
        return key

    def strcmp(self, a, b):
        ka = self.sort_key(a) if a else ''
        kb = self.sort_key(b) if b else ''
        if ka < kb:
            return -1
        if ka > kb:
            return 1
        return 0

    def find(self, haystack, needle):
        if not haystack or not needle:
            return -1, 0
        h = haystack.casefold()
        n = needle.casefold()
        idx = h.find(n)
        if idx == -1:
            return -1, 0
        return idx, len(needle)

    def contains(self, haystack, needle):
        if not haystack or not needle:
            return False
        return needle.casefold() in haystack.casefold()

    def startswith(self, text, prefix):
        if not text or not prefix:
            return False
        return text.casefold().startswith(prefix.casefold())

    def collation_order(self, text):
        if not text:
            return 0, 0
        return ord(text[0].upper()), 1

    def clone(self):
        return _PythonCollator(self.strength, self.numeric, self.upper_first)

def sort_key(obj):
    if obj is None:
        return ''
    if isinstance(obj, bytes):
        try:
            obj = obj.decode(sys.getdefaultencoding())
        except ValueError:
            return obj
    return unicodedata.normalize('NFD', obj).casefold()

def numeric_sort_key(obj):
    if obj is None:
        return ''
    if isinstance(obj, bytes):
        try:
            obj = obj.decode(sys.getdefaultencoding())
        except ValueError:
            return obj
    key = unicodedata.normalize('NFD', obj).casefold()
    parts = re.split(r'(\d+)', key)
    return tuple(int(p) if p.isdigit() else p for p in parts)

def primary_sort_key(obj):
    return sort_key(obj)

def case_sensitive_sort_key(obj):
    if obj is None:
        return ''
    if isinstance(obj, bytes):
        try:
            obj = obj.decode(sys.getdefaultencoding())
        except ValueError:
            return obj
    return unicodedata.normalize('NFD', obj)

def collation_order(text):
    if not text:
        return 0, 0
    return ord(text[0].upper()), 1

def strcmp(a, b):
    ka = sort_key(a) if a else ''
    kb = sort_key(b) if b else ''
    if ka < kb:
        return -1
    if ka > kb:
        return 1
    return 0

def case_sensitive_strcmp(a, b):
    ka = case_sensitive_sort_key(a) if a else ''
    kb = case_sensitive_sort_key(b) if b else ''
    if ka < kb:
        return -1
    if ka > kb:
        return 1
    return 0

def primary_strcmp(a, b):
    return strcmp(a, b)

def upper(x):
    if isinstance(x, bytes):
        x = x.decode('utf-8', 'replace')
    return x.upper() if x else x

def lower(x):
    if isinstance(x, bytes):
        x = x.decode('utf-8', 'replace')
    return x.lower() if x else x

def title_case(x):
    if isinstance(x, bytes):
        x = x.decode('utf-8', 'replace')
    return x.title() if x else x

def capitalize(x):
    try:
        return upper(x[0]) + lower(x[1:])
    except (IndexError, TypeError, AttributeError):
        return x

def swapcase(x):
    return x.swapcase() if x else x

def find(haystack, needle):
    if not haystack or not needle:
        return -1, 0
    h = haystack.casefold()
    n = needle.casefold()
    idx = h.find(n)
    if idx == -1:
        return -1, 0
    return idx, len(needle)

def primary_find(haystack, needle):
    return find(haystack, needle)

def contains(haystack, needle):
    if not haystack or not needle:
        return False
    return needle.casefold() in haystack.casefold()

def primary_contains(haystack, needle):
    return contains(haystack, needle)

def startswith(text, prefix):
    if not text or not prefix:
        return False
    return text.casefold().startswith(prefix.casefold())

def primary_startswith(text, prefix):
    return startswith(text, prefix)

safe_chr = chr
ord_string = str

def character_name(string):
    try:
        return unicodedata.name(string[0]) if string else None
    except (TypeError, ValueError):
        return None

def character_name_from_code(code):
    try:
        return unicodedata.name(chr(code))
    except (TypeError, ValueError):
        return ''

def normalize(text, mode='NFC'):
    return unicodedata.normalize(mode, str(text))

def contractions(col=None):
    return frozenset()

def partition_by_first_letter(items, reverse=False, key=lambda x: x):
    from collections import OrderedDict
    items = sorted(items, key=lambda x: sort_key(key(x)), reverse=reverse)
    ans = OrderedDict()
    last_c = ' '
    for item in items:
        c = (key(item) or ' ')[0].upper()
        if c != last_c:
            last_c = c
        try:
            ans[last_c].append(item)
        except KeyError:
            ans[last_c] = [item]
    return ans

string_length = len
utf16_length = len

icu_version = '15.0'
