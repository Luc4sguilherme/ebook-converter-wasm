"""
WASM stub for calibre KEPUB output plugin.

Generates a standard EPUB via EPUBOutput and then post-processes it
to add Kobo-specific markup (CSS, body wrappers, koboSpan sentence
spans, and kobo.js). Uses string/regex processing instead of lxml
to avoid WASM C-stack overflows on deeply nested HTML trees.
"""
import os
import re
import zipfile

from calibre.customize.conversion import OptionRecommendation, OutputFormatPlugin

KOBO_CSS_ID = 'kobostylehacks'
KOBO_SPAN_STYLE_ID = 'koboSpanStyle'
OUTER_DIV_ID = 'book-columns'
INNER_DIV_ID = 'book-inner'
KOBO_SPAN_CLASS = 'koboSpan'
KOBO_CSS = 'div#book-inner { margin-top: 0; margin-bottom: 0; }'
KOBO_SPAN_CSS = '.koboSpan { -webkit-text-combine: inherit; }'

_SENTENCE_END = re.compile(
    r'(?<=[.!?\u2026\u3002\uff01\uff1f])'
    r'[\s\u00a0]+'
    r'(?=[A-Z\u00c0-\u024f\u0400-\u04ff\u4e00-\u9fff\u3040-\u30ff])',
    re.UNICODE,
)

_HEAD_CLOSE = re.compile(r'</head\s*>', re.IGNORECASE)
_BODY_OPEN = re.compile(r'(<body[^>]*>)', re.IGNORECASE | re.DOTALL)
_BODY_CLOSE = re.compile(r'</body\s*>', re.IGNORECASE)

_TEXT_RUN = re.compile(r'(?<=>)([^<]+)(?=<)')

KOBO_JS = b"""\
var gPosition = 0;
var gProgress = 0;
var gCurrentPage = 0;
var gPageCount = 0;
var gClientHeight = null;

function getPosition() { return gPosition; }
function getProgress() { return gProgress; }
function getPageCount() { return gPageCount; }
function getCurrentPage() { return gCurrentPage; }

function setupBookColumns() {
    var body = document.getElementsByTagName('body')[0].style;
    body.marginLeft = '0px !important';
    body.marginRight = '0px !important';
    body.marginTop = '0px !important';
    body.marginBottom = '0px !important';
    body.paddingTop = '0px !important';
    body.paddingBottom = '0px !important';
    body.webkitNbspMode = 'space';
    var bc = document.getElementById('book-columns').style;
    bc.width = (window.innerWidth * 2) + 'px !important';
    bc.height = window.innerHeight + 'px !important';
    bc.marginTop = '0px !important';
    bc.webkitColumnWidth = window.innerWidth + 'px !important';
    bc.webkitColumnGap = '0px !important';
    bc.overflow = 'none';
    bc.paddingTop = '0px !important';
    bc.paddingBottom = '0px !important';
    gCurrentPage = 1;
    gProgress = gPosition = 0;
    var bi = document.getElementById('book-inner').style;
    bi.marginLeft = '10px';
    bi.marginRight = '10px';
    bi.padding = '0';
    gPageCount = document.body.scrollWidth / window.innerWidth;
    if (gClientHeight < window.innerHeight) { gPageCount = 1; }
}

function paginate(tagId) {
    if (gClientHeight == undefined) {
        gClientHeight = document.getElementById('book-columns').clientHeight;
    }
    setupBookColumns();
    if (typeof window.device !== 'undefined') {
        window.device.reportPageCount(gPageCount);
        var tagIdPageNumber = 0;
        if (tagId.length > 0) {
            tagIdPageNumber = estimatePageNumberForAnchor(tagId);
        }
        window.device.finishedPagination(tagId, tagIdPageNumber);
    }
}

function goBack() {
    if (gCurrentPage > 1) {
        --gCurrentPage;
        gPosition -= window.innerWidth;
        window.scrollTo(gPosition, 0);
    }
}

function goForward() {
    if (gCurrentPage < gPageCount) {
        ++gCurrentPage;
        gPosition += window.innerWidth;
        window.scrollTo(gPosition, 0);
    }
}

function goPage(pageNumber) {
    if (pageNumber > 0 && pageNumber <= gPageCount) {
        gCurrentPage = pageNumber;
        gPosition = (gCurrentPage - 1) * window.innerWidth;
        window.scrollTo(gPosition, 0);
    }
}

function estimateFirstAnchorForPageNumber(page) {
    var spans = document.getElementsByTagName('span');
    var lastKoboSpanId = "";
    for (var i = 0; i < spans.length; i++) {
        if (spans[i].id.substr(0, 5) == "kobo.") {
            lastKoboSpanId = spans[i].id;
            if (spans[i].offsetTop >= (page * window.innerHeight)) {
                return spans[i].id;
            }
        }
    }
    return lastKoboSpanId;
}

function estimatePageNumberForAnchor(spanId) {
    var span = document.getElementById(spanId);
    if (span) { return Math.floor(span.offsetTop / window.innerHeight); }
    return 0;
}
"""

