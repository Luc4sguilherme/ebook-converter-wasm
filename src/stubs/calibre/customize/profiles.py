"""Minimal WASM stub for calibre.customize.profiles"""

FONT_SIZES = [('xx-small', 1),
              ('x-small',  None),
              ('small',    2),
              ('medium',   3),
              ('large',    4),
              ('x-large',  5),
              ('xx-large', 6),
              (None,       7)]

class InputProfile:
    name = 'Default Input Profile'
    short_name = 'default'
    description = 'Default input profile for WASM'
    author = 'ebook-converter-wasm'
    supported_platforms = {'windows', 'osx', 'linux'}
    can_be_disabled = False
    type = 'Input profile'
    screen_size = (1600, 1200)
    dpi = 100
    fbase = 12
    fsizes = [5, 7, 9, 12, 13.5, 17, 20, 22, 24]
    fkey = []
    fnames = {}
    fnums = {}
    supports_mobi_indexing = False
    touchscreen = False
    comic_screen_size = (584, 754)
    width_pts = 1600 * 72.0 / 100
    height_pts = 1200 * 72.0 / 100

    def __init__(self, *args, **kwargs):
        self.width, self.height = self.screen_size
        self.fkey = list(self.fsizes)
        fsizes = list(self.fsizes)
        self.fsizes = []
        for (name, num), size in zip(FONT_SIZES, fsizes):
            self.fsizes.append((name, num, float(size)))
        self.fnames = {name: sz for name, _, sz in self.fsizes if name}
        self.fnums = {num: sz for _, num, sz in self.fsizes if num}

class OutputProfile:
    name = 'Default Output Profile'
    short_name = 'default'
    description = 'Default output profile for WASM'
    author = 'ebook-converter-wasm'
    supported_platforms = {'windows', 'osx', 'linux'}
    can_be_disabled = False
    type = 'Output profile'
    screen_size = (1600, 1200)
    dpi = 100
    fbase = 12
    fsizes = [5, 7, 9, 12, 13.5, 17, 20, 22, 24]
    fkey = []
    fnames = {}
    fnums = {}
    supports_mobi_indexing = False
    touchscreen = False
    touchscreen_news_css = ''
    comic_screen_size = (584, 754)
    extra_css_modules = []
    periodical_date_in_title = True
    ratings_char = '*'
    empty_ratings_char = ' '
    unsupported_unicode_chars = []
    mobi_ems_per_blockquote = 1.0
    epub_periodical_format = None
    width_pts = 1600 * 72.0 / 100
    height_pts = 1200 * 72.0 / 100
    minimum_font_size = 0

    def __init__(self, *args, **kwargs):
        self.width, self.height = self.screen_size
        self.fkey = list(self.fsizes)
        fsizes = list(self.fsizes)
        self.fsizes = []
        for (name, num), size in zip(FONT_SIZES, fsizes):
            self.fsizes.append((name, num, float(size)))
        self.fnames = {name: sz for name, _, sz in self.fsizes if name}
        self.fnums = {num: sz for _, num, sz in self.fsizes if num}

input_profiles = [InputProfile()]
output_profiles = [OutputProfile()]

class HanlinV3Output(OutputProfile):
    name = 'Hanlin V3 Output'
    short_name = 'hanlinv3'
    screen_size = (584, 754)

class HanlinV5Output(OutputProfile):
    name = 'Hanlin V5 Output'
    short_name = 'hanlinv5'
    screen_size = (584, 754)

class SonyReaderOutput(OutputProfile):
    name = 'Sony Reader Output'
    short_name = 'sony'
    screen_size = (590, 775)

class KindleOutput(OutputProfile):
    name = 'Kindle Output'
    short_name = 'kindle'
    screen_size = (525, 640)
    supports_mobi_indexing = True
    mobi_ems_per_blockquote = 2.0

class KindleDXOutput(KindleOutput):
    name = 'Kindle DX Output'
    short_name = 'kindle_dx'
    screen_size = (744, 1022)

class KindleFireOutput(KindleOutput):
    name = 'Kindle Fire Output'
    short_name = 'kindle_fire'
    screen_size = (570, 1016)

