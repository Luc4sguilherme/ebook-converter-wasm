"""Stub for calibre_extensions.imageops"""

def load_from_data_without_gil(data):
    """Load image from raw data. In WASM, use PIL."""
    from PIL import Image
    import io
    return Image.open(io.BytesIO(data))
