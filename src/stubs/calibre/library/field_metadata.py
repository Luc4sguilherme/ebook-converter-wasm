"""Minimal WASM stub for calibre.library.field_metadata"""

class FieldMetadata(dict):
    """Dict-like metadata schema used by calibre Metadata class."""

    def __init__(self):
        super().__init__({
            'title': {'kind': 'field'},
            'authors': {'kind': 'field'},
            'tags': {'kind': 'field'},
            'series': {'kind': 'field'},
            'series_index': {'kind': 'field'},
            'publisher': {'kind': 'field'},
            'rating': {'kind': 'field'},
            'comments': {'kind': 'field'},
            'language': {'kind': 'field'},
            'languages': {'kind': 'field'},
            'pubdate': {'kind': 'field'},
            'timestamp': {'kind': 'field'},
            'identifiers': {'kind': 'field'},
            'isbn': {'kind': 'field'},
            'cover': {'kind': 'field'},
        })

    def __contains__(self, key):
        return dict.__contains__(self, key)

    def __iter__(self):
        return dict.__iter__(self)
