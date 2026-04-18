"""
WASM-compatible html5_parser replacement.

Uses lxml.html for lxml tree output. When return_root=False, returns a
bs4.BeautifulSoup object (needed by calibre's BeautifulSoup wrapper).

The native html5-parser C extension (based on Gumbo) cannot run in WASM.
"""

from lxml import etree, html as lxml_html

XHTML_NS = 'http://www.w3.org/1999/xhtml'

def _decode(html, transport_encoding=None, fallback_encoding=None):
    if isinstance(html, bytes):

        if html[:3] == b'\xef\xbb\xbf':
            return html[3:].decode('utf-8', 'replace')
        if html[:2] in (b'\xff\xfe', b'\xfe\xff'):
            return html.decode('utf-16', 'replace')

        if html[:5] == b'<?xml':
            import re
            m = re.search(rb'encoding=["\']([^"\']+)', html[:200])
            if m:
                enc = m.group(1).decode('ascii', 'replace')
                try:
                    return html.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    pass

        encoding = transport_encoding or fallback_encoding or 'utf-8'
        try:
            return html.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            try:
                return html.decode('utf-8', 'replace')
            except Exception:
                return html.decode('latin-1', 'replace')
    return html

def _is_xhtml(html_str):
    """Detect if content is XHTML based on namespace or content type."""
    if 'xmlns="http://www.w3.org/1999/xhtml"' in html_str[:1000]:
        return True
    if 'application/xhtml+xml' in html_str[:500]:
        return True
    return False

def parse(html, treebuilder='lxml', namespaceHTMLElements=False,
          transport_encoding=None, fallback_encoding=None,
          maybe_xhtml=False, sanitize_names=False, return_root=True, **kwargs):
    """Parse HTML5 document.

    When return_root=True (default), returns an lxml element tree.
    When return_root=False, returns a bs4.BeautifulSoup object.
    """
    html = _decode(html, transport_encoding, fallback_encoding)

    if not return_root:
        import bs4
        return bs4.BeautifulSoup(html, 'html.parser')

    if maybe_xhtml or _is_xhtml(html):
        try:
            parser = etree.XMLParser(recover=True, no_network=True,
                                     resolve_entities=False)
            root = etree.fromstring(html.encode('utf-8'), parser=parser)
            if root is not None and root.tag is not None:

                tag = root.tag
                if isinstance(tag, str):
                    local = tag.split('}')[-1] if '}' in tag else tag
                    if local.lower() == 'html':
                        return root
        except Exception:
            pass

    try:
        root = lxml_html.document_fromstring(html)
    except Exception:

        try:
            parser = lxml_html.HTMLParser(recover=True)
            root = lxml_html.document_fromstring(html, parser=parser)
        except Exception:
            root = lxml_html.document_fromstring('<html><body></body></html>')

    return root
