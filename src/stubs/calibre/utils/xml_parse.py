from lxml import etree
from lxml.html import (
    document_fromstring as _doc_fromstring,
    fragment_fromstring as _frag_fromstring,
)

def safe_xml_fromstring(raw, recover=True):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    parser = etree.XMLParser(recover=recover, no_network=True, resolve_entities=False)
    return etree.fromstring(raw, parser=parser)

def safe_html_fromstring(raw, recover=True):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    parser = etree.HTMLParser(recover=recover, no_network=True)
    return etree.fromstring(raw, parser=parser)

def document_fromstring(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return _doc_fromstring(raw)

def fragment_fromstring(raw, create_parent=False):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return _frag_fromstring(raw, create_parent=create_parent)

def find_tests():
    pass
