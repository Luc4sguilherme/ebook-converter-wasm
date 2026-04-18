"""
WASM stub for calibre.ebooks.covers

Generates simple cover images using PIL/Pillow instead of Qt.
"""
import random
from io import BytesIO

COVER_WIDTH = 1200
COVER_HEIGHT = 1600

COLOR_THEMES = [
    ((232, 217, 172), (56, 45, 26)),    
    ((216, 237, 181), (24, 49, 40)),     
    ((211, 220, 242), (0, 48, 90)),      
    ((230, 241, 245), (59, 62, 64)),     
]

def create_cover(title, authors, series=None, series_index=1, prefs=None, as_qimage=False):
    """Create a cover image from title, authors, and optional series info.

    Returns JPEG image data as bytes.
    """
    from PIL import Image, ImageDraw

    width = COVER_WIDTH
    height = COVER_HEIGHT

    bg_color, text_color = random.choice(COLOR_THEMES)

    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    band_top = height // 3
    band_bottom = band_top + height // 3
    band_color = tuple(max(0, c - 40) for c in bg_color)
    draw.rectangle([0, band_top, width, band_bottom], fill=band_color)

    font_title = None
    font_author = None
    try:
        from PIL import ImageFont
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", 72)
        font_author = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", 48)
    except Exception:
        try:
            from PIL import ImageFont
            font_title = ImageFont.load_default(size=72)
            font_author = ImageFont.load_default(size=48)
        except Exception:
            pass

    title_y = band_top + 40
    _draw_centered_text(draw, title or 'Unknown', width, title_y, text_color, font_title)

    if authors:
        author_text = ' & '.join(a for a in authors if a)
        author_y = band_top + 160
        _draw_centered_text(draw, author_text, width, author_y, text_color, font_author)

    if series:
        series_text = f'{series} #{series_index}'
        series_y = band_bottom + 40
        _draw_centered_text(draw, series_text, width, series_y, text_color, font_author)

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()

def generate_cover(mi, prefs=None, as_qimage=False):
    """Generate a cover from a Metadata object."""
    title = str(mi.title) if mi.title else 'Unknown'
    authors = list(mi.authors) if mi.authors else ['Unknown']
    series = str(mi.series) if mi.series else None
    series_index = mi.series_index if mi.series_index else 1
    return create_cover(title, authors, series, series_index, prefs=prefs, as_qimage=as_qimage)

def generate_masthead(title, output_path=None, width=600, height=60, as_qimage=False, font_family=None):
    """Generate a masthead image for periodicals."""
    from PIL import Image, ImageDraw

    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    font = None
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", int(height * 0.75))
    except Exception:
        try:
            from PIL import ImageFont
            font = ImageFont.load_default(size=int(height * 0.75))
        except Exception:
            pass

    _draw_centered_text(draw, title or '', width, height // 8, (0, 0, 0), font)

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=85)
    data = buf.getvalue()

    if output_path is not None:
        with open(output_path, 'wb') as f:
            f.write(data)
        return None
    return data

def calibre_cover2(title, author_string='', series_string='', prefs=None, as_qimage=False, logo_path=None):
    """Simplified cover generation for calibre branding."""
    authors = [author_string] if author_string else []
    return create_cover(title, authors, series=series_string if series_string else None)

def message_image(text, width=500, height=400, font_size=20):
    """Generate a simple image with text."""
    from PIL import Image, ImageDraw

    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    _draw_centered_text(draw, text, width, height // 3, (0, 0, 0), None)

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()

def _draw_centered_text(draw, text, img_width, y, color, font):
    """Draw text centered horizontally on the image."""
    if not text:
        return
    kwargs = {'fill': color}
    if font is not None:
        kwargs['font'] = font
    bbox = draw.textbbox((0, 0), text, **({k: v for k, v in kwargs.items() if k == 'font'}))
    text_width = bbox[2] - bbox[0]
    x = max(10, (img_width - text_width) // 2)

    if text_width > img_width - 20:
        while len(text) > 3:
            text = text[:-1]
            bbox = draw.textbbox((0, 0), text + '...', **({k: v for k, v in kwargs.items() if k == 'font'}))
            text_width = bbox[2] - bbox[0]
            if text_width <= img_width - 20:
                text = text + '...'
                break
        x = 10
    draw.text((x, y), text, **kwargs)
