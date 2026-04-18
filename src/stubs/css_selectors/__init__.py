"""
WASM stub for calibre's css_selectors C extension.
Wraps lxml.cssselect to provide the same interface.
"""
import re
import sys

from lxml.cssselect import CSSSelector, SelectorError as _LxmlSelectorError, SelectorSyntaxError

class SelectorError(Exception):
    pass

INAPPROPRIATE_PSEUDO_CLASSES = frozenset({
    'link', 'visited', 'hover', 'active', 'focus',
    'target', 'enabled', 'disabled', 'checked', 'indeterminate',
})

_PSEUDO_PAT = re.compile(
    r':{1,2}(' + '|'.join(INAPPROPRIATE_PSEUDO_CLASSES) + r')',
    re.I,
)

_SELECTOR_CACHE = {}
_SELECTOR_CACHE_MAX = 512

def _make_ns_agnostic(xpath):
    """Rewrite cssselect-generated XPath to match regardless of element namespace."""

    xpath = re.sub(
        r"::([a-zA-Z][a-zA-Z0-9-]*)",
        lambda m: "::*[local-name()='" + m.group(1) + "']",
        xpath,
    )

    xpath = re.sub(
        r"/([a-zA-Z][a-zA-Z0-9-]*)(?![\w-]*::)",
        lambda m: "/*[local-name()='" + m.group(1) + "']",
        xpath,
    )
    return xpath

def _get_cached_selector(css, namespaces=None):
    """Get or create a cached CSS selector."""
    cache_key = (css, id(namespaces) if namespaces else None)
    if cache_key in _SELECTOR_CACHE:
        return _SELECTOR_CACHE[cache_key]
    sel = CSSSelector(css, namespaces=namespaces)
    if len(_SELECTOR_CACHE) < _SELECTOR_CACHE_MAX:
        _SELECTOR_CACHE[cache_key] = sel
    return sel

_KNOWN_NS_PREFIXES = {
    'svg': 'http://www.w3.org/2000/svg',
    'xlink': 'http://www.w3.org/1999/xlink',
    'html': 'http://www.w3.org/1999/xhtml',
    'xhtml': 'http://www.w3.org/1999/xhtml',
    'epub': 'http://www.idpf.org/2007/ops',
    'mathml': 'http://www.w3.org/1998/Math/MathML',
    'xml': 'http://www.w3.org/XML/1998/namespace',
}

_NS_PREFIX_PAT = re.compile(r'(\w+)\|(\w+)')

def _resolve_ns_selector(css):
    """
    Convert namespace-prefixed CSS selectors to local-name XPath queries.

    E.g. 'svg|svg' → XPath that matches elements with local-name 'svg'
    regardless of namespace.
    """
    match = _NS_PREFIX_PAT.search(css)
    if match:
        return True, match.group(2)  
    return False, None

def parse(css):
    return css

class Select:
    def __init__(self, root, default_lang=None, default_namespace=None,
                 ignore_inappropriate_pseudo_classes=False, dispatch_map=None, trace=False):
        self.root = root
        self.default_namespace = default_namespace
        self.default_lang = default_lang
        self.ignore_inappropriate_pseudo_classes = ignore_inappropriate_pseudo_classes
        self._has_ns = False
        if root is not None:
            tag = getattr(root, 'tag', '')
            if isinstance(tag, str) and '{' in tag:
                self._has_ns = True

    def __call__(self, css, namespaces=None):
        try:
            if self.ignore_inappropriate_pseudo_classes:
                css = _PSEUDO_PAT.sub('', css)

            css = css.strip()
            if not css:
                return []

            has_ns_prefix, local_name = _resolve_ns_selector(css)
            if has_ns_prefix and local_name:

                xpath = f".//*[local-name()='{local_name}']"
                return self.root.xpath(xpath)

            sel = _get_cached_selector(css, namespaces=namespaces)
            if self._has_ns:
                xpath = _make_ns_agnostic(sel.path)
                return self.root.xpath(xpath)
            return sel(self.root)
        except (_LxmlSelectorError, SelectorSyntaxError) as e:

            print(f'css_selectors: invalid selector {css!r}: {e}',
                  file=sys.stderr)
            return []
        except Exception as e:

            print(f'css_selectors: error evaluating {css!r}: {e}',
                  file=sys.stderr)
            return []

    def __bool__(self):
        return self.root is not None

def get_parsed_selector(css):
    return css
