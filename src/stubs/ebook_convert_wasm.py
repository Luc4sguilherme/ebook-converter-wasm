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

def convert(input_path, output_path, options=None):
    """
    Convert an ebook from one format to another.

    Args:
        input_path:  Path to input file in virtual filesystem
        output_path: Path to output file in virtual filesystem
        options:     Dict of conversion options (optional)

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
            from pyodide.ffi import to_js  
            import js as _js
            cb = getattr(_js, '_calibreProgressCallback', None)
            if cb is not None:
                cb(frac, msg or '')
        except Exception:
            pass

    plumber = Plumber(input_path, output_path, log, progress_reporter)

    if options:
        recommendations = [
            (key, None if val == 'None' else val, OptionRecommendation.HIGH)
            for key, val in options.items()
        ]
        plumber.merge_ui_recommendations(recommendations)

    plumber.run()
    return output_path

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
