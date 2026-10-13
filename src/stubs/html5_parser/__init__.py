"""
WASM-compatible replacement for the html5-parser C extension.

The real html5-parser (https://github.com/kovidgoyal/html5-parser) runs the
Gumbo HTML 5 parser and builds the lxml tree directly with libxml2, which
cannot be done from Pyodide. This module implements the same API on top of
html5lib, which implements the same WHATWG parsing algorithm in pure Python.

html5lib builds a plain xml.etree tree, which is then copied into lxml with
the namespace layout html5-parser produces: HTML elements in the XHTML
namespace declared as the default namespace on the root (when
namespace_elements or maybe_xhtml is set), and SVG/MathML subtrees with
their own default namespace declaration.
"""

import re
import warnings
import xml.etree.ElementTree as ET

from lxml import etree

__version__ = (0, 4, 12)
version = __version__

XHTML_NS = 'http://www.w3.org/1999/xhtml'
SVG_NS = 'http://www.w3.org/2000/svg'
MATHML_NS = 'http://www.w3.org/1998/Math/MathML'
XLINK_NS = 'http://www.w3.org/1999/xlink'
XML_NS = 'http://www.w3.org/XML/1998/namespace'
XMLNS_NS = 'http://www.w3.org/2000/xmlns/'

# Prefixes that are understood even when the document does not declare them
WELL_KNOWN_PREFIXES = {
    'xml': XML_NS,
    'xlink': XLINK_NS,
    'epub': 'http://www.idpf.org/2007/ops',
}

VOID_ELEMENTS = frozenset((
    'area', 'base', 'basefont', 'bgsound', 'br', 'col', 'command', 'embed',
    'event-source', 'frame', 'hr', 'image', 'img', 'input', 'keygen', 'link',
    'meta', 'param', 'source', 'track', 'wbr',
))

_name_start = (
    'A-Z_a-z\xc0-\xd6\xd8-\xf6\xf8-˿Ͱ-ͽͿ-῿'
    '‌-‍⁰-↏Ⰰ-⿯、-퟿豈-﷏'
    'ﷰ-�\U00010000-\U000effff')
_name_char = _name_start + r'\-.0-9\xb7̀-ͯ‿-⁀'
_valid_name = re.compile(f'[{_name_start}][{_name_char}]*$')
_invalid_name_char = re.compile(f'[^{_name_char}]')
_invalid_xml_chars = re.compile(
    '[^\u0009\u000a\u000d -퟿-�\U00010000-\U0010ffff]')


def sanitize_name(name):
    if _valid_name.match(name) is not None:
        return name
    name = _invalid_name_char.sub('_', name)
    if not name or _valid_name.match(name) is None:
        name = '_' + name
    return name


def _clean_text(text):
    if text and _invalid_xml_chars.search(text) is not None:
        text = _invalid_xml_chars.sub('', text)
    return text


def _clean_comment(text):
    text = _clean_text(text or '')
    while '--' in text:
        text = text.replace('--', '- -')
    if text.endswith('-'):
        text += ' '
    return text


def _split(tag):
    if tag[0] == '{':
        ns, _, local = tag[1:].partition('}')
        return ns, local
    return None, tag


def _decode(raw, transport_encoding=None, fallback_encoding=None):
    if not isinstance(raw, bytes):
        return raw
    from html5lib._inputstream import HTMLBinaryInputStream
    kw = {}
    if transport_encoding:
        kw['override_encoding'] = transport_encoding
    if fallback_encoding:
        kw['default_encoding'] = fallback_encoding
    try:
        stream = HTMLBinaryInputStream(raw, **kw)
        enc = stream.charEncoding[0].name
    except Exception:
        enc = fallback_encoding or 'utf-8'
    try:
        return raw.decode(enc, 'replace')
    except LookupError:
        return raw.decode('utf-8', 'replace')


_parser_classes = {}


