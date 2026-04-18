"""
WASM-compatible font scanner stub.

Threading and filesystem scanning for fonts is not available in WASM.
"""

class NoFonts(Exception):
    pass

class FontScanner:
    """Stub font scanner for WASM - no system fonts available."""

    def __init__(self):
        self._fonts = []

    def start(self):
        pass

    def join(self, timeout=None):
        pass

    @property
    def is_alive(self):
        return False

    def scan(self):
        return []

    def fonts(self):
        return []

    def fonts_for_family(self, family):
        return []

    def legacy_fonts_for_family(self, family):
        return []

    def find_font_for_text(self, text, allowed_families=None):
        return None

    def get_font_data(self, font):
        return None

font_scanner = FontScanner()
