import re
import html.entities

def ascii_pat(for_binary=False):
    attr = 'binary' if for_binary else 'text'
    ans = getattr(ascii_pat, attr, None)
    if ans is None:
        chars = set(range(32)) - {9, 10, 13}
        chars.add(127)
        pat = '|'.join(map(chr, chars))
        if for_binary:
            pat = pat.encode('ascii')
        ans = re.compile(pat)
        setattr(ascii_pat, attr, ans)
    return ans

def clean_ascii_chars(txt, charlist=None):
    r'''
    Remove ASCII control chars.
    This is all control chars except \t, \n and \r
    '''
    is_binary = isinstance(txt, bytes)
    empty = b'' if is_binary else ''
    if not txt:
        return empty
    if charlist is None:
        pat = ascii_pat(is_binary)
    else:
        pat = '|'.join(map(chr, charlist))
        if is_binary:
            pat = pat.encode('utf-8')
        pat = re.compile(pat)
    return pat.sub(empty, txt)

def allowed(x):
    x = ord(x)
    return ((x != 127 and (31 < x < 0xd800 or x in (9, 10, 13))) or
            (0xdfff < x < 0xfffe) or (0xffff < x <= 0x10ffff))

def clean_xml_chars(unicode_string):
    """Remove characters that are not allowed in XML."""
    if not unicode_string:
        return unicode_string
    return ''.join(filter(allowed, unicode_string))

def unescape(text, rm=False, rchar=''):
    """Remove HTML or XML character references and entities from a text string."""
    def fixup(m, rm=rm, rchar=rchar):
        text = m.group(0)
        if text[:2] == "&#":
            try:
                if text[:3] == "&#x":
                    return chr(int(text[3:-1], 16))
                else:
                    return chr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            try:
                text = chr(html.entities.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        if rm:
            return rchar
        return text
    return re.sub(r"&#?\w+;", fixup, text)