HTML_MEDIA_TYPES = frozenset((
    'application/xhtml+xml', 'text/html', 'application/html+xml',
))

def _add_kobo_spans_string(html):
    """Add koboSpan spans around text content using regex (no lxml).

    Operates only on body content, skipping text inside script/style/pre/svg/math.
    """
    paranum = [0]
    segnum = [0]

    skip_ranges = []
    for m in re.finditer(
        r'<(script|style|pre|code|svg|math)\b[^>]*>.*?</\1\s*>',
        html, re.IGNORECASE | re.DOTALL,
    ):
        skip_ranges.append((m.start(), m.end()))

    def in_skip_range(pos):
        for start, end in skip_ranges:
            if start <= pos < end:
                return True
        return False

    def replace_text_run(match):
        text = match.group(1)
        if not text.strip():
            return match.group(0)
        if in_skip_range(match.start()):
            return match.group(0)
        paranum[0] += 1
        segnum[0] = 0
        parts = _SENTENCE_END.split(text)
        spans = ''
        for part in parts:
            if part:
                segnum[0] += 1
                spans += f'<span class="{KOBO_SPAN_CLASS}" id="kobo.{paranum[0]}.{segnum[0]}">{part}</span>'
        return spans if spans else match.group(0)

    return _TEXT_RUN.sub(replace_text_run, html)

def _kepubify_html(raw_bytes, kobo_js_href='kobo.js'):
    """Add Kobo markup using string operations (no lxml — avoids WASM stack issues)."""
    text = raw_bytes.decode('utf-8', errors='replace')

    kobo_head = (
        f'<style type="text/css" id="{KOBO_CSS_ID}">{KOBO_CSS}</style>\n'
        f'<style type="text/css" id="{KOBO_SPAN_STYLE_ID}">{KOBO_SPAN_CSS}</style>\n'
        f'<script type="text/javascript" src="{kobo_js_href}"> </script>\n'
    )
    m = _HEAD_CLOSE.search(text)
    if m:
        text = text[:m.start()] + kobo_head + text[m.start():]

    text = _BODY_OPEN.sub(
        rf'\1<div id="{OUTER_DIV_ID}"><div id="{INNER_DIV_ID}">',
        text, count=1,
    )
    text = _BODY_CLOSE.sub(
        f'</div></div></body>',
        text, count=1,
    )

    text = _add_kobo_spans_string(text)

    return text.encode('utf-8')

def _is_html_file(filename):
    """Check if a filename looks like an HTML content document."""
    lower = filename.lower()
    return lower.endswith(('.xhtml', '.html', '.htm'))

