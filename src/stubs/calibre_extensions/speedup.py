"""Stub for calibre_extensions.speedup"""
import os
import re

def pread_all(fd, size, offset):
    """Read size bytes from file descriptor fd at given offset."""
    os.lseek(fd, offset, os.SEEK_SET)
    data = b''
    while len(data) < size:
        chunk = os.read(fd, size - len(data))
        if not chunk:
            break
        data += chunk
    return data

def pdf_float(x):
    """Format a float for PDF output."""
    s = f'{x:.4f}'

    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s

_barename_re = re.compile(r'\{[^}]*\}(.*)')

def barename(name):
    """Strip namespace from an XML tag name."""
    m = _barename_re.match(name)
    return m.group(1) if m else name

_namespace_re = re.compile(r'\{([^}]*)\}')

def namespace(name):
    """Extract namespace from an XML tag name."""
    m = _namespace_re.match(name)
    return m.group(1) if m else ''

def get_num_of_significant_chars(text):
    """Return the number of significant (non-whitespace) characters."""
    return len(text) - text.count(' ') - text.count('\t') - text.count('\n') - text.count('\r')

def _allowed(x):
    x = ord(x)
    return ((x != 127 and (31 < x < 0xd800 or x in (9, 10, 13))) or
            (0xdfff < x < 0xfffe) or (0xffff < x <= 0x10ffff))

def clean_xml_chars(unicode_string):
    """Remove characters that are not allowed in XML."""
    if not unicode_string:
        return unicode_string
    return ''.join(filter(_allowed, unicode_string))
