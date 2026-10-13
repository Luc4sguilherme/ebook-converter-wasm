"""
WASM-compatible replacement for calibre.utils.icu

Provides pure Python fallbacks for ICU text operations.
No native ICU library needed.
"""
import re
import sys
import unicodedata

_locale = 'en'

_digit_run = re.compile(r'\d+')


def _char_class(ch, cat):
    # Ordering of character classes in the ICU root collation
    if cat[0] == 'Z' or ch in '\t\n\r\x0b\x0c':
        return 0
    if cat[0] == 'P':
        return 1
    if cat[0] == 'S':
        return 2
    if cat[0] == 'N':
        return 3
    return 4


def _icu_key(text, strength=2, numeric=False, upper_first=False):
    '''
    Approximation of an ICU root collation sort key. The key has up to three
    levels: base characters (punctuation < symbols < digits < letters,
    ignoring case and accents), then accents, then case.
    '''
    if text is None:
        return ()
    if isinstance(text, bytes):
        text = text.decode('utf-8', 'replace')
    nfd = unicodedata.normalize('NFD', text)
    primary, secondary, tertiary = [], [], []
    pos, n = 0, len(nfd)
    while pos < n:
        ch = nfd[pos]
        if numeric and '0' <= ch <= '9':
            m = _digit_run.match(nfd, pos)
            primary.append((3, int(m.group())))
            secondary.append(0)
            tertiary.append(0)
            pos = m.end()
            continue
        pos += 1
        if unicodedata.combining(ch):
            if secondary:
                secondary[-1] = secondary[-1] * 0x10000 + ord(ch)
            continue
        cat = unicodedata.category(ch)
        folded = ch.casefold()
        primary.append((_char_class(ch, cat), folded))
        secondary.append(0)
        if folded != ch:
            tertiary.append(0 if upper_first else 1)
        else:
            tertiary.append(1 if upper_first else 0)
    key = (tuple(primary),)
    if strength >= 2:
        key += (tuple(secondary),)
    if strength >= 3:
        key += (tuple(tertiary),)
    return key


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
        strength = {'primary': 1, 'secondary': 2}.get(self.strength, 3)
        return _icu_key(text, strength, self.numeric, self.upper_first)

    def strcmp(self, a, b):
        ka = self.sort_key(a or '')
        kb = self.sort_key(b or '')
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
    return _icu_key(obj, 2)

def numeric_sort_key(obj):
    return _icu_key(obj, 2, numeric=True)

def primary_sort_key(obj):
    return _icu_key(obj, 1)

def case_sensitive_sort_key(obj):
    return _icu_key(obj, 3, upper_first=True)

def collation_order(text):
    if not text:
        return 0, 0
    return ord(text[0].upper()), 1

def strcmp(a, b):
    ka = sort_key(a or '')
    kb = sort_key(b or '')
    if ka < kb:
        return -1
    if ka > kb:
        return 1
    return 0

def case_sensitive_strcmp(a, b):
    ka = case_sensitive_sort_key(a or '')
    kb = case_sensitive_sort_key(b or '')
    if ka < kb:
        return -1
    if ka > kb:
        return 1
    return 0

def primary_strcmp(a, b):
    ka = primary_sort_key(a or '')
    kb = primary_sort_key(b or '')
    return (ka > kb) - (ka < kb)

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


def utf16_length(text):
    return len(text.encode('utf-16-le')) // 2


# Text segmentation {{{
# Replacement for the BreakIterator of the ICU C extension, following the
# word and sentence boundary rules of Unicode UAX #29, which is what ICU
# implements (minus the dictionary based segmentation of CJK text).

