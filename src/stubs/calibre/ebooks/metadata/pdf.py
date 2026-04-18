"""
WASM stub for calibre.ebooks.metadata.pdf

Replaces subprocess calls to pdfinfo with the pdfinfo WASM binary
that the JS layer registers as globalThis._pdfinfoWasmOutput via
Pyodide's JS interop.
"""

import functools
import os
import re
import shutil

from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.metadata import (
    MetaInformation, string_to_authors, check_isbn, check_doi)

def _get_wasm_output():
    """Get the JS-registered pdfinfo WASM function via Pyodide."""
    try:
        from pyodide.ffi import JsProxy  
        import js
        output_fn = getattr(js, '_pdfinfoWasmOutput', None)
        if output_fn is not None:
            return output_fn
    except ImportError:
        pass
    return None

def _call_pdfinfo(args, cwd=None):
    """
    Call pdfinfo via the WASM bridge.

    Falls back to returning empty string if the bridge is not available.
    """
    wasm_output = _get_wasm_output()
    if wasm_output is None:
        print('pdfinfo WASM not available — PDF metadata extraction disabled')
        return b''

    from pyodide.ffi import to_js
    raw = wasm_output(to_js(args), cwd or os.getcwd())
    if hasattr(raw, 'valueOf'):
        raw = raw.valueOf()
    return str(raw).encode('utf-8')

def read_info(outputdir, get_cover):
    """Read info dict and cover from a pdf file named src.pdf in outputdir."""
    source_file = os.path.join(outputdir, 'src.pdf')
    ans = {}

    try:
        raw = _call_pdfinfo(
            ['pdfinfo', '-enc', 'UTF-8', '-isodates', source_file],
            cwd=outputdir,
        )
    except Exception as e:
        print(f'pdfinfo errored out: {e}')
        return None

    if not raw:
        return None

    try:
        info_raw = raw.decode('utf-8')
    except UnicodeDecodeError:
        print('pdfinfo returned no UTF-8 data')
        return None

    for line in info_raw.splitlines():
        if ':' not in line:
            continue
        field, val = line.partition(':')[::2]
        val = val.strip()
        if field and val:
            ans[field] = val.strip()

    try:
        raw = _call_pdfinfo(
            ['pdfinfo', '-meta', source_file],
            cwd=outputdir,
        )
    except Exception as e:
        print(f'pdfinfo failed to read XML metadata: {e}')
    else:
        if raw:
            parts = re.split(br'^Metadata:', raw, 1, flags=re.MULTILINE)
            if len(parts) > 1:
                raw = parts[1].strip()
            if raw:
                ans['xmp_metadata'] = raw

    return ans

def is_pdf_encrypted(path_to_pdf):
    try:
        raw = _call_pdfinfo(['pdfinfo', path_to_pdf],
                            cwd=os.path.dirname(path_to_pdf) or os.getcwd())
    except Exception:
        return False
    q = re.search(br'^Encrypted:\s*(\S+)', raw, flags=re.MULTILINE)
    if q is not None:
        return q.group(1) == b'yes'
    return False

def get_metadata(stream, cover=True):
    with TemporaryDirectory('_pdf_metadata_read') as pdfpath:
        stream.seek(0)
        with open(os.path.join(pdfpath, 'src.pdf'), 'wb') as f:
            shutil.copyfileobj(stream, f)

        info = read_info(pdfpath, False)
        if info is None:
            raise ValueError('Could not read info dict from PDF')

    title = info.get('Title', None) or 'Unknown'
    au = info.get('Author', None)
    if au is None:
        au = ['Unknown']
    else:
        au = string_to_authors(au)
    mi = MetaInformation(title, au)

    creator = info.get('Creator', None)
    if creator:
        mi.book_producer = creator

    keywords = info.get('Keywords', None)
    mi.tags = []
    if keywords:
        mi.tags = [x.strip() for x in keywords.split(',')]
        isbn = [check_isbn(x) for x in mi.tags if check_isbn(x)]
        if isbn:
            mi.isbn = isbn = isbn[0]
        mi.tags = [x for x in mi.tags if check_isbn(x) != isbn]

    subject = info.get('Subject', None)
    if subject:
        mi.tags.insert(0, subject)

    if 'xmp_metadata' in info:
        from calibre.ebooks.metadata.xmp import consolidate_metadata
        mi = consolidate_metadata(mi, info)

    for scheme, check_func in {'doi': check_doi, 'isbn': check_isbn}.items():
        if scheme not in mi.get_identifiers():
            for k, v in info.items():
                if k != 'xmp_metadata':
                    val = check_func(v)
                    if val:
                        mi.set_identifier(scheme, val)
                        break

    return mi

get_quick_metadata = functools.partial(get_metadata, cover=False)

def set_metadata(stream, mi):
    return None
