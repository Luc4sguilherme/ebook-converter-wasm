"""
WASM replacement for image utilities that normally depend on Qt.
Uses PIL/Pillow if available in Pyodide, otherwise basic stubs.
"""

def image_from_data(data):
    """Load image from bytes."""
    try:
        from PIL import Image
        import io
        return Image.open(io.BytesIO(data))
    except ImportError:
        return None

def image_to_data(img, fmt='PNG'):
    """Convert image to bytes."""
    try:
        from PIL import Image
        import io
        buf = io.BytesIO()
        if isinstance(img, Image.Image):
            img.save(buf, format=fmt)
            return buf.getvalue()
    except ImportError:
        pass
    return b''

def scale_image(data, width=0, height=0):
    """Scale image data to fit within width/height."""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        if width and height:
            img.thumbnail((width, height), Image.LANCZOS)
        elif width:
            ratio = width / img.width
            img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
        elif height:
            ratio = height / img.height
            img = img.resize((int(img.width * ratio), height), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue(), img.width, img.height
    except ImportError:
        return data, 0, 0