def _parser_class(maybe_xhtml):
    ans = _parser_classes.get(maybe_xhtml)
    if ans is not None:
        return ans
    import html5lib
    from html5lib import constants
    from html5lib._tokenizer import HTMLTokenizer

    start_tag = constants.tokenTypes['StartTag']
    end_tag = constants.tokenTypes['EndTag']

    class Tokenizer(HTMLTokenizer):

        def __iter__(self):
            for token in HTMLTokenizer.__iter__(self):
                if (token['type'] == start_tag and token.get('selfClosing')
                        and token['name'] not in VOID_ELEMENTS):
                    # XHTML style self closed tags such as <title/> or
                    # <div/>, close them immediately instead of letting
                    # them swallow the rest of the document
                    token['selfClosing'] = False
                    token['selfClosingAcknowledged'] = True
                    yield token
                    yield {'type': end_tag, 'name': token['name'], 'data': []}
                    self.state = self.dataState
                else:
                    yield token

    class Parser(html5lib.HTMLParser):

        # Same as HTMLParser._parse() in html5lib 1.1, except for the
        # tokenizer class
        def _parse(self, stream, innerHTML=False, container='div', scripting=False, **kwargs):
            self.innerHTMLMode = innerHTML
            self.container = container
            self.scripting = scripting
            self.tokenizer = (Tokenizer if maybe_xhtml else HTMLTokenizer)(stream, parser=self, **kwargs)
            self.reset()
            try:
                self.mainLoop()
            except constants._ReparseException:
                self.reset()
                self.mainLoop()

    _parser_classes[maybe_xhtml] = Parser
    return Parser


def _run_parser(html, maybe_xhtml, fragment_context=None):
    import html5lib
    builder = html5lib.getTreeBuilder('etree', ET, fullTree=True)
    parser = _parser_class(maybe_xhtml)(tree=builder, namespaceHTMLElements=True)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        if fragment_context is None:
            return parser.parse(html)
        return parser.parseFragment(html, container=fragment_context)


class _Converter:

    def __init__(self, namespace_elements, maybe_xhtml, sanitize_names, root_nsmap):
        self.namespace_elements = namespace_elements or maybe_xhtml
        self.maybe_xhtml = maybe_xhtml
        self.sanitize_names = sanitize_names
        self.prefixes = dict(WELL_KNOWN_PREFIXES)
        self.prefixes.update(root_nsmap)
        self.root_nsmap = root_nsmap

    def name(self, name):
        if self.sanitize_names:
            return sanitize_name(name)
        return name

    def tag(self, src_tag):
        ns, local = _split(src_tag)
        if ns == XHTML_NS:
            if self.maybe_xhtml and ':' in local:
                prefix, _, rest = local.partition(':')
                pns = self.prefixes.get(prefix)
                if pns and rest:
                    return f'{{{pns}}}{self.name(rest)}', pns
            return (f'{{{XHTML_NS}}}{self.name(local)}' if self.namespace_elements else self.name(local)), XHTML_NS
        if not self.namespace_elements:
            return self.name(local), ns
        return f'{{{ns}}}{self.name(local)}' if ns else self.name(local), ns

    def attrib(self, src, elem_ns):
        ans = {}
        for key, val in src.items():
            ns, local = _split(key)
            if ns is None:
                if local == 'xmlns' or local.startswith('xmlns:'):
                    continue
                if ':' in local:
                    prefix, _, rest = local.partition(':')
                    pns = self.prefixes.get(prefix) if (self.maybe_xhtml or prefix == 'xml') else None
                    if pns and rest:
                        if self.namespace_elements or pns == XML_NS:
                            key = f'{{{pns}}}{self.name(rest)}'
                        else:
                            key = self.name(rest)
                        ans[key] = val
                        continue
                key = self.name(local)
            elif ns == XMLNS_NS:
                continue
            elif self.namespace_elements or ns == XML_NS:
                key = f'{{{ns}}}{self.name(local)}'
            else:
                key = self.name(local)
            ans[key] = val
        return ans

    def set_attribs(self, elem, attrib):
        for k, v in attrib.items():
            try:
                elem.set(k, v)
            except ValueError:
                try:
                    elem.set(k, _clean_text(v))
                except ValueError:
                    pass

    def convert_children(self, src, dest, dest_ns):
        # Iterative depth first copy to avoid recursion limits on deeply
        # nested (broken) markup
        stack = [(src, dest, dest_ns, iter(src))]
        comment_tag = ET.Comment
        pi_tag = ET.ProcessingInstruction
        last_by_parent = {}
        while stack:
            s, d, dns, it = stack[-1]
            child = next(it, None)
            if child is None:
                stack.pop()
                continue
            ctag = child.tag
            if ctag is comment_tag:
                node = etree.Comment(_clean_comment(child.text))
                d.append(node)
            elif ctag is pi_tag or not isinstance(ctag, str) or ctag == '<!DOCTYPE>':
                if child.tail:
                    self.append_text(d, child.tail)
                continue
            else:
                tag, ns = self.tag(ctag)
                nsmap = None
                if self.namespace_elements and ns not in (dns, None) and ns in (SVG_NS, MATHML_NS):
                    nsmap = {None: ns}
                try:
                    node = etree.SubElement(d, tag, nsmap=nsmap) if nsmap else etree.SubElement(d, tag)
                except ValueError:
                    node = etree.SubElement(d, '_' + sanitize_name(tag.rpartition('}')[-1]))
                if child.attrib:
                    self.set_attribs(node, self.attrib(child.attrib, ns))
                if child.text:
                    node.text = _safe(child.text)
                if len(child):
                    stack.append((child, node, ns if self.namespace_elements else dns, iter(child)))
            if child.tail:
                node.tail = _safe(child.tail)

    def append_text(self, parent, text):
        text = _safe(text)
        if len(parent):
            last = parent[-1]
            last.tail = (last.tail or '') + text
        else:
            parent.text = (parent.text or '') + text


