"""
Pure Python replacement for calibre's uchardet extension.

detect(raw) returns the name of the detected encoding (or '' when nothing
could be detected), like the C extension. uchardet is a C++ port of the
Mozilla universal charset detector, the chardet package is a Python port of
the same detector, so it is used when the data is not valid UTF-8.
"""

import codecs

# chardet reports latin-1 for most western text, but real world documents
# labelled or detected as latin-1 are almost always windows-1252 (curly
# quotes, dashes, etc.), which is a superset. This is also what uchardet and
# the WHATWG encoding standard do.
_ALIASES = {
    'iso-8859-1': 'windows-1252',
    'ascii': 'ascii',
}


def _is_utf8(raw):
    dec = codecs.getincrementaldecoder('utf-8')('strict')
    try:
        # final=False so that a multi-byte sequence truncated at the end of
        # the sample does not cause a failure
        dec.decode(raw, final=False)
    except UnicodeDecodeError:
        return False
    return True


def detect(raw):
    if isinstance(raw, str):
        raw = raw.encode('utf-8', 'replace')
    if not raw:
        return ''
    if raw.isascii():
        return 'ascii'
    if _is_utf8(raw):
        return 'utf-8'
    enc = ''
    try:
        import chardet
        enc = chardet.detect(raw).get('encoding') or ''
    except Exception:
        try:
            import charset_normalizer
            best = charset_normalizer.from_bytes(raw).best()
            enc = best.encoding if best is not None else ''
        except Exception:
            enc = ''
    enc = enc.lower().replace('_', '-')
    if not enc:
        return 'windows-1252'
    return _ALIASES.get(enc, enc)
