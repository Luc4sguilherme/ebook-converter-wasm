"""
WASM stub for calibre.ebooks.pdf.html_writer

Replaces the Qt WebEngine-based HTML→PDF renderer with fpdf2,
a pure-Python PDF library that works in Pyodide/WASM.

The approach:
  1. Parse the OPF to get the spine (ordered HTML files)
  2. Read each HTML file, extract text content
  3. Render to PDF using fpdf2's write_html()
"""
import os
import re

from lxml import etree

PAGE_SIZES = {
    'a0': (2383.94, 3370.39),
    'a1': (1683.78, 2383.94),
    'a2': (1190.55, 1683.78),
    'a3': (841.89, 1190.55),
    'a4': (595.28, 841.89),
    'a5': (419.53, 595.28),
    'a6': (297.64, 419.53),
    'b0': (2834.65, 4008.19),
    'b1': (2004.09, 2834.65),
    'b2': (1417.32, 2004.09),
    'b3': (1000.63, 1417.32),
    'b4': (708.66, 1000.63),
    'b5': (498.90, 708.66),
    'b6': (354.33, 498.90),
    'letter': (612.0, 792.0),
    'legal': (612.0, 1008.0),
}

UNIT_FACTORS = {
    'point': 1.0,
    'inch': 72.0,
    'millimeter': 72.0 / 25.4,
    'centimeter': 72.0 / 2.54,
    'pica': 12.0,
    'didot': 0.375 * (72.0 / 25.4),
    'cicero': 12 * 0.375 * (72.0 / 25.4),
    'devicepixel': 1.0,
}

def _get_page_size_mm(opts):
    """Return (width_mm, height_mm) based on opts."""
    if opts.custom_size:
        parts = opts.custom_size.lower().split('x')
        if len(parts) == 2:
            try:
                w, h = float(parts[0].strip()), float(parts[1].strip())
                factor = UNIT_FACTORS.get(opts.unit, 72.0)

                w_mm = (w * factor) / (72.0 / 25.4)
                h_mm = (h * factor) / (72.0 / 25.4)
                return (w_mm, h_mm)
            except (ValueError, TypeError):
                pass

    paper = getattr(opts, 'paper_size', 'letter') or 'letter'
    pts = PAGE_SIZES.get(paper.lower(), PAGE_SIZES['letter'])

    w_mm = pts[0] / (72.0 / 25.4)
    h_mm = pts[1] / (72.0 / 25.4)
    return (w_mm, h_mm)

def _get_margins_mm(opts):
    """Return (left, top, right, bottom) margins in mm."""
    def to_mm(val):

        if val is None or val < 0:
            return 25.4  
        return val / (72.0 / 25.4)

    left = to_mm(getattr(opts, 'pdf_page_margin_left', None) or
                 getattr(opts, 'margin_left', None))
    top = to_mm(getattr(opts, 'pdf_page_margin_top', None) or
                getattr(opts, 'margin_top', None))
    right = to_mm(getattr(opts, 'pdf_page_margin_right', None) or
                  getattr(opts, 'margin_right', None))
    bottom = to_mm(getattr(opts, 'pdf_page_margin_bottom', None) or
                   getattr(opts, 'margin_bottom', None))
    return left, top, right, bottom

def _parse_css_length_to_pt(css_text, prop):
    """Extract a CSS length property value and convert to points."""
    m = re.search(rf'(?:^|;|\s){prop}\s*:\s*([\d.]+)\s*(pt|px|mm|cm|in)', css_text)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    if unit == 'pt':
        return val
    elif unit == 'px':
        return val * 72.0 / 96.0
    elif unit == 'mm':
        return val * 72.0 / 25.4
    elif unit == 'cm':
        return val * 72.0 / 2.54
    elif unit == 'in':
        return val * 72.0
    return None

def _parse_css_dimensions(css_text):
    """Parse CSS and return {class_name: (width_pt, height_pt)} for rules with dimensions."""
    dims = {}
    for m in re.finditer(r'\.(\w+)\s*\{([^}]*)\}', css_text):
        cls_name = m.group(1)
        body = m.group(2)
        w = _parse_css_length_to_pt(body, 'width')
        h = _parse_css_length_to_pt(body, 'height')
        if w is not None or h is not None:
            dims[cls_name] = (w, h)
    return dims

