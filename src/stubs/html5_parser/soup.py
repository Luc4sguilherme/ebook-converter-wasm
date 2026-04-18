"""html5_parser.soup — BeautifulSoup integration for WASM html5_parser stub."""

def parse(html, return_root=False, **kwargs):
    """Parse HTML into a BeautifulSoup tree.

    This module always returns a bs4.BeautifulSoup object (return_root
    defaults to False here, matching the real html5_parser.soup API).
    """
    from html5_parser import parse as _parse
    return _parse(html, return_root=return_root, **kwargs)
