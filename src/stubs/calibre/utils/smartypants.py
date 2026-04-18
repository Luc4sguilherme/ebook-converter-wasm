"""
SmartyPants — smart typographic punctuation for HTML.

Converts ASCII quotes, dashes, and ellipses to their typographically
correct HTML entity equivalents.

Based on smartypants.py by Chad Miller, ported from SmartyPants by John Gruber.
"""
import re

tags_to_skip_regex = re.compile(r"<(/)?(style|pre|code|kbd|script|math)[^>]*>", re.I)
self_closing_regex = re.compile(r'/\s*>$')

def parse_attr(attr):
    do_dashes = do_backticks = do_quotes = do_ellipses = do_stupefy = 0

    if attr == "1":
        do_quotes = do_backticks = do_dashes = do_ellipses = 1
    elif attr == "2":
        do_quotes = do_backticks = do_ellipses = 1
        do_dashes = 2
    elif attr == "3":
        do_quotes = do_backticks = do_ellipses = 1
        do_dashes = 3
    elif attr == "-1":
        do_stupefy = 1
    else:
        for c in attr:
            if c == "q": do_quotes = 1
            elif c == "b": do_backticks = 1
            elif c == "B": do_backticks = 2
            elif c == "d": do_dashes = 1
            elif c == "D": do_dashes = 2
            elif c == "i": do_dashes = 3
            elif c == "e": do_ellipses = 1
    return do_dashes, do_backticks, do_quotes, do_ellipses, do_stupefy

def smartyPants(text, attr='1'):
    if attr == "0":
        return text

    do_dashes, do_backticks, do_quotes, do_ellipses, do_stupefy = parse_attr(attr)
    dashes_func = {1: educateDashes, 2: educateDashesOldSchool, 3: educateDashesOldSchoolInverted}.get(do_dashes, lambda x: x)
    backticks_func = {1: educateBackticks, 2: lambda x: educateSingleBackticks(educateBackticks(x))}.get(do_backticks, lambda x: x)
    ellipses_func = {1: educateEllipses}.get(do_ellipses, lambda x: x)
    stupefy_func = {1: stupefyEntities}.get(do_stupefy, lambda x: x)
    skipped_tag_stack = []
    tokens = _tokenize(text)
    result = []
    in_pre = False
    prev_token_last_char = ""

    for cur_token in tokens:
        if cur_token[0] == "tag":
            result.append(cur_token[1])
            skip_match = tags_to_skip_regex.match(cur_token[1])
            if skip_match is not None:
                is_self_closing = self_closing_regex.search(skip_match.group()) is not None
                if not is_self_closing:
                    if not skip_match.group(1):
                        skipped_tag_stack.append(skip_match.group(2).lower())
                        in_pre = True
                    else:
                        if len(skipped_tag_stack) > 0:
                            if skip_match.group(2).lower() == skipped_tag_stack[-1]:
                                skipped_tag_stack.pop()
                        if len(skipped_tag_stack) == 0:
                            in_pre = False
        else:
            t = cur_token[1]
            last_char = t[-1:]
            if not in_pre:
                t = processEscapes(t)
                t = re.sub('&quot;', '"', t)
                t = dashes_func(t)
                t = ellipses_func(t)
                t = backticks_func(t)

                if do_quotes != 0:
                    if t == "'":
                        if re.match(r"\S", prev_token_last_char):
                            t = "&#8217;"
                        else:
                            t = "&#8216;"
                    elif t == '"':
                        if re.match(r"\S", prev_token_last_char):
                            t = "&#8221;"
                        else:
                            t = "&#8220;"
                    else:
                        t = educateQuotes(t)

                t = stupefy_func(t)

            prev_token_last_char = last_char
            result.append(t)

    return "".join(result)