def _inject_image_dimensions(html_content, html_dir, avail_w_pt):
    """
    Inject width/height attributes into <img> tags that lack them.

    fpdf2's write_html() interprets img width/height as points (divides by k),
    so all values are computed in points.

    Sources (in priority order):
      1. CSS class dimensions (from <style> blocks or linked CSS files)
      2. Inline style dimensions
      3. Actual image file dimensions via PIL
    """

    css_dims = {}
    for sm in re.finditer(r'<style[^>]*>(.*?)</style>', html_content,
                          re.DOTALL | re.IGNORECASE):
        css_dims.update(_parse_css_dimensions(sm.group(1)))
    for lm in re.finditer(r'<link[^>]*href="([^"]*\.css)"', html_content,
                          re.IGNORECASE):
        css_path = os.path.normpath(os.path.join(html_dir, lm.group(1)))
        if os.path.exists(css_path):
            try:
                with open(css_path, 'r', encoding='utf-8', errors='replace') as f:
                    css_dims.update(_parse_css_dimensions(f.read()))
            except Exception:
                pass

    def _process_img(match):
        tag = match.group(0)

        if (re.search(r'\bwidth\s*=\s*"', tag, re.IGNORECASE) and
                re.search(r'\bheight\s*=\s*"', tag, re.IGNORECASE)):
            return tag

        w_pt = None
        h_pt = None

        cls_m = re.search(r'\bclass="([^"]*)"', tag, re.IGNORECASE)
        if cls_m:
            for cls in cls_m.group(1).split():
                if cls in css_dims:
                    w_pt, h_pt = css_dims[cls]
                    break

        if w_pt is None and h_pt is None:
            style_m = re.search(r'\bstyle="([^"]*)"', tag, re.IGNORECASE)
            if style_m:
                w_pt = _parse_css_length_to_pt(style_m.group(1), 'width')
                h_pt = _parse_css_length_to_pt(style_m.group(1), 'height')

        if w_pt is None and h_pt is None:
            src_m = re.search(r'\bsrc="([^"]*)"', tag, re.IGNORECASE)
            if src_m:
                src = src_m.group(1)
                img_path = (src if os.path.isabs(src)
                            else os.path.normpath(os.path.join(html_dir, src)))
                if os.path.exists(img_path):
                    try:
                        from PIL import Image
                        with Image.open(img_path) as im:
                            pw, ph = im.size
                            w_pt = pw * 72.0 / 96.0
                            h_pt = ph * 72.0 / 96.0
                    except Exception:
                        pass

        if w_pt is None and h_pt is None:
            return tag

        if w_pt is not None and w_pt > avail_w_pt:
            if h_pt is not None:
                h_pt = h_pt * (avail_w_pt / w_pt)
            w_pt = avail_w_pt

        tag = re.sub(r'\s+width="[^"]*"', '', tag, flags=re.IGNORECASE)
        tag = re.sub(r'\s+height="[^"]*"', '', tag, flags=re.IGNORECASE)

        attrs = ''
        if w_pt is not None:
            attrs += f' width="{w_pt:.1f}"'
        if h_pt is not None:
            attrs += f' height="{h_pt:.1f}"'

        tag = re.sub(r'\s*/?\s*>$', f'{attrs}>', tag)
        return tag

    return re.sub(r'<img[^>]*/?>', _process_img, html_content, flags=re.IGNORECASE)