_STERM = '!?\u037e\u0589\u061f\u06d4\u0700-\u0702\u07f9\u0964\u0965\u104a\u104b\u1362\u1367\u1368\u166e\u1803\u1809\u1944\u1945\u203c\u203d\u2047-\u2049\u2e2e\u3002\ua4ff\ua60e\ua60f\ua876\ua877\ufe56\ufe57\uff01\uff1f\uff61'
_ATERM = '.\u2024\ufe52\uff0e'
_CLOSE = '"\'\u2019\u201d\u00bb\u203a)\\]}\u300d\u300f\u3011\uff09'
_PARASEP = '\n\r\u0085\u2028\u2029'
_sentence_end = re.compile(
    f'[{_STERM}{_ATERM}]+[{_CLOSE}]*[ \t\u00a0\u2000-\u200b\u3000]*[{_PARASEP}]?'
    f'|[{_PARASEP}]')
_word = re.compile(r"\w+(?:[\u0027\u2019.:\u00b7\u2027\uff1a]\w+)*")
_cjk = re.compile('[\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\U00020000-\U0002fa1f]')


def _sentence_boundaries(text):
    ''' Yield the positions at which a new sentence starts '''
    n = len(text)
    for m in _sentence_end.finditer(text):
        end = m.end()
        if end >= n:
            break
        token = m.group()
        if token[0] in _PARASEP:
            yield end
            continue
        if token[0] in _ATERM and not any(c in _STERM for c in token):
            start = m.start()
            nxt = text[end]
            # 3.14, e.g. the, U.S.A.
            if end == start + 1 and (nxt.isdigit() or nxt.islower()):
                continue
            if end == start + 1 and start > 0 and text[start - 1].isalpha() and nxt.isupper():
                continue
            # SB8: no break if the next word starts with a lower case letter
            rest = text[end:end + 64]
            for ch in rest:
                if ch.isalpha():
                    if ch.islower():
                        break
                    yield end
                    break
                if ch in _PARASEP or ch in _STERM or ch in _ATERM:
                    yield end
                    break
            else:
                yield end
            continue
        yield end


class _BreakIterator:

    def __init__(self, break_type, locale='', extra_break_chars=None):
        self.break_type = break_type
        self.locale = locale
        self.extra_break_chars = extra_break_chars or ''
        self.text = ''

    def set_text(self, text):
        self.text = text or ''

    def _words(self):
        text = self.text
        extra = self.extra_break_chars
        for m in _word.finditer(text):
            start, word = m.start(), m.group()
            pieces = [(start, word)]
            if extra:
                pieces = []
                pos = start
                for part in re.split('([' + re.escape(extra) + '])', word):
                    if part and part not in extra:
                        pieces.append((pos, part))
                    pos += len(part)
            for pos, piece in pieces:
                if _cjk.search(piece) is None:
                    yield pos, len(piece)
                    continue
                # Ideographs and syllables form words on their own
                run = 0
                for i, ch in enumerate(piece):
                    if _cjk.match(ch):
                        if run:
                            yield pos + i - run, run
                            run = 0
                        yield pos + i, 1
                    else:
                        run += 1
                if run:
                    yield pos + len(piece) - run, run

    def _sentences(self):
        text = self.text
        if not text:
            return
        prev = 0
        for b in _sentence_boundaries(text):
            if b > prev:
                yield prev, b - prev
                prev = b
        if prev < len(text):
            yield prev, len(text) - prev

    def split2(self):
        if self.break_type == _icu.UBRK_SENTENCE:
            return list(self._sentences())
        return list(self._words())

    def split(self):
        return [self.text[p:p+s] for p, s in self.split2()]

    def count_words(self):
        return len(self.split2())

    def index(self, needle):
        text = self.text
        if not needle:
            return -1
        for p, s in self._words():
            if text.startswith(needle, p):
                end = p + len(needle)
                if end == len(text) or not (text[end].isalnum() or text[end] == '_'):
                    return p
        return -1


class _ICU:
    UBRK_CHARACTER, UBRK_WORD, UBRK_LINE, UBRK_SENTENCE = range(4)
    BreakIterator = _BreakIterator


_icu = _ICU()
# }}}

icu_version = '15.0'
