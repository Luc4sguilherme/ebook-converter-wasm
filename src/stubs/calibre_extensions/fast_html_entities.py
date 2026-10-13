"""
Pure Python port of calibre's fast_html_entities C extension
(src/calibre/ebooks/html_entities.c).

replace_all_entities(raw, keep_xml_entities=False) replaces every named or
numeric entity in raw. When keep_xml_entities is True, entities that resolve
to one of the five XML special characters (& < > " ') are left untouched so
that the result is still well formed markup.
"""

import re

_entity_body = re.compile(r'#?[A-Za-z0-9]*')
_html5_entities = None


def _entities():
    global _html5_entities
    if _html5_entities is None:
        from calibre.ebooks.html_entities import html5_entities
        _html5_entities = html5_entities
    return _html5_entities


_XML_UNSAFE = frozenset('<>&"\'')


def _convert(name, keep_xml_entities):
    # Returns the replacement text or None if the entity must be kept as is
    if name[0] == '#':
        if len(name) < 2:
            return None
        try:
            if name[1] in 'xX':
                if len(name) < 3:
                    return None
                codepoint = int(name[2:], 16)
            else:
                if not name[1:].isdigit():
                    return None
                codepoint = int(name[1:])
        except ValueError:
            return None
        codepoint &= 0xffffffff
        if keep_xml_entities and codepoint < 128 and chr(codepoint) in _XML_UNSAFE:
            return None
        if codepoint == 0 or codepoint >= 0x110000 or 0xd800 <= codepoint <= 0xdfff:
            return ''
        return chr(codepoint)
    val = _entities().get(name)
    if val is None:
        return None
    if keep_xml_entities and val in _XML_UNSAFE:
        return None
    return val


def _replace(raw, keep_xml_entities):
    if '&' not in raw:
        return raw
    out = []
    pos = 0
    n = len(raw)
    find = raw.find
    match = _entity_body.match
    while pos < n:
        amp = find('&', pos)
        if amp < 0:
            out.append(raw[pos:])
            break
        out.append(raw[pos:amp])
        end = match(raw, amp + 1).end()
        if end < n and raw[end] == ';':
            entity = raw[amp:end + 1]
            elen = len(entity.encode('utf-8')) if not entity.isascii() else len(entity)
            rep = None
            if 3 <= elen <= 64:
                rep = _convert(entity[1:-1], keep_xml_entities)
            out.append(entity if rep is None else rep)
            pos = end + 1
        else:
            # Copy the & the entity characters and the character that
            # terminated the entity (if any) verbatim
            stop = min(end + 1, n)
            out.append(raw[amp:stop])
            pos = stop
    ans = ''.join(out)
    # The C implementation returns the input unchanged if the output is empty
    return ans or raw


def replace_all_entities(raw, keep_xml_entities=False):
    if isinstance(raw, bytes):
        return _replace(raw.decode('utf-8'), bool(keep_xml_entities)).encode('utf-8')
    if not isinstance(raw, str):
        raise TypeError('string must be unicode object or UTF-8 encoded bytes')
    return _replace(raw, bool(keep_xml_entities))