XHTML_NS = 'http://www.w3.org/1999/xhtml'
_BLOCK_TAGS = frozenset((
    'body', 'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'ul', 'ol',
    'dl', 'dt', 'dd', 'blockquote', 'pre', 'table', 'thead', 'tbody', 'tfoot',
    'tr', 'td', 'th', 'section', 'article', 'center', 'header', 'footer',
    'nav', 'aside', 'main', 'figure', 'figcaption', 'hr',
))
_ALIGNABLE_TAGS = frozenset(('p', 'div', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'))
_INHERITED = ('text-align', 'font-weight', 'font-style', 'color', 'text-decoration')
# Formatting implied by the tag itself (user agent stylesheet)
_TAG_FORMATTING = {
    'b': 'b', 'strong': 'b', 'th': 'b',
    'h1': 'b', 'h2': 'b', 'h3': 'b', 'h4': 'b', 'h5': 'b', 'h6': 'b',
    'i': 'i', 'em': 'i', 'cite': 'i', 'var': 'i', 'dfn': 'i',
    'u': 'u', 'ins': 'u', 's': 's', 'del': 's', 'strike': 's',
}
_BLACK = frozenset(('black', '#000', '#000000', 'rgb(0,0,0)', 'initial', 'inherit', 'currentcolor', 'windowtext'))


def _parse_declarations(text):
    ans = {}
    for decl in (text or '').split(';'):
        name, sep, val = decl.partition(':')
        if sep:
            val = val.replace('!important', '').strip()
            if val:
                ans[name.strip().lower()] = val
    return ans


def _parse_stylesheet(css, rules):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    # Drop @page, @font-face, etc. rules, keep the contents of @media blocks
    css = re.sub(r'@(?:page|font-face)[^{]*\{[^}]*\}', '', css, flags=re.IGNORECASE)
    css = re.sub(r'@[a-z-]+[^{;]*;', '', css, flags=re.IGNORECASE)
    for m in re.finditer(r'([^{}@]+)\{([^{}]*)\}', css):
        decls = _parse_declarations(m.group(2))
        if not decls:
            continue
        for sel in m.group(1).split(','):
            sel = sel.strip().lower()
            if re.match(r'^[a-z0-9]*(\.[\w-]+)?$', sel) and sel:
                rules.setdefault(sel, {}).update(decls)


def _css_color(val):
    ''' Return the color as #rrggbb or None for black and unsupported values '''
    val = val.strip().lower()
    if val in _BLACK:
        return None
    from PIL import ImageColor
    try:
        rgb = ImageColor.getrgb(val)[:3]
    except ValueError:
        return None
    return None if rgb == (0, 0, 0) else '#{:02x}{:02x}{:02x}'.format(*rgb)


def _is_bold(val):
    val = (val or '').strip().lower()
    if val in ('bold', 'bolder'):
        return True
    return val.isdigit() and int(val) >= 600


def _local(tag):
    return tag.rpartition('}')[-1].lower() if isinstance(tag, str) else ''


def _wrap_content(elem, tag, **attrs):
    wrapper = elem.makeelement(f'{{{XHTML_NS}}}{tag}' if elem.tag.startswith('{') else tag, attrs)
    wrapper.text, elem.text = elem.text, None
    for child in list(elem):
        wrapper.append(child)
    elem.append(wrapper)
    return wrapper


def _apply_css_styles(html_content, html_dir):
    '''
    Resolve the CSS of the book (calibre's flattened class based stylesheets
    and inline styles) and express the parts that fpdf2 understands with HTML
    markup: text alignment as style on block elements, bold, italic,
    underline, strike through, colors, superscripts and subscripts as
    formatting tags, and remove elements with display: none.
    '''
    try:
        root = etree.fromstring(html_content.encode('utf-8'))
    except Exception:
        return html_content
    rules = {}
    for elem in root.iter():
        tag = _local(elem.tag)
        if tag == 'link' and 'stylesheet' in (elem.get('rel') or '').lower() and elem.get('href'):
            path = os.path.normpath(os.path.join(html_dir, elem.get('href')))
            try:
                with open(path, 'rb') as f:
                    _parse_stylesheet(f.read().decode('utf-8', 'replace'), rules)
            except OSError:
                pass
        elif tag == 'style' and elem.text:
            _parse_stylesheet(elem.text, rules)

    body = next((e for e in root.iter() if _local(e.tag) == 'body'), None)
    if body is None:
        return html_content

    def walk(elem, inherited, applied):
        tag = _local(elem.tag)
        decl = dict(rules.get(tag, {}))
        for cls in (elem.get('class') or '').split():
            cls = cls.lower()
            decl.update(rules.get('.' + cls, {}))
            decl.update(rules.get(f'{tag}.{cls}', {}))
        inline = _parse_declarations(elem.get('style'))
        decl.update(inline)
        if decl.get('display', '').lower() == 'none':
            parent = elem.getparent()
            if parent is not None:
                if elem.tail:
                    prev = elem.getprevious()
                    if prev is not None:
                        prev.tail = (prev.tail or '') + elem.tail
                    else:
                        parent.text = (parent.text or '') + elem.tail
                parent.remove(elem)
            return

        computed = dict(inherited)
        for prop in _INHERITED:
            if prop in decl:
                computed[prop] = decl[prop].lower()
        if 'text-decoration-line' in decl:
            computed['text-decoration'] = decl['text-decoration-line'].lower()

        # Keep only the inline properties that are handled later, the rest
        # is expressed with markup below
        keep = {k: v for k, v in inline.items() if k in (
            'line-height', 'font-size', 'font-family', 'page-break-before',
            'page-break-after', 'break-before', 'break-after')}
        align = computed.get('text-align', '')
        if tag in _ALIGNABLE_TAGS and align in ('center', 'right', 'justify'):
            keep['text-align'] = align
        if keep:
            elem.set('style', '; '.join(f'{k}: {v}' for k, v in keep.items()))
        elif 'style' in elem.attrib:
            del elem.attrib['style']

        own = _TAG_FORMATTING.get(tag)
        if own:
            applied = applied | {own}
        is_block = tag in _BLOCK_TAGS
        has_block_children = is_block and any(_local(d.tag) in _BLOCK_TAGS for d in elem.iterdescendants())
        if not has_block_children and tag not in ('img', 'br', 'hr', 'table', 'tr', 'ul', 'ol', 'dl'):
            want = set()
            if _is_bold(computed.get('font-weight')):
                want.add('b')
            if computed.get('font-style') in ('italic', 'oblique'):
                want.add('i')
            deco = computed.get('text-decoration', '')
            if 'underline' in deco:
                want.add('u')
            if 'line-through' in deco:
                want.add('s')
            color = _css_color(computed['color']) if computed.get('color') else None
            if color and tag != 'a' and f'color:{color}' not in applied:
                want.add(f'color:{color}')
            va = decl.get('vertical-align', '').lower()
            if not is_block and va in ('super', 'sub') and tag not in ('sup', 'sub'):
                want.add(va[:3])
            new = want - applied
            if new and (elem.text or len(elem)):
                for fmt in sorted(new):
                    if fmt.startswith('color:'):
                        _wrap_content(elem, 'font', color=fmt[6:])
                    else:
                        _wrap_content(elem, fmt)
                applied = applied | new
        for child in list(elem):
            if isinstance(child.tag, str):
                walk(child, computed, applied)

    walk(body, {}, frozenset())
    return etree.tostring(root, encoding='unicode')


def _extract_inline_style_attrs(html_content):
    """
    Convert useful inline CSS styles to fpdf2-compatible HTML attributes.

    Extracts color, font-size, font-family, and text-align from style=""
    attributes and converts them to equivalent HTML attributes or <font> tags.
    """
    def _convert_style_to_attrs(match):
        full_tag = match.group(0)
        tag_name = match.group(1).lower()
        style_match = re.search(r'\bstyle="([^"]*)"', full_tag, re.IGNORECASE)
        if not style_match:
            return full_tag

        style = style_match.group(1)
        extra_attrs = ''

        align_m = re.search(r'text-align\s*:\s*(left|center|right|justify)', style, re.I)
        if align_m and tag_name in ('p', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            if not re.search(r'\balign=', full_tag, re.I):
                extra_attrs += f' align="{align_m.group(1)}"'

        lh_m = re.search(r'line-height\s*:\s*([\d.]+)', style, re.I)
        if lh_m and tag_name == 'p':
            if not re.search(r'\bline-height=', full_tag, re.I):
                extra_attrs += f' line-height="{lh_m.group(1)}"'

        break_m = re.search(r'break-(?:before|after)\s*:\s*page', style, re.I)
        if break_m:

            return full_tag

        if extra_attrs:

            result = re.sub(r'\s*style="[^"]*"', '', full_tag, flags=re.I)
            result = re.sub(r'>$', f'{extra_attrs}>', result)
            return result

        return re.sub(r'\s*style="[^"]*"', '', full_tag, flags=re.I)

    html_content = re.sub(
        r'<(p|div|td|th|h[1-6]|blockquote|tr)\b[^>]*style="[^"]*"[^>]*>',
        _convert_style_to_attrs, html_content, flags=re.IGNORECASE)

    return html_content

def _convert_span_styles_to_font(html_content):
    """
    Convert <span style="..."> to <font> tags where possible.

    fpdf2 supports <font color="" face="" size=""> but not <span>.
    Also converts bold/italic spans to <b>/<i> tags as matched pairs.
    """

    html_content = re.sub(
        r'<span\b[^>]*style="[^"]*font-weight\s*:\s*bold[^"]*"[^>]*>(.*?)</span>',
        r'<b>\1</b>', html_content, flags=re.DOTALL | re.IGNORECASE)

    html_content = re.sub(
        r'<span\b[^>]*style="[^"]*font-style\s*:\s*italic[^"]*"[^>]*>(.*?)</span>',
        r'<i>\1</i>', html_content, flags=re.DOTALL | re.IGNORECASE)

    def _span_to_font(match):
        attrs = match.group(1)
        style_m = re.search(r'style="([^"]*)"', attrs, re.I)
        if not style_m:
            return ''  

        style = style_m.group(1)
        font_attrs = []

        color_m = re.search(r'(?:^|;)\s*color\s*:\s*(#[0-9a-fA-F]{3,6}|\w+)', style)
        if color_m:
            font_attrs.append(f'color="{color_m.group(1)}"')

        family_m = re.search(r'font-family\s*:\s*([^;]+)', style, re.I)
        if family_m:
            face = family_m.group(1).strip().strip("'\"").split(',')[0].strip()
            font_attrs.append(f'face="{face}"')

        size_m = re.search(r'font-size\s*:\s*([\d.]+)\s*(px|pt|em|rem)', style, re.I)
        if size_m:
            val = float(size_m.group(1))
            unit = size_m.group(2).lower()
            if unit == 'pt':
                pt = val
            elif unit == 'px':
                pt = val * 0.75
            elif unit in ('em', 'rem'):
                pt = val * 12
            else:
                pt = 12
            if pt <= 8:
                size = 1
            elif pt <= 10:
                size = 2
            elif pt <= 13:
                size = 3
            elif pt <= 16:
                size = 4
            elif pt <= 20:
                size = 5
            elif pt <= 28:
                size = 6
            else:
                size = 7
            font_attrs.append(f'size="{size}"')

        if font_attrs:
            return '<font ' + ' '.join(font_attrs) + '>'
        return ''

    html_content = re.sub(
        r'<span\b([^>]*)>', _span_to_font, html_content, flags=re.IGNORECASE)

    html_content = re.sub(r'</span>', '</font>', html_content, flags=re.IGNORECASE)

    return html_content

def _clean_html_for_fpdf2(html_content):
    """
    Clean and simplify HTML content for fpdf2's write_html() parser.

    fpdf2 supports these HTML elements:
      h1-h6, p, br, hr, b, i, s, u, font, center, a, pre, code,
      img, ol, ul, li, dl, dt, dd, sup, sub, table/thead/tfoot/tbody/tr/th/td,
      section, article, blockquote
    This function preserves supported elements and strips unsupported ones.
    """

    html_content = re.sub(r'<\?xml[^>]*\?>', '', html_content)
    html_content = re.sub(r'<!DOCTYPE[^>]*>', '', html_content, flags=re.IGNORECASE)

    html_content = re.sub(r'\s+xmlns(?::[a-z]+)?="[^"]*"', '', html_content)

    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content,
                           re.DOTALL | re.IGNORECASE)
    if body_match:
        html_content = body_match.group(1)

    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content,
                          flags=re.DOTALL | re.IGNORECASE)

    html_content = re.sub(r'<head[^>]*>.*?</head>', '', html_content,
                          flags=re.DOTALL | re.IGNORECASE)

    html_content = re.sub(r'<svg[^>]*>.*?</svg>', '', html_content,
                          flags=re.DOTALL | re.IGNORECASE)

    html_content = _extract_inline_style_attrs(html_content)

    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content,
                          flags=re.DOTALL | re.IGNORECASE)

    html_content = _convert_span_styles_to_font(html_content)

    def _div_to_p(match):
        attrs = match.group(1) or ''
        align_m = re.search(r'\balign="([^"]*)"', attrs, re.I)
        if align_m:
            return f'<p align="{align_m.group(1)}">'
        return '<p>'

    html_content = re.sub(r'<div\b([^>]*)>', _div_to_p, html_content,
                          flags=re.IGNORECASE)
    html_content = re.sub(r'</div>', '</p>', html_content, flags=re.IGNORECASE)

    html_content = re.sub(r'<span\b[^>]*>', '', html_content, flags=re.IGNORECASE)

    html_content = re.sub(
        r'\s+(?:class|id|data-[\w-]+|role|epub:type|xml:lang|lang|title)="[^"]*"',
        '', html_content, flags=re.IGNORECASE)

    def _strip_non_break_style(match):
        style = match.group(1)
        if 'break-before' in style or 'break-after' in style:
            return match.group(0)  
        return ''

    html_content = re.sub(r'\s*style="([^"]*)"', _strip_non_break_style,
                          html_content, flags=re.IGNORECASE)

    html_content = re.sub(r'<p[^>]*>\s*</p>', '', html_content, flags=re.IGNORECASE)

    html_content = re.sub(r'<(br|hr|img)([^>]*)/>', r'<\1\2>', html_content,
                          flags=re.IGNORECASE)

    html_content = re.sub(
        r'<p>\s*(<img[^>]*>)\s*</p>',
        r'<center>\1</center>',
        html_content, flags=re.IGNORECASE)

    html_content = re.sub(
        r'<a[^>]*\s+href="#[^"]*"[^>]*>(.*?)</a>', r'\1',
        html_content, flags=re.DOTALL | re.IGNORECASE)

    html_content = re.sub(
        r'<a\s+(?:name|id)="[^"]*"[^>]*>\s*</a>', '', html_content,
        flags=re.IGNORECASE)
    html_content = re.sub(
        r'<a\s+(?:name|id)="[^"]*"\s*/?\s*>', '', html_content,
        flags=re.IGNORECASE)

    html_content = re.sub(
        r'<a\b(?![^>]*\bhref=)[^>]*>(.*?)</a>', r'\1',
        html_content, flags=re.DOTALL | re.IGNORECASE)

    for tag in ['nav', 'aside', 'header', 'footer',
                'main', 'figure', 'figcaption', 'details', 'summary',
                'mark', 'time', 'abbr', 'cite', 'q', 'small',
                'ruby', 'rt', 'rp', 'bdi', 'bdo', 'wbr',
                'map', 'area', 'canvas', 'audio', 'video', 'source',
                'embed', 'object', 'param', 'iframe']:
        html_content = re.sub(
            rf'</?{tag}[^>]*>', '', html_content, flags=re.IGNORECASE)

    def _clean_table_cell(m):
        # fpdf2 renders the content of a cell as a single run of text: any
        # markup that splits the text (<br>, partial formatting, links) makes
        # it reject the whole document. Keep the text, and the formatting only
        # when it applies to the entire cell.
        open_tag, content, close_tag = m.group(1), m.group(2), m.group(3)
        text = re.sub(r'<br\b[^>]*>', ' ', content, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            return f'{open_tag}{close_tag}'
        wrappers = []
        inner = content.strip()
        while True:
            fm = re.match(r'^<(b|strong|i|em|u)\b[^>]*>(.*)</\1>$', inner, flags=re.DOTALL | re.IGNORECASE)
            if fm is None or re.search(rf'</{fm.group(1)}>', fm.group(2), flags=re.IGNORECASE):
                break
            wrappers.append({'strong': 'b', 'em': 'i'}.get(fm.group(1).lower(), fm.group(1).lower()))
            inner = fm.group(2).strip()
        for w in reversed(wrappers):
            text = f'<{w}>{text}</{w}>'
        return f'{open_tag}{text}{close_tag}'

    html_content = re.sub(r'(<ul\b[^>]*?)\s+type="[^"]*"', r'\1', html_content, flags=re.IGNORECASE)

    html_content = re.sub(
        r'(<t[dh][^>]*>)(.*?)(</t[dh]>)',
        _clean_table_cell, html_content, flags=re.DOTALL | re.IGNORECASE)

    # The PDF core fonts are used with the WinAnsi (windows-1252) encoding,
    # map the characters it does not contain to close equivalents
    _unicode_map = {
        '\u00a0': ' ',
        '\u2032': "\u0027", '\u2033': '"',
        '\u200b': '', '\u200c': '', '\u200d': '', '\u2060': '',
        '\ufeff': '',
        '\u2010': '-', '\u2011': '-', '\u2012': '\u2013',
        '\u2015': '\u2014',
        '\u2212': '-',
        '\u00ad': '',
        '\u2002': ' ', '\u2003': ' ', '\u2009': ' ', '\u202f': ' ', '\u2007': ' ', '\u2008': ' ',
        '\u2116': 'No.',
        '\u201b': '\u2018', '\u201f': '\u201c', '\u2024': '.', '\u2043': '-',
    }
    for uc, asc in _unicode_map.items():
        html_content = html_content.replace(uc, asc)

    cleaned = []
    for ch in html_content:
        try:
            ch.encode('cp1252')
            cleaned.append(ch)
        except UnicodeEncodeError:

            import unicodedata
            try:
                name = unicodedata.name(ch, '')

                if 'DASH' in name or 'HYPHEN' in name or 'MINUS' in name:
                    cleaned.append('-')
                elif 'SPACE' in name:
                    cleaned.append(' ')
                elif 'QUOTATION' in name:
                    cleaned.append('"' if 'DOUBLE' in name else "'")
                elif 'ARROW' in name:
                    cleaned.append('-')
                else:

                    decomposed = unicodedata.normalize('NFKD', ch)
                    ascii_chars = decomposed.encode('cp1252', 'ignore').decode('cp1252')
                    cleaned.append(ascii_chars if ascii_chars else '?')
            except Exception:
                cleaned.append('?')
    html_content = ''.join(cleaned)

    html_content = re.sub(r'\n\s*\n', '\n', html_content)
    html_content = html_content.strip()

    return html_content

def _parse_opf_spine(opf_path):
    """Parse OPF file and return ordered list of HTML file paths."""
    opf_dir = os.path.dirname(opf_path)
    tree = etree.parse(opf_path)
    root = tree.getroot()

    nsmap = {'opf': 'http://www.idpf.org/2007/opf'}

    manifest = {}
    for item in root.xpath('//opf:manifest/opf:item', namespaces=nsmap):
        item_id = item.get('id', '')
        href = item.get('href', '')
        media_type = item.get('media-type', '')
        manifest[item_id] = (href, media_type)

    if not manifest:
        for item in root.iter():
            if item.tag.endswith('}item') or item.tag == 'item':
                item_id = item.get('id', '')
                href = item.get('href', '')
                media_type = item.get('media-type', '')
                manifest[item_id] = (href, media_type)

    spine_ids = []
    for itemref in root.xpath('//opf:spine/opf:itemref', namespaces=nsmap):
        spine_ids.append(itemref.get('idref', ''))

    if not spine_ids:
        for itemref in root.iter():
            if itemref.tag.endswith('}itemref') or itemref.tag == 'itemref':
                spine_ids.append(itemref.get('idref', ''))

    html_files = []
    for sid in spine_ids:
        if sid in manifest:
            href, media_type = manifest[sid]
            fpath = os.path.join(opf_dir, href)
            if os.path.exists(fpath):
                html_files.append(fpath)

    if not html_files:
        for item_id, (href, media_type) in manifest.items():
            if 'html' in media_type or 'xhtml' in media_type:
                fpath = os.path.join(opf_dir, href)
                if os.path.exists(fpath):
                    html_files.append(fpath)

    return html_files

def _resolve_images(html_content, base_dir):
    """
    Convert relative image src paths to absolute paths so fpdf2 can find them.
    """
    def replace_src(match):
        prefix = match.group(1)
        src = match.group(2)
        if src.startswith(('http://', 'https://', 'data:', '/')):
            return match.group(0)
        abs_path = os.path.normpath(os.path.join(base_dir, src))
        if os.path.exists(abs_path):
            return f'{prefix}"{abs_path}"'
        return match.group(0)

    return re.sub(r'(<img[^>]*\ssrc=)"([^"]*)"', replace_src, html_content,
                  flags=re.IGNORECASE)

def convert(opf_path, opts, metadata=None, output_path=None,
            log=None, cover_data=None, report_progress=None):
    """
    Convert OEB content (referenced by OPF) to PDF using fpdf2.

    Args:
        opf_path:        Path to the OPF file
        opts:            Conversion options
        metadata:        Book metadata (title, authors, etc.)
        output_path:     Where to write the PDF
        log:             Logger
        cover_data:      Cover image bytes (or None)
        report_progress: Progress callback
    """
    from fpdf import FPDF

    if log:
        log.info('Converting to PDF using fpdf2...')

    page_w_mm, page_h_mm = _get_page_size_mm(opts)
    margin_l, margin_t, margin_r, margin_b = _get_margins_mm(opts)

    pdf = FPDF(unit='mm', format=(page_w_mm, page_h_mm))
    # The core fonts are embedded with WinAnsiEncoding, which gives access to
    # typographic quotes, dashes, ellipsis, etc. that latin-1 does not have
    pdf.core_fonts_encoding = 'windows-1252'
    pdf.set_margins(margin_l, margin_t, margin_r)
    pdf.set_auto_page_break(True, margin=margin_b)

    title = 'Unknown'
    author = 'Unknown'
    if metadata:
        if hasattr(metadata, 'title') and metadata.title:
            title = str(metadata.title)
        if hasattr(metadata, 'authors') and metadata.authors:
            from calibre.ebooks.metadata import authors_to_string
            author = authors_to_string(metadata.authors)

    pdf.set_title(title)
    pdf.set_author(author)
    if hasattr(metadata, 'tags') and metadata.tags:
        pdf.set_keywords(', '.join(metadata.tags))

    font_family = 'Helvetica'
    std_font = getattr(opts, 'pdf_standard_font', 'serif')
    if std_font == 'serif':
        font_family = 'Times'
    elif std_font == 'mono':
        font_family = 'Courier'

    font_size = getattr(opts, 'pdf_default_font_size', 20)
    if font_size:

        font_size = max(8, int(font_size * 0.75))

    tag_styles = _tag_styles(font_size)

    if cover_data:
        try:
            _add_cover_page(pdf, cover_data, page_w_mm, page_h_mm,
                            margin_l, margin_t,
                            getattr(opts, 'preserve_cover_aspect_ratio', False))
        except Exception as e:
            if log:
                log.warn(f'Failed to add cover image: {e}')

    html_files = _parse_opf_spine(opf_path)
    if not html_files and log:
        log.warn('No HTML files found in OPF spine')

    total = len(html_files)
    for idx, html_path in enumerate(html_files):
        if report_progress:
            report_progress(idx / max(total, 1), f'Processing page {idx + 1}/{total}')

        try:
            with open(html_path, 'rb') as f:
                raw = f.read()

            try:
                html_content = raw.decode('utf-8')
            except UnicodeDecodeError:
                html_content = raw.decode('latin-1')

            html_dir = os.path.dirname(html_path)
            avail_w_pt = (page_w_mm - margin_l - margin_r) * 72.0 / 25.4
            html_content = _apply_css_styles(html_content, html_dir)
            html_content = _inject_image_dimensions(
                html_content, html_dir, avail_w_pt)

            html_content = _clean_html_for_fpdf2(html_content)

            html_content = _resolve_images(html_content, html_dir)

            if not html_content.strip():
                continue

            if idx > 0 or cover_data:
                pdf.add_page()
            else:
                pdf.add_page()

            pdf.set_font(font_family, size=font_size)
            try:
                pdf.write_html(html_content, tag_styles=tag_styles, li_prefix_color=(0, 0, 0),
                               ul_bullet_char='\u2022')
            except Exception as e:
                if log:
                    log.warn(f'fpdf2 write_html failed for {os.path.basename(html_path)}: {e}')

                try:
                    pdf.add_page()
                except Exception:
                    pass
                _write_plain_text_fallback(pdf, html_content, font_family, font_size)

        except Exception as e:
            if log:
                log.warn(f'Error processing {html_path}: {e}')
            continue

    if getattr(opts, 'pdf_page_numbers', False):
        _add_page_numbers(pdf)

    if report_progress:
        report_progress(0.95, 'Writing PDF...')

    pdf.output(output_path)

    if log:
        file_size = os.path.getsize(output_path)
        log.info(f'PDF output: {file_size:,} bytes, {pdf.pages_count} pages')

    if report_progress:
        report_progress(1.0, 'Done')

def _tag_styles(font_size):
    '''
    Styles for fpdf2's HTML renderer matching the default stylesheet of web
    browsers (black bold headings sized relative to the base font), instead
    of the fpdf2 defaults (dark red headings and quotes).
    '''
    from fpdf.fonts import TextStyle
    scale = {'h1': 2.0, 'h2': 1.5, 'h3': 1.17, 'h4': 1.0, 'h5': 0.83, 'h6': 0.67}
    ans = {h: TextStyle(font_style='B', color='#000000', font_size_pt=round(font_size * k, 1))
           for h, k in scale.items()}
    ans['blockquote'] = TextStyle(color='#000000', t_margin=3, b_margin=3, l_margin=10)
    return ans

def _add_cover_page(pdf, cover_data, page_w_mm, page_h_mm,
                    margin_l, margin_t, preserve_aspect):
    """Add a cover image as the first page."""
    import io
    import tempfile

    pdf.add_page()

    suffix = '.jpg'  
    if cover_data[:4] == b'\x89PNG':
        suffix = '.png'
    elif cover_data[:4] == b'GIF8':
        suffix = '.gif'

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(cover_data)
        tmp_path = tmp.name

    try:
        usable_w = page_w_mm - margin_l * 2
        usable_h = page_h_mm - margin_t * 2

        if preserve_aspect:

            pdf.image(tmp_path, x=margin_l, y=margin_t,
                      w=usable_w, h=0, keep_aspect_ratio=True)
        else:

            pdf.image(tmp_path, x=margin_l, y=margin_t,
                      w=usable_w, h=usable_h)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

def _write_plain_text_fallback(pdf, html_content, font_family, font_size):
    """Fallback: strip all HTML tags and write as plain text."""
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = re.sub(r'\s+', ' ', text).strip()
    if text:
        pdf.set_font(font_family, size=font_size)
        pdf.multi_cell(w=0, h=font_size * 0.5, text=text)

def _add_page_numbers(pdf):
    """Add page numbers at the bottom of each page using aliases."""

    pdf.alias_nb_pages()
