"""
WASM-compatible replacement for calibre.utils.img

Uses PIL/Pillow for all image operations. No Qt dependency.
"""
import math
import os
from io import BytesIO

def fit_image(width, height, pwidth, pheight):
    """Fit image in box of width pwidth and height pheight."""
    scaled = height > pheight or width > pwidth
    if height > pheight:
        corrf = pheight / float(height)
        width, height = math.floor(corrf * width), pheight
    if width > pwidth:
        corrf = pwidth / float(width)
        width, height = pwidth, math.floor(corrf * height)
    if height > pheight:
        corrf = pheight / float(height)
        width, height = math.floor(corrf * width), pheight
    return scaled, int(width), int(height)

class NotImage(ValueError):
    pass

class AnimatedGIF(ValueError):
    pass

def normalize_format_name(fmt):
    fmt = fmt.lower()
    if fmt == 'jpg':
        fmt = 'jpeg'
    return fmt

def image_from_data(data):
    """Load an image from bytes data using PIL."""
    try:
        from PIL import Image
        return Image.open(BytesIO(data))
    except Exception:
        return None

def image_to_data(img, fmt='PNG'):
    """Convert a PIL Image to bytes."""
    try:
        from PIL import Image
        if isinstance(img, Image.Image):
            buf = BytesIO()
            img.save(buf, format=fmt)
            return buf.getvalue()
    except Exception:
        pass
    return b''

def scale_image(data, width=0, height=0, compression_quality=70, as_png=False, preserve_aspect_ratio=True):
    """Scale image data."""
    try:
        from PIL import Image
        img = Image.open(BytesIO(data))
        if width and height:
            if preserve_aspect_ratio:
                img.thumbnail((width, height), Image.LANCZOS)
            else:
                img = img.resize((width, height), Image.LANCZOS)
        elif width:
            ratio = width / img.width
            img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
        elif height:
            ratio = height / img.height
            img = img.resize((int(img.width * ratio), height), Image.LANCZOS)
        buf = BytesIO()
        fmt = 'PNG' if as_png else 'JPEG'
        save_kwargs = {}
        if fmt == 'JPEG':
            save_kwargs['quality'] = compression_quality
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
        img.save(buf, format=fmt, **save_kwargs)
        return buf.getvalue(), img.width, img.height
    except Exception:
        return data, 0, 0

def png_data_to_gif_data(data):
    """Convert PNG bytes to GIF bytes."""
    from PIL import Image
    img = Image.open(BytesIO(data))
    buf = BytesIO()
    if img.mode in ('p', 'P'):
        transparency = img.info.get('transparency')
        if transparency is not None:
            img.save(buf, 'gif', transparency=transparency)
        else:
            img.save(buf, 'gif')
    elif img.mode in ('rgba', 'RGBA'):
        alpha = img.split()[3]
        mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
        img = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255)
        img.paste(255, mask)
        img.save(buf, 'gif', transparency=255)
    else:
        img = img.convert('P', palette=Image.ADAPTIVE)
        img.save(buf, 'gif')
    return buf.getvalue()

def gif_data_to_png_data(data, discard_animation=False):
    """Convert GIF bytes to PNG bytes."""
    from PIL import Image
    img = Image.open(BytesIO(data))
    if hasattr(img, 'is_animated') and img.is_animated and not discard_animation:
        raise AnimatedGIF()
    buf = BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()

def save_cover_data_to(data, path=None, bgcolor='#ffffff',
                       resize_to=None, compression_quality=90,
                       minify_to=None, grayscale=False, eink=False,
                       letterbox=False, letterbox_color='#ffffff',
                       data_fmt='jpeg'):
    """Save cover image data. Returns bytes if path is None."""
    try:
        from PIL import Image
        img = Image.open(BytesIO(data))

        if resize_to:
            img = img.resize(resize_to, Image.LANCZOS)
        if minify_to:
            img.thumbnail(minify_to, Image.LANCZOS)
        if grayscale:
            img = img.convert('L')

        fmt = normalize_format_name(data_fmt).upper()
        if fmt == 'JPEG' and img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        buf = BytesIO()
        save_kwargs = {}
        if fmt == 'JPEG':
            save_kwargs['quality'] = compression_quality
        img.save(buf, format=fmt, **save_kwargs)

        result = buf.getvalue()
        if path:
            with open(path, 'wb') as f:
                f.write(result)
        return result
    except Exception:
        if path:
            with open(path, 'wb') as f:
                f.write(data)
        return data

def resize_image(data, width, height):
    """Resize image data to exact dimensions."""
    try:
        from PIL import Image
        if isinstance(data, bytes):
            img = Image.open(BytesIO(data))
        else:
            img = data
        img = img.resize((width, height), Image.LANCZOS)
        if isinstance(data, bytes):
            buf = BytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue()
        return img
    except Exception:
        return data

def resize_to_fit(img, width, height):
    """Resize image to fit within width x height, preserving aspect ratio."""
    try:
        from PIL import Image
        if isinstance(img, bytes):
            img = Image.open(BytesIO(img))
        if not hasattr(img, 'width'):
            return img
        scaled, nw, nh = fit_image(img.width, img.height, width, height)
        if scaled:
            return img.resize((nw, nh), Image.LANCZOS)
        return img
    except Exception:
        return img

def clone_image(img):
    """Clone a PIL image."""
    try:
        return img.copy()
    except Exception:
        return img

def optimize_png(data):
    """No-op optimization in WASM."""
    return data

def optimize_jpeg(data):
    """No-op optimization in WASM."""
    return data

def encode_jpeg(data, quality=80):
    """Encode image data as JPEG."""
    try:
        from PIL import Image
        img = Image.open(BytesIO(data))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=quality)
        return buf.getvalue()
    except Exception:
        return data

