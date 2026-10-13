"""html5_parser.soup — build a BeautifulSoup tree using the HTML 5 algorithm."""


def set_soup_module(val):
    pass


def parse(html, return_root=True, keep_doctype=True, transport_encoding=None,
          fallback_encoding=None, **kwargs):
    '''
    Parse the specified :attr:`html` into a BeautifulSoup tree. Mirrors
    html5_parser.soup.parse(), using the html5lib tree builder of bs4, which
    implements the same parsing algorithm as html5-parser.
    '''
    import bs4
    if isinstance(html, bytes):
        from . import _decode
        html = _decode(html, transport_encoding, fallback_encoding)
    try:
        soup = bs4.BeautifulSoup(html, 'html5lib')
    except bs4.FeatureNotFound:
        soup = bs4.BeautifulSoup(html, 'html.parser')
    if not keep_doctype:
        for x in list(soup.contents):
            if isinstance(x, bs4.Doctype):
                x.extract()
    if return_root:
        root = soup.find('html')
        return root if root is not None else soup
    return soup
