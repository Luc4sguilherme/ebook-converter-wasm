"""
ebook_convert_wasm.py — Entry point for ebook-convert in WASM.

Uses the original calibre package (kovidgoyal/calibre)
for the conversion pipeline.
"""
import sys
import os
import builtins

def _init_calibre_env():
    """Set up the calibre environment for WASM."""

    if not hasattr(builtins, '_'):
        builtins._ = lambda x: x
    if not hasattr(builtins, '__'):
        builtins.__ = lambda x: x
    if not hasattr(builtins, 'ngettext'):
        builtins.ngettext = lambda s, p, n: s if n == 1 else p
    if not hasattr(builtins, 'pgettext'):
        builtins.pgettext = lambda c, m: m

    for d in ['/tmp/calibre-config', '/tmp/calibre-cache',
              '/tmp/calibre-convert']:
        os.makedirs(d, exist_ok=True)

    os.environ['CALIBRE_CONFIG_DIR'] = '/tmp/calibre-config'
    os.environ.setdefault('CALIBRE_OVERRIDE_LANG', 'en')

def _coerce_option(rec, val):
    '''
    Convert an option value to the type ebook-convert's command line parser
    would produce for it, which is derived from the type of the recommended
    value of the option (see calibre.ebooks.conversion.cli).
    '''
    import numbers
    default = rec.recommended_value
    if val is None:
        return None
    if isinstance(default, bool):
        if isinstance(val, str):
            return val.strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(val)
    if isinstance(val, bool):
        return val
    if isinstance(default, numbers.Real):
        # The command line parser uses the float type for integer defaults too
        return float(val)
    if isinstance(val, (int, float)) and not isinstance(val, bool) and isinstance(default, str):
        return str(val)
    return val

def convert(input_path, output_path, options=None):
    """
    Convert an ebook from one format to another.

    Args:
        input_path:  Path to input file in virtual filesystem
        output_path: Path to output file in virtual filesystem
        options:     Dict of conversion options (optional). Names can use
                     dashes or underscores (base-font-size or base_font_size)

    Returns:
        str: Path to the output file

    Raises:
        Exception: If conversion fails
    """
    _init_calibre_env()

    from calibre.utils.logging import default_log as log
    from calibre.ebooks.conversion.plumber import Plumber
    from calibre.customize.conversion import OptionRecommendation

    def progress_reporter(frac, msg=''):
        if msg:
            percent = int(frac * 100)
            log.info('%d%% %s' % (percent, msg))
        try:
            import js as _js
            cb = getattr(_js, '_calibreProgressCallback', None)
            if cb is not None:
                cb(frac, msg or '')
        except Exception:
            pass

    plumber = Plumber(input_path, output_path, log, progress_reporter)

    if options:
        recommendations = []
        for key, val in options.items():
            name = key.lstrip('-').replace('-', '_')
            if val == 'None':
                val = None
            rec = plumber.get_option_by_name(name)
            if rec is None:
                log.warn(f'Ignoring unknown conversion option: {key}')
                continue
            try:
                val = _coerce_option(rec, val)
            except (TypeError, ValueError):
                raise ValueError(f'Invalid value for the conversion option {key}: {val!r}')
            recommendations.append((name, val, OptionRecommendation.HIGH))
        plumber.merge_ui_recommendations(recommendations)

    plumber.run()
    return output_path

def htmlz_to_html(htmlz_path):
    '''
    Return the main HTML file of the HTMLZ archive as a single self contained
    document: stylesheets are inlined and images embedded as data: URLs.
    '''
    import base64
    import posixpath
    import re
    import zipfile

    from calibre import guess_type

    with zipfile.ZipFile(htmlz_path) as zf:
        names = set(zf.namelist())
        html_names = [n for n in zf.namelist() if n.lower().endswith(('.html', '.xhtml', '.htm'))]
        if not html_names:
            with open(htmlz_path, 'rb') as f:
                return f.read()
        main = 'index.html' if 'index.html' in names else next(
            (n for n in html_names if 'index' in n.lower()), html_names[0])
        base = posixpath.dirname(main)
        html = zf.read(main).decode('utf-8', 'replace')

        def resolve(href, relative_to):
            href = href.strip().strip('\'"')
            if not href or re.match(r'^[a-z][a-z0-9+.-]*:', href, re.I) or href.startswith('#'):
                return None
            from urllib.parse import unquote
            href = unquote(href.partition('#')[0].partition('?')[0])
            name = posixpath.normpath(posixpath.join(relative_to, href))
            return name if name in names else None

        def data_url(name):
            mt = guess_type(name)[0] or 'application/octet-stream'
            return f'data:{mt};base64,' + base64.standard_b64encode(zf.read(name)).decode('ascii')

        def embed_css_urls(css, relative_to):
            def sub(m):
                name = resolve(m.group(2), relative_to)
                return f'url({data_url(name)})' if name else m.group(0)
            return re.sub(r'url\(\s*([\'"]?)([^\'")]+)\1\s*\)', sub, css)

        def inline_link(m):
            tag = m.group(0)
            if 'stylesheet' not in tag.lower():
                return tag
            href = re.search(r'href\s*=\s*(["\'])(.*?)\1', tag, re.I | re.S)
            name = resolve(href.group(2), base) if href else None
            if not name:
                return tag
            css = zf.read(name).decode('utf-8', 'replace')
            css = embed_css_urls(css, posixpath.dirname(name))
            return '<style type="text/css">\n' + css.replace('</style', '<\\/style') + '\n</style>'

        html = re.sub(r'<link\b[^>]*>', inline_link, html, flags=re.I)

        def embed_src(m):
            name = resolve(m.group(3), base)
            return f'{m.group(1)}={m.group(2)}{data_url(name)}{m.group(2)}' if name else m.group(0)

        html = re.sub(r'\b(src|xlink:href|poster)\s*=\s*(["\'])(.*?)\2', embed_src, html, flags=re.I | re.S)
        html = re.sub(r'(<style\b[^>]*>)(.*?)(</style>)',
                      lambda m: m.group(1) + embed_css_urls(m.group(2), base) + m.group(3), html, flags=re.I | re.S)
        return html.encode('utf-8')

def pack_directory(path):
    ''' Return the contents of a directory (e.g. OEB output) as a ZIP archive '''
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(path):
            for fname in files:
                fpath = os.path.join(root, fname)
                zf.write(fpath, os.path.relpath(fpath, path))
    return buf.getvalue()

def get_version():
    return '0.1.0-wasm'

def available_input_formats():
    """Return set of supported input formats."""
    _init_calibre_env()
    try:
        from calibre.customize.ui import available_input_formats as _aif
        return _aif()
    except Exception:
        return {'epub', 'html', 'txt', 'mobi', 'docx', 'rtf', 'fb2', 'odt',
                'pdb', 'lrf', 'azw3', 'azw4', 'htmlz', 'pdf'}

def available_output_formats():
    """Return set of supported output formats."""
    _init_calibre_env()
    try:
        from calibre.customize.ui import available_output_formats as _aof
        return _aof()
    except Exception:
        return {'epub', 'html', 'htmlz', 'txt', 'mobi', 'docx', 'rtf', 'fb2',
                'lrf', 'azw3'}