def educateQuotes(text):
    punct_class = r"""[!"#\$\%'()*+,-.\/:;<=>?\@\[\\\]\^_`{|}~]"""

    text = re.sub(r"""^'(?=%s\\B)""" % (punct_class,), r"""&#8217;""", text)
    text = re.sub(r"""^"(?=%s\\B)""" % (punct_class,), r"""&#8221;""", text)

    text = re.sub(r""""'(?=\w)""", """&#8220;&#8216;""", text)
    text = re.sub(r"""'"(?=\w)""", """&#8216;&#8220;""", text)
    text = re.sub(r'''""(?=\w)''', """&#8220;&#8220;""", text)
    text = re.sub(r"""''(?=\w)""", """&#8216;&#8216;""", text)
    text = re.sub(r'''\"\'''', """&#8221;&#8217;""", text)
    text = re.sub(r'''\'\"''', """&#8217;&#8221;""", text)
    text = re.sub(r'''""''', """&#8221;&#8221;""", text)
    text = re.sub(r"""''""", """&#8217;&#8217;""", text)

    text = re.sub(r"""(\W|^)'(?=\d{2}s)""", r"""\1&#8217;""", text)

    text = re.sub(r'''(\W|^)([-0-9.]+\s*)'(\s*[-0-9.]+)"''', r'\1\2&#8242;\3&#8243;', text)

    text = re.sub(r"""(?<=\W)"(?=\w)""", r"""&#8220;""", text)
    text = re.sub(r"""(?<=\W)'(?=\w)""", r"""&#8216;""", text)
    text = re.sub(r"""(?<=\w)"(?=\W)""", r"""&#8221;""", text)
    text = re.sub(r"""(?<=\w)'(?=\W)""", r"""&#8217;""", text)

    close_class = r"""[^\ \t\r\n\[\{\(\-]"""
    dec_dashes = r"""&#8211;|&#8212;"""

    opening_single_quotes_regex = re.compile(r"""
            (
                \s          |   # a whitespace char, or
                &nbsp;      |   # a non-breaking space entity, or
                --          |   # dashes, or
                &[mn]dash;  |   # named dash entities
                %s          |   # or decimal entities
                &\#x201[34];    # or hex
            )
            '                 # the quote
            (?=\w)            # followed by a word character
            """ % (dec_dashes,), re.VERBOSE)
    text = opening_single_quotes_regex.sub(r"""\1&#8216;""", text)

    closing_single_quotes_regex = re.compile(r"""
            (%s)
            '
            (?!\s | s\b | \d)
            """ % (close_class,), re.VERBOSE)
    text = closing_single_quotes_regex.sub(r"""\1&#8217;""", text)

    closing_single_quotes_regex = re.compile(r"""
            (%s)
            '
            (\s | s\b)
            """ % (close_class,), re.VERBOSE)
    text = closing_single_quotes_regex.sub(r"""\1&#8217;\2""", text)

    text = re.sub(r"""'""", r"""&#8216;""", text)

    opening_double_quotes_regex = re.compile(r"""
            (
                \s          |   # a whitespace char, or
                &nbsp;      |   # a non-breaking space entity, or
                --          |   # dashes, or
                &[mn]dash;  |   # named dash entities
                %s          |   # or decimal entities
                &\#x201[34];    # or hex
            )
            "                 # the quote
            (?=\w)            # followed by a word character
            """ % (dec_dashes,), re.VERBOSE)
    text = opening_double_quotes_regex.sub(r"""\1&#8220;""", text)

    closing_double_quotes_regex = re.compile(r"""
            "
            (?=\s)
            """, re.VERBOSE)
    text = closing_double_quotes_regex.sub(r"""&#8221;""", text)

    closing_double_quotes_regex = re.compile(r"""
            (%s)   # character that indicates the quote should be closing
            "
            """ % (close_class,), re.VERBOSE)
    text = closing_double_quotes_regex.sub(r"""\1&#8221;""", text)

    if text.endswith('-"'):
        text = text[:-1] + '&#8221;'

    text = re.sub(r'"', r"""&#8220;""", text)

    return text

def educateBackticks(text):
    text = re.sub(r"""``""", r"""&#8220;""", text)
    text = re.sub(r"""''""", r"""&#8221;""", text)
    return text

def educateSingleBackticks(text):
    text = re.sub(r"""`""", r"""&#8216;""", text)
    text = re.sub(r"""'""", r"""&#8217;""", text)
    return text

def educateDashes(text):
    text = re.sub(r"""---""", r"""&#8211;""", text)
    text = re.sub(r"""--""", r"""&#8212;""", text)
    return text

def educateDashesOldSchool(text):
    text = re.sub(r"""---""", r"""&#8212;""", text)
    text = re.sub(r"""--""", r"""&#8211;""", text)
    return text

def educateDashesOldSchoolInverted(text):
    text = re.sub(r"""---""", r"""&#8211;""", text)
    text = re.sub(r"""--""", r"""&#8212;""", text)
    return text

def educateEllipses(text):
    text = re.sub(r"""\.\.\.""", r"""&#8230;""", text)
    text = re.sub(r"""\. \. \.""", r"""&#8230;""", text)
    return text

def stupefyEntities(text):
    text = re.sub(r"""&#8211;""", r"""-""", text)
    text = re.sub(r"""&#8212;""", r"""--""", text)
    text = re.sub(r"""&#8216;""", r"""'""", text)
    text = re.sub(r"""&#8217;""", r"""'""", text)
    text = re.sub(r"""&#8220;""", r'''"''', text)
    text = re.sub(r"""&#8221;""", r'''"''', text)
    text = re.sub(r"""&#8230;""", r"""...""", text)
    return text

def processEscapes(text):
    text = re.sub(r"""\\\\""", r"""&#92;""", text)
    text = re.sub(r'''\\"''', r"""&#34;""", text)
    text = re.sub(r"""\\'""", r"""&#39;""", text)
    text = re.sub(r"""\\\.""", r"""&#46;""", text)
    text = re.sub(r"""\\-""", r"""&#45;""", text)
    text = re.sub(r"""\\`""", r"""&#96;""", text)
    return text

def _tokenize(html):
    tokens = []
    tag_soup = re.compile(r"""([^<]*)(<[^>]*>)""")
    token_match = tag_soup.search(html)
    previous_end = 0
    while token_match is not None:
        if token_match.group(1):
            tokens.append(['text', token_match.group(1)])
        tokens.append(['tag', token_match.group(2)])
        previous_end = token_match.end()
        token_match = tag_soup.search(html, token_match.end())
    if previous_end < len(html):
        tokens.append(['text', html[previous_end:]])
    return tokens

def run_tests(return_tests=False):
    import unittest
    sp = smartyPants

    class TestSmartypantsAllAttributes(unittest.TestCase):
        def test_dates(self):
            self.assertEqual(sp("one two '60s"), "one two &#8217;60s")
            self.assertEqual(sp("1440-80's"), "1440-80&#8217;s")
            self.assertEqual(sp("1960s"), "1960s")
            self.assertEqual(sp("1960's"), "1960&#8217;s")

        def test_skip_tags(self):
            self.assertEqual(
                sp("""<script type="text/javascript">\nvar x = "test";\n</script>"""),
                """<script type="text/javascript">\nvar x = "test";\n</script>""")

        def test_educated_quotes(self):
            self.assertEqual(sp('"Isn\'t this fun?"'), '&#8220;Isn&#8217;t this fun?&#8221;')

    tests = unittest.defaultTestLoader.loadTestsFromTestCase(TestSmartypantsAllAttributes)
    if return_tests:
        return tests
    unittest.TextTestRunner(verbosity=4).run(tests)