def _get_opf_html_items(opf_data):
    """Parse OPF manifest to get HTML item hrefs and their media types."""
    html_items = set()
    try:
        text = opf_data.decode('utf-8', errors='replace')
        for m in re.finditer(r'<item\b([^>]*)/?>', text, re.IGNORECASE | re.DOTALL):
            attrs = m.group(1)
            mt_m = re.search(r'media-type\s*=\s*["\']([^"\']*)["\']', attrs)
            href_m = re.search(r'href\s*=\s*["\']([^"\']*)["\']', attrs)
            if href_m:
                mt = (mt_m.group(1) if mt_m else '').lower()
                href = href_m.group(1)
                if mt in HTML_MEDIA_TYPES or (not mt and _is_html_file(href)):
                    html_items.add(href)
    except Exception:
        pass
    return html_items

class KEPUBOutput(OutputFormatPlugin):

    name = 'KEPUB Output'
    author = 'ebook-converter-wasm'
    file_type = 'kepub'
    commit_name = 'kepub_output'

    options = {
        OptionRecommendation(
            name='dont_split_on_page_breaks',
            recommended_value=False,
            help='Do not split on page breaks.'),
        OptionRecommendation(
            name='flow_size', recommended_value=512,
            help='Split all HTML files larger than this size (in KB). '
                 'Set to 0 to disable size based splitting.'),
        OptionRecommendation(
            name='no_default_epub_cover',
            recommended_value=False,
            help='Do not insert a cover at the beginning.'),
        OptionRecommendation(
            name='preserve_cover_aspect_ratio',
            recommended_value=True,
            help='Preserve the aspect ratio of the cover.'),
    }

    recommendations = set()

    def convert(self, oeb, output_path, input_plugin, opts, log):
        from calibre.customize.ui import plugin_for_output_format

        epub_output = plugin_for_output_format('epub')
        if epub_output is None:
            raise ValueError('EPUB output plugin not available (needed for KEPUB)')

        user_dont_split = getattr(opts, 'dont_split_on_page_breaks', False)
        user_flow_size = getattr(opts, 'flow_size', 512)

        for opt in epub_output.options:
            setattr(opts, opt.option.name, opt.recommended_value)
        opts.dont_split_on_page_breaks = user_dont_split
        opts.flow_size = user_flow_size
        opts.preserve_cover_aspect_ratio = True

        tmp_epub = output_path + '.epub.tmp'
        try:
            epub_output.convert(oeb, tmp_epub, input_plugin, opts, log)
            log.info('Adding Kobo markup...')
            self._kepubify_epub(tmp_epub, output_path, log)
        finally:
            if os.path.exists(tmp_epub):
                os.remove(tmp_epub)

    def _kepubify_epub(self, epub_path, output_path, log):
        """Post-process EPUB file to add Kobo-specific markup."""

        opf_html_items = set()
        opf_dir = ''

        with zipfile.ZipFile(epub_path, 'r') as zin:

            for name in zin.namelist():
                if name.lower().endswith('.opf'):
                    opf_data = zin.read(name)
                    opf_dir = name.rsplit('/', 1)[0] + '/' if '/' in name else ''
                    opf_html_items = _get_opf_html_items(opf_data)
                    break

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                kobo_js_added = False
                kobo_js_path = opf_dir + 'kobo.js'

                for item in zin.infolist():
                    data = zin.read(item.filename)

                    if opf_dir and item.filename.startswith(opf_dir):
                        rel_name = item.filename[len(opf_dir):]
                    else:
                        rel_name = item.filename

                    is_html = (rel_name in opf_html_items or
                               item.filename in opf_html_items or
                               _is_html_file(item.filename))

                    if is_html and not item.filename.endswith('.opf'):
                        try:

                            depth = item.filename.count('/') - kobo_js_path.count('/')
                            if depth > 0:
                                js_href = '../' * depth + 'kobo.js'
                            else:
                                js_href = 'kobo.js'

                            data = _kepubify_html(data, js_href)
                        except Exception as e:
                            log.warn(f'Failed to kepubify {item.filename}: {e}')

                    zout.writestr(item, data)

                if not kobo_js_added:
                    zout.writestr(kobo_js_path, KOBO_JS)
