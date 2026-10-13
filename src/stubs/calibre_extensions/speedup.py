"""
Pure Python port of calibre's speedup C extension (src/calibre/utils/speedup.c).
"""
import copy as _copy
import math
import os
import re
from datetime import datetime

O_CLOEXEC = getattr(os, 'O_CLOEXEC', 0)


def pread_all(fd, size, offset):
    """Read size bytes from file descriptor fd at given offset."""
    if hasattr(os, 'pread'):
        chunks = []
        while size > 0:
            chunk = os.pread(fd, size, offset)
            if not chunk:
                break
            chunks.append(chunk)
            size -= len(chunk)
            offset += len(chunk)
        return b''.join(chunks)
    os.lseek(fd, offset, os.SEEK_SET)
    data = b''
    while len(data) < size:
        chunk = os.read(fd, size - len(data))
        if not chunk:
            break
        data += chunk
    return data


def pdf_float(f):
    """Convert a float to a string representation suitable for PDF."""
    f = float(f)
    a = abs(f)
    if a <= 1.0e-7:
        return '0'
    precision = 6
    if a > 1:
        precision = min(max(0, 6 - int(math.log10(a))), 6)
    buf = f'{f:.{precision}f}'
    if precision > 0:
        buf = buf.rstrip('0')
        if buf.endswith('.'):
            buf = buf[:-1]
    return buf


def barename(name):
    """Strip namespace from an XML tag name."""
    return name.rpartition('}')[-1]


def namespace(name):
    """Extract namespace from an XML tag name."""
    if name and name[0] == '{':
        return name[1:].partition('}')[0]
    return ''


_ignored_tags = frozenset(('script', 'style', 'noscript', 'title'))
_weighted_tags = {'svg': 1000, 'img': 1000, 'video': 2000}


def _count_chars_in(text):
    if not text:
        return 0
    return len(text) - sum(1 for ch in text if ch <= ' ')


def get_num_of_significant_chars(elem):
    """Count the characters in the text and tail of elem that are not whitespace or control chars."""
    tag = getattr(elem, 'tag', None)
    ans = 0
    ignored = False
    text = None
    if isinstance(tag, str):
        name = tag.rpartition('}')[-1].lower()
        if name in _ignored_tags:
            ignored = True
        else:
            ans += _weighted_tags.get(name, 0)
        text = getattr(elem, 'text', None)
    tail = getattr(elem, 'tail', None)
    if isinstance(tail, str):
        ans += _count_chars_in(tail)
    if not ignored and isinstance(text, str):
        ans += _count_chars_in(text)
    return ans


_bad_xml_chars = re.compile(
    '[^\u0009\u000a\u000d -~\u0085 -퟿-﷏ﷰ-�\U00010000-\U0010ffff]')


def clean_xml_chars(unicode_string):
    """Remove characters that are not allowed in XML."""
    if not isinstance(unicode_string, str):
        raise TypeError('A unicode string is required')
    if not unicode_string:
        return unicode_string
    return _bad_xml_chars.sub('', unicode_string)


def parse_iso8601(date_string):
    '''
    Returns (naive datetime, is_aware, utc offset in seconds). Port of the
    hand written parser in speedup.c
    '''
    s = date_string
    n = len(s)
    pos = 0

    def fail(msg):
        raise ValueError(f'{date_string} is not a valid ISO 8601 datestring: {msg}')

    def read_number(max_digits):
        nonlocal pos
        val = 0
        count = 0
        while count < max_digits and pos < n and '0' <= s[pos] <= '9':
            val = val * 10 + ord(s[pos]) - 48
            pos += 1
            count += 1
        return val, count

    def optional(ch):
        nonlocal pos
        if pos < n and s[pos] == ch:
            pos += 1

    while pos < n and s[pos] in ' \n\r\t\v\f':
        pos += 1
    year, c = read_number(4)
    if c < 4:
        fail('No year specified')
    optional('-')
    month, c = read_number(2)
    day = hour = minute = second = usecond = 0
    if month == 0:
        month = 1
    else:
        optional('-')
        day, c = read_number(2)
    if day == 0:
        day = 1
    if month > 12:
        fail('month greater than 12')
    if pos < n and s[pos] in 'T ':
        pos += 1
        hour, c = read_number(2)
        if c < 2:
            fail('No hour specified')
        optional(':')
        minute, c = read_number(2)
        optional(':')
        second, c = read_number(2)
        if pos < n and s[pos] in '.,':
            pos += 1
            usecond, c = read_number(6)
            while pos < n and '0' <= s[pos] <= '9':
                pos += 1
            usecond *= 10 ** (6 - c)
    tzsign = 0
    tzhour = 1000
    tzminute = 0
    if pos < n:
        ch = s[pos]
        if ch == 'Z':
            tzhour = 0
            pos += 1
        elif ch == '+':
            tzsign = 1
            pos += 1
        elif ch == '-':
            tzsign = -1
            pos += 1
    if tzsign != 0:
        tzhour, c = read_number(2)
        optional(':')
        tzminute, c = read_number(2)
    dt = datetime(year, month, day, hour, minute, second, usecond)
    return dt, tzhour != 1000, tzsign * 60 * (tzhour * 60 + tzminute)


def parse_date(raw):
    '''
    Parse dates of the form YYYY-MM-DD HH:MM:SS+HH:MM as stored by calibre.
    Returns (year, month, day, hour, minute, second, tz_seconds) or None.
    '''
    raw = raw.lstrip(' \t\n\r\f\v')
    if len(raw) < 19:
        return None
    m = re.match(r'(\d{4}).(\d{2}).(\d{2}).(\d{2}).(\d{2}).(\d{2})', raw)
    if m is None:
        return None
    year, month, day, hour, minute, second = map(int, m.groups())
    tz = raw[-6:]
    sign = 0
    if tz[0] == '+':
        sign = 1
    elif tz[0] == '-':
        sign = -1
    tzsecs = 0
    if sign:
        try:
            tzsecs = sign * (int(tz[1:3]) * 3600 + int(tz[4:6]) * 60)
        except ValueError:
            return None
    return year, month, day, hour, minute, second, tzsecs


def websocket_mask(data, mask, offset=0):
    mask = bytes(mask)
    return bytes(b ^ mask[(i + offset) & 3] for i, b in enumerate(data))


def deepcopy(obj, memo=None):
    return _copy.deepcopy(obj, memo)


def detach(devnull):
    pass


def set_thread_name(name):
    pass


def create_texture(*args, **kwargs):
    raise NotImplementedError('create_texture is not available in WASM')