def add_borders_to_image(data, left=0, top=0, right=0, bottom=0, border_color='#ffffff'):
    """Add borders to image."""
    try:
        from PIL import Image, ImageColor
        img = Image.open(BytesIO(data))
        color = ImageColor.getrgb(border_color)
        new_w = img.width + left + right
        new_h = img.height + top + bottom
        new_img = Image.new(img.mode, (new_w, new_h), color)
        new_img.paste(img, (left, top))
        buf = BytesIO()
        new_img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception:
        return data

def image_and_format_from_data(data):
    """Return (image, format_name) from data bytes."""
    try:
        from PIL import Image
        img = Image.open(BytesIO(data))
        return img, (img.format or 'png').lower()
    except Exception:
        return None, None

def get_exe_path(name):
    """Not available in WASM."""
    return name

def load_jxr_data(data):
    """JXR not supported in WASM."""
    raise NotImage('JPEG-XR not supported in WASM environment')

def null_image():
    """Return a 1x1 transparent PNG."""
    try:
        from PIL import Image
        return Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    except Exception:
        return None

def image_from_path(path):
    """Load image from file path."""
    try:
        from PIL import Image
        return Image.open(path)
    except Exception:
        return None

def image_from_x(x):
    """Load image from bytes or path."""
    if isinstance(x, (bytes, bytearray)):
        return image_from_data(x)
    return image_from_path(x)

def save_image(img, path, **kw):
    """Save PIL image to path."""
    try:
        img.save(path, **kw)
    except Exception:
        pass

def blend_on_canvas(img, width, height, bgcolor='#ffffff'):
    """Blend image onto a canvas."""
    try:
        from PIL import Image, ImageColor
        canvas = Image.new('RGB', (width, height), ImageColor.getrgb(bgcolor))
        if img.mode == 'RGBA':
            canvas.paste(img, (0, 0), img)
        else:
            canvas.paste(img, (0, 0))
        return canvas
    except Exception:
        return img

def blend_image(img, bgcolor='#ffffff'):
    """Blend image with background color."""
    try:
        from PIL import Image, ImageColor
        if img.mode != 'RGBA':
            return img
        canvas = Image.new('RGB', img.size, ImageColor.getrgb(bgcolor))
        canvas.paste(img, mask=img.split()[3])
        return canvas
    except Exception:
        return img

class Canvas:
    def __init__(self, width, height, bgcolor='#ffffff'):
        from PIL import Image, ImageColor
        self.img = Image.new('RGBA', (width, height), ImageColor.getrgb(bgcolor))

    def compose(self, img, x=0, y=0):
        try:
            if img.mode == 'RGBA':
                self.img.paste(img, (x, y), img)
            else:
                self.img.paste(img, (x, y))
        except Exception:
            pass

    def export(self, fmt='PNG', compression_quality=95):
        buf = BytesIO()
        self.img.save(buf, format=fmt)
        return buf.getvalue()

def create_canvas(width, height, bgcolor='#ffffff'):
    return Canvas(width, height, bgcolor)

def overlay_image(img, canvas=None, left=0, top=0):
    """Overlay image on canvas."""
    if canvas is None:
        return img
    try:
        canvas.compose(img, left, top)
        return canvas.img
    except Exception:
        return img

def texture_image(canvas, texture):
    """No-op in WASM."""
    return canvas

def crop_image(img, x, y, width, height):
    """Crop image."""
    try:
        return img.crop((x, y, x + width, y + height))
    except Exception:
        return img

def grayscale_image(img):
    """Convert to grayscale."""
    try:
        return img.convert('L')
    except Exception:
        return img

def set_image_opacity(img, alpha=0.5):
    """Set image opacity."""
    try:
        from PIL import Image
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        r, g, b, a = img.split()
        from PIL import ImageEnhance
        a = a.point(lambda x: int(x * alpha))
        return Image.merge('RGBA', (r, g, b, a))
    except Exception:
        return img

def flip_image(img, horizontal=False, vertical=False):
    """Flip image."""
    try:
        from PIL import Image
        if horizontal:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if vertical:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
    except Exception:
        pass
    return img

def image_has_transparent_pixels(img):
    """Check if image has transparency."""
    try:
        if img.mode == 'RGBA':
            return img.getextrema()[3][0] < 255
    except Exception:
        pass
    return False

def rotate_image(img, degrees):
    """Rotate image."""
    try:
        return img.rotate(degrees, expand=True)
    except Exception:
        return img

def gaussian_sharpen_image(img, radius=0, sigma=3, high_quality=True):
    """No-op in WASM."""
    return img

def gaussian_blur_image(img, radius=-1, sigma=3):
    """Blur image."""
    try:
        from PIL import ImageFilter
        return img.filter(ImageFilter.GaussianBlur(radius=max(1, sigma)))
    except Exception:
        return img

def despeckle_image(img):
    """No-op in WASM."""
    return img

def oil_paint_image(img, radius=-1, high_quality=True):
    """No-op in WASM."""
    return img

def normalize_image(img):
    """No-op in WASM."""
    return img

def quantize_image(img, max_colors=256, dither=True, palette=''):
    """Quantize image colors."""
    try:
        from PIL import Image
        method = Image.MEDIANCUT if dither else Image.FASTOCTREE
        return img.quantize(colors=max_colors, method=method)
    except Exception:
        return img

def eink_dither_image(img):
    """Convert to e-ink friendly."""
    return grayscale_image(img)

def remove_borders_from_image(img, fuzz=None):
    """No-op - border removal not supported in WASM."""
    return img

def run_optimizer(file_path, cmd, as_filter=False, input_data=None):
    """No-op in WASM."""
    if input_data is not None:
        return input_data
    return None
