import re, codecs

def substitute_entites(raw):
    """Replace HTML entities with unicode characters."""
    import html as _html
    try:
        return _html.unescape(raw)
    except Exception:
        return raw

def xml_to_unicode(raw, verbose=False, strip_encoding_pats=False, resolve_entities=False, assume_utf8=False):
    if isinstance(raw, str):
        return raw, 'utf-8'
    for bom, enc in [(codecs.BOM_UTF8, 'utf-8'), (codecs.BOM_UTF16_LE, 'utf-16-le'),
                     (codecs.BOM_UTF16_BE, 'utf-16-be')]:
        if raw.startswith(bom):
            return raw[len(bom):].decode(enc, 'replace'), enc
    enc = _detect_xml_enc(raw)
    try:
        return raw.decode(enc, 'replace'), enc
    except (UnicodeDecodeError, LookupError):
        return raw.decode('utf-8', 'replace'), 'utf-8'

def _detect_xml_enc(raw):
    if isinstance(raw, str):
        return 'utf-8'
    for bom, enc in [(codecs.BOM_UTF8, 'utf-8'), (codecs.BOM_UTF16_LE, 'utf-16-le'),
                     (codecs.BOM_UTF16_BE, 'utf-16-be')]:
        if raw.startswith(bom):
            return enc
    m = re.search(b'<\\?xml[^>]+encoding=["\'](.*?)["\'\\s]', raw[:1024])
    if m:
        try:
            codecs.lookup(m.group(1).decode('ascii'))
            return m.group(1).decode('ascii')
        except (LookupError, UnicodeDecodeError):
            pass
    return 'utf-8'

def detect_xml_encoding(raw, verbose=False, assume_utf8=True):
    """Returns (decoded_text, encoding) tuple."""
    if isinstance(raw, str):
        return (raw, 'utf-8')
    enc = _detect_xml_enc(raw)
    try:
        return (raw.decode(enc, 'replace'), enc)
    except (UnicodeDecodeError, LookupError):
        return (raw.decode('utf-8', 'replace'), 'utf-8')

def strip_encoding_declarations(raw, limit=50):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', 'replace')
    return re.sub(r'<\?xml[^>]+\?>', '', raw[:limit*80]) + raw[limit*80:]

def force_encoding(raw, verbose=False):
    return xml_to_unicode(raw, verbose)

def detect(raw):
    return {'encoding': 'utf-8', 'confidence': 0.5}
