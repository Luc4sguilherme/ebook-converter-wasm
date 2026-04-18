"""Stub for calibre_extensions.fast_html_entities — pure Python fallback."""

import html
import re

_ENTITY_RE = re.compile(r'&(#?[a-zA-Z0-9]+);')

def replace_all_entities(raw, xml_replace=False):
    """Replace all HTML entities in *raw* with their Unicode equivalents.

    If *xml_replace* is True, re-escape the five XML-special characters
    after entity expansion (useful when the result will be embedded in XML).
    """
    result = html.unescape(raw)
    if xml_replace:
        result = (result
                  .replace('&', '&amp;')
                  .replace('<', '&lt;')
                  .replace('>', '&gt;')
                  .replace('"', '&quot;')
                  .replace("'", '&apos;'))
    return result