_safe = _clean_text


def _root_nsmap(src_root):
    ans = {}
    for key, val in src_root.attrib.items():
        ns, local = _split(key)
        if ns is None and local.startswith('xmlns:'):
            prefix = local[6:]
            if prefix and val:
                ans[prefix] = val
        elif ns == XMLNS_NS and local != 'xmlns' and val:
            ans[local] = val
    return ans


def parse(
    html,
    transport_encoding=None,
    namespace_elements=False,
    treebuilder='lxml',
    fallback_encoding=None,
    keep_doctype=True,
    maybe_xhtml=False,
    return_root=True,
    line_number_attr=None,
    sanitize_names=True,
    stack_size=16 * 1024,
    fragment_context=None,
):
    '''
    Parse the specified :attr:`html` and return the parsed representation.

    Mirrors the API of html5_parser.parse(). line_number_attr and
    stack_size are accepted for compatibility but are ignored.
    '''
    treebuilder = (treebuilder or 'lxml').lower()
    if treebuilder == 'soup' or not return_root and treebuilder not in ('lxml', 'lxml_html'):
        from .soup import parse as soup_parse
        return soup_parse(html, return_root=return_root, transport_encoding=transport_encoding,
                          fallback_encoding=fallback_encoding)
    html = _decode(html or '', transport_encoding, fallback_encoding)
    if fragment_context:
        ctx = fragment_context
        if ctx.startswith('svg:') or ctx.startswith('math:'):
            ctx = ctx.partition(':')[2]
        frag = _run_parser(html, maybe_xhtml, ctx)
        conv = _Converter(namespace_elements, maybe_xhtml, sanitize_names, {})
        if conv.namespace_elements:
            container = etree.Element(f'{{{XHTML_NS}}}{ctx}', nsmap={None: XHTML_NS, 'xlink': XLINK_NS})
        else:
            container = etree.Element(ctx)
        if frag.text:
            container.text = _clean_text(frag.text)
        conv.convert_children(frag, container, XHTML_NS)
        return container

    doc = _run_parser(html, maybe_xhtml)
    src_root = None
    for child in doc:
        if isinstance(child.tag, str) and child.tag.endswith('}html'):
            src_root = child
            break
    if src_root is None:  # cannot happen with the HTML 5 algorithm
        src_root = ET.Element(f'{{{XHTML_NS}}}html')

    root_ns = _root_nsmap(src_root) if maybe_xhtml else {}
    conv = _Converter(namespace_elements, maybe_xhtml, sanitize_names, root_ns)
    if conv.namespace_elements:
        nsmap = {None: XHTML_NS, 'xlink': XLINK_NS}
        for prefix, uri in root_ns.items():
            if prefix not in ('xml', 'xmlns') and uri != XHTML_NS:
                try:
                    etree.QName(uri, 'x')
                    nsmap[sanitize_name(prefix)] = uri
                except ValueError:
                    pass
        root = etree.Element(f'{{{XHTML_NS}}}html', nsmap=nsmap)
    else:
        root = etree.Element('html')
    conv.set_attribs(root, conv.attrib(src_root.attrib, XHTML_NS))
    if src_root.text and src_root.text.strip():
        root.text = _clean_text(src_root.text)
    conv.convert_children(src_root, root, XHTML_NS)

    # Comments outside the root element
    before = True
    for child in doc:
        if child is src_root:
            before = False
            continue
        if child.tag is ET.Comment:
            c = etree.Comment(_clean_comment(child.text))
            if before:
                root.addprevious(c)
            else:
                root.addnext(c)

    if treebuilder == 'lxml_html':
        from lxml.html import fromstring as html_fromstring
        root = html_fromstring(etree.tostring(root, encoding='unicode'))
    if return_root:
        return root
    return root.getroottree()
