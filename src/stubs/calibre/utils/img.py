#!/usr/bin/env python
# License: GPLv3 Copyright: 2015-2019, Kovid Goyal <kovid at kovidgoyal.net>
"""
WASM-compatible replacement for calibre.utils.img

calibre implements its image handling with Qt (QImage) and the imageops C++
extension, neither of which is available in WASM. This module provides the
same API and behavior on top of Pillow. Images are represented by the
QtImage class, a thin wrapper around a PIL image that implements the parts
of the QImage interface calibre code uses on the objects returned by this
module (width(), height(), isNull(), hasAlphaChannel(), ...).
"""

import os
from io import BytesIO

from calibre import fit_image
from calibre.utils.config_base import tweaks
from calibre.utils.imghdr import what


# Utilities {{{
class NotImage(ValueError):
    pass


class AnimatedGIF(ValueError):
    pass


def normalize_format_name(fmt):
    fmt = fmt.lower()
    if fmt == 'jpg':
        fmt = 'jpeg'
    return fmt


def get_exe_path(name):
    return name


def load_jxr_data(data):
    raise NotImage('JPEG-XR images are not supported')


def _pil():
    from PIL import Image
    return Image


def _smooth():
    Image = _pil()
    return getattr(Image, 'Resampling', Image).LANCZOS


def _color(c):
    from PIL import ImageColor
    if isinstance(c, (tuple, list)):
        return tuple(c)[:3]
    return ImageColor.getrgb(c or '#ffffff')[:3]


class QtImage:
    ''' Minimal QImage compatible wrapper around a PIL image '''

    __slots__ = ('pil',)

    def __init__(self, pil=None):
        self.pil = pil

    def width(self):
        return 0 if self.pil is None else self.pil.width

    def height(self):
        return 0 if self.pil is None else self.pil.height

    def size(self):
        return (self.width(), self.height())

    def isNull(self):
        return self.pil is None or self.pil.width < 1 or self.pil.height < 1

    def hasAlphaChannel(self):
        if self.pil is None:
            return False
        mode = self.pil.mode
        return mode in ('RGBA', 'LA', 'PA', 'RGBa', 'La') or (mode == 'P' and 'transparency' in self.pil.info)

    def allGray(self):
        if self.pil is None:
            return True
        mode = self.pil.mode
        if mode in ('1', 'L', 'LA', 'I', 'I;16', 'F'):
            return True
        rgb = self.pil.convert('RGB')
        r, g, b = rgb.split()
        from PIL import ImageChops
        return ImageChops.difference(r, g).getbbox() is None and ImageChops.difference(g, b).getbbox() is None

    def copy(self, x=0, y=0, w=None, h=None):
        if self.pil is None:
            return QtImage()
        if w is None:
            return QtImage(self.pil.copy())
        return QtImage(self.pil.crop((int(x), int(y), int(x + w), int(y + h))))

    def mirrored(self, horizontal=False, vertical=True):
        img = self.pil
        Image = _pil()
        T = getattr(Image, 'Transpose', Image)
        if horizontal:
            img = img.transpose(T.FLIP_LEFT_RIGHT)
        if vertical:
            img = img.transpose(T.FLIP_TOP_BOTTOM)
        return QtImage(img if img is not self.pil else img.copy())

    def scaled(self, width, height, *args):
        return QtImage(self.pil.resize((max(1, int(width)), max(1, int(height))), _smooth()))

    def __getattr__(self, name):
        # Give access to the PIL API for code that expects PIL images
        return getattr(object.__getattribute__(self, 'pil'), name)


def _normalize_mode(img):
    ''' Convert the image to one of the modes calibre code can work with, the
    equivalent of what Qt does when loading images. '''
    mode = img.mode
    if mode in ('1', 'L', 'LA', 'RGB', 'RGBA'):
        return img
    if mode == 'P':
        return img.convert('RGBA' if 'transparency' in img.info else 'RGB')
    if mode in ('PA', 'RGBa', 'La'):
        return img.convert('RGBA')
    if mode == 'CMYK':
        from PIL import ImageChops
        if img.format == 'JPEG' and img.info.get('adobe'):
            # Photoshop writes inverted CMYK JPEGs
            img = ImageChops.invert(img)
        return img.convert('RGB')
    if mode.startswith('I') or mode == 'F':
        return img.point(lambda i: i * (1 / 256)).convert('L')
    return img.convert('RGBA' if 'A' in mode else 'RGB')


def _as_pil(img):
    if isinstance(img, QtImage):
        return img.pil
    return image_from_data(img).pil
# }}}


# png <-> gif {{{

def png_data_to_gif_data(data):
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
        mask = Image.eval(alpha, lambda a: 255 if a <=128 else 0)
        img = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255)
        img.paste(255, mask)
        img.save(buf, 'gif', transparency=255)
    else:
        img = img.convert('P', palette=Image.ADAPTIVE)
        img.save(buf, 'gif')
    return buf.getvalue()


def gif_data_to_png_data(data, discard_animation=False):
    from PIL import Image
    img = Image.open(BytesIO(data))
    if getattr(img, 'is_animated', False) and not discard_animation:
        raise AnimatedGIF()
    buf = BytesIO()
    img.save(buf, 'png')
    return buf.getvalue()

# }}}


# Loading images {{{

def set_image_allocation_limit(size_in_mb=1024):
    Image = _pil()
    Image.MAX_IMAGE_PIXELS = int(size_in_mb * 1024 * 1024 // 4)


def null_image():
    ' Create an invalid image. For internal use. '
    return QtImage()


def _load(data):
    Image = _pil()
    img = Image.open(BytesIO(data))
    img.load()
    return img


def image_from_data(data):
    ' Create an image object from data, which should be a bytestring. '
    if isinstance(data, QtImage):
        return data
    Image = _pil()
    if isinstance(data, Image.Image):
        return QtImage(_normalize_mode(data))
    if isinstance(data, (bytearray, memoryview)):
        data = bytes(data)
    try:
        img = _load(data)
    except Exception as err:
        q = what(None, data)
        if q == 'jxr':
            return load_jxr_data(data)
        raise NotImage(f'Not a valid image (detected type: {q}). Error: {err}')
    return QtImage(_normalize_mode(img))


def image_from_path(path):
    ' Load an image from the specified path. '
    with open(path, 'rb') as f:
        return image_from_data(f.read())


def image_from_x(x):
    ' Create an image from a bytestring or a path or a file like object. '
    if isinstance(x, str):
        return image_from_path(x)
    if hasattr(x, 'read'):
        return image_from_data(x.read())
    if isinstance(x, (bytes, bytearray, memoryview, QtImage)):
        return image_from_data(x)
    if isinstance(x, _pil().Image):
        return image_from_data(x)
    raise TypeError(f'Unknown image src type: {type(x)}')


_PIL_FORMAT_NAMES = {'mpo': 'jpeg', 'jpeg2000': 'jp2'}


def image_and_format_from_data(data):
    ' Create an image object from the specified data which should be a bytestring and also return the format of the image '
    try:
        img = _load(bytes(data))
    except Exception:
        return QtImage(), (what(None, data) or '')
    fmt = (img.format or '').lower()
    fmt = _PIL_FORMAT_NAMES.get(fmt, fmt)
    return QtImage(_normalize_mode(img)), fmt
# }}}


# Saving images {{{

def image_to_data(img, compression_quality=95, fmt='JPEG', png_compression_level=9, jpeg_optimized=True, jpeg_progressive=False):
    '''
    Serialize image to bytestring in the specified format.

    :param compression_quality: is for JPEG and WEBP and goes from 0 to 100.
                                100 being lowest compression, highest image quality. For WEBP 100 means lossless.
    :param png_compression_level: is for PNG and goes from 0-9. 9 being highest compression.
    :param jpeg_optimized: Turns on the 'optimize' option for libjpeg which losslessly reduce file size
    :param jpeg_progressive: Turns on the 'progressive scan' option for libjpeg which allows JPEG images to be downloaded in streaming fashion
    '''
    img = image_from_data(img)
    if img.isNull():
        raise ValueError('Failed to export image as ' + fmt + ' with error: image is null')
    fmt = fmt.upper()
    if fmt == 'GIF':
        return png_data_to_gif_data(image_to_data(img, fmt='PNG', png_compression_level=1))
    pil = img.pil
    buf = BytesIO()
    kw = {}
    if fmt in ('JPG', 'JPEG'):
        fmt = 'JPEG'
        if img.hasAlphaChannel():
            pil = blend_image(img).pil
        if pil.mode not in ('L', 'RGB'):
            pil = pil.convert('RGB')
        kw = {'quality': max(0, min(100, int(compression_quality))), 'optimize': bool(jpeg_optimized),
              'progressive': bool(jpeg_progressive)}
    elif fmt == 'PNG':
        kw = {'compress_level': min(9, max(0, int(png_compression_level)))}
    elif fmt == 'WEBP':
        q = max(0, min(100, int(compression_quality)))
        kw = {'lossless': True, 'quality': 70} if q >= 100 else {'quality': q}
    elif fmt in ('BMP', 'PPM', 'PGM', 'PBM') and pil.mode not in ('1', 'L', 'RGB'):
        pil = blend_image(img).pil if img.hasAlphaChannel() else pil.convert('RGB')
    elif fmt in ('TIF',):
        fmt = 'TIFF'
    try:
        pil.save(buf, format=fmt, **kw)
    except Exception as err:
        raise ValueError(f'Failed to export image as {fmt} with error: {err}')
    return buf.getvalue()


def save_image(img, path, **kw):
    ''' Save image to the specified path. Image format is taken from the file
    extension. You can pass the same keyword arguments as for the
    `image_to_data()` function. '''
    fmt = path.rpartition('.')[-1]
    kw['fmt'] = kw.get('fmt', fmt)
    with open(path, 'wb') as f:
        f.write(image_to_data(image_from_data(img), **kw))


def save_cover_data_to(
    data, path=None,
    bgcolor='#ffffff',
    resize_to=None,
    compression_quality=90,
    minify_to=None,
    grayscale=False,
    eink=False,
    letterbox=False,
    letterbox_color='#000000',
    data_fmt='jpeg'
):
    '''
    Saves image in data to path, in the format specified by the path
    extension. Removes any transparency. If there is no transparency and no
    resize and the input and output image formats are the same, no changes are
    made.

    :param data: Image data as bytestring
    :param path: If None img data is returned, in JPEG format
    :param data_fmt: The fmt to return data in when path is None. Defaults to JPEG
    :param compression_quality: The quality of the image after compression.
        Number between 1 and 100. 1 means highest compression, 100 means no
        compression (lossless). When generating PNG this number is divided by 10
        for the png_compression_level.
    :param bgcolor: The color for transparent pixels. Must be specified in hex.
    :param resize_to: A tuple (width, height) or None for no resizing
    :param minify_to: A tuple (width, height) to specify maximum target size.
        The image will be resized to fit into this target size. If None the
        value from the tweak is used.
    :param grayscale: If True, the image is converted to grayscale,
        if that's not already the case.
    :param eink: If True, the image is dithered down to the 16 specific shades
        of gray of the eInk palette.
        Works best with formats that actually support color indexing (i.e., PNG)
    :param letterbox: If True, in addition to fit resize_to inside minify_to,
        the image will be letterboxed (i.e., centered on a black background).
    :param letterbox_color: If letterboxing is used, this is the background color
        used. The default is black.
    '''
    fmt = normalize_format_name(data_fmt if path is None else os.path.splitext(path)[1][1:])
    if isinstance(data, QtImage):
        img = data
        changed = True
    else:
        img, orig_fmt = image_and_format_from_data(data)
        if img.isNull():
            raise NotImage('Not a valid image')
        orig_fmt = normalize_format_name(orig_fmt)
        changed = fmt != orig_fmt
    if resize_to is not None:
        changed = True
        img = img.scaled(int(resize_to[0]), int(resize_to[1]))
    owidth, oheight = img.width(), img.height()
    if minify_to is None:
        nwidth, nheight = tweaks['maximum_cover_size']
        nwidth, nheight = max(1, nwidth), max(1, nheight)
    else:
        nwidth, nheight = minify_to

    if letterbox:
        img = blend_on_canvas(img, nwidth, nheight, bgcolor=letterbox_color)
        # Check if we were minified
        if oheight != nheight or owidth != nwidth:
            changed = True
    else:
        scaled, nwidth, nheight = fit_image(owidth, oheight, nwidth, nheight)
        if scaled:
            changed = True
            img = img.scaled(int(nwidth), int(nheight))
    if img.hasAlphaChannel():
        changed = True
        img = blend_image(img, bgcolor)
    if grayscale and not eink:
        if not img.allGray():
            changed = True
            img = grayscale_image(img)
    if eink:
        img = eink_dither_image(img)
        changed = True
    if path is None:
        return image_to_data(img, compression_quality, fmt, compression_quality // 10) if changed else data
    with open(path, 'wb') as f:
        f.write(image_to_data(img, compression_quality, fmt, compression_quality // 10) if changed else data)
# }}}


# Overlaying images {{{

def blend_on_canvas(img, width, height, bgcolor='#ffffff'):
    ' Blend the `img` onto a canvas with the specified background color and size '
    img = image_from_data(img)
    w, h = img.width(), img.height()
    scaled, nw, nh = fit_image(w, h, width, height)
    if scaled:
        img = img.scaled(int(nw), int(nh))
        w, h = nw, nh
    canvas = create_canvas(width, height, bgcolor)
    overlay_image(img, canvas, (width - w)//2, (height - h)//2)
    return canvas


class Canvas:

    def __init__(self, width, height, bgcolor='#ffffff'):
        self.img = create_canvas(width, height, bgcolor)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def compose(self, img, x=0, y=0):
        img = image_from_data(img)
        overlay_image(img, self.img, x, y)

    def export(self, fmt='JPEG', compression_quality=95):
        return image_to_data(self.img, compression_quality=compression_quality, fmt=fmt)


def create_canvas(width, height, bgcolor='#ffffff'):
    'Create a blank canvas of the specified size and color '
    Image = _pil()
    return QtImage(Image.new('RGB', (max(1, int(width)), max(1, int(height))), _color(bgcolor)))


def overlay_image(img, canvas=None, left=0, top=0):
    ' Overlay the `img` onto the canvas at the specified position '
    img = image_from_data(img)
    if canvas is None:
        canvas = create_canvas(img.width(), img.height(), '#ffffff')
    left, top = int(left), int(top)
    src = img.pil
    dest = canvas.pil
    if src.mode in ('RGBA', 'LA'):
        if dest.mode != 'RGBA':
            layer = src.convert('RGBA')
            dest.paste(layer, (left, top), layer)
        else:
            dest.alpha_composite(src.convert('RGBA'), (left, top))
    else:
        dest.paste(src.convert(dest.mode) if src.mode != dest.mode else src, (left, top))
    return canvas


def texture_image(canvas, texture):
    ' Repeatedly tile the image `texture` across and down the image `canvas` '
    canvas = image_from_data(canvas)
    if canvas.hasAlphaChannel():
        canvas = blend_image(canvas)
    texture = image_from_data(texture)
    tw, th = texture.width(), texture.height()
    for y in range(0, canvas.height(), th):
        for x in range(0, canvas.width(), tw):
            overlay_image(texture, canvas, x, y)
    return canvas


def blend_image(img, bgcolor='#ffffff'):
    ' Used to convert images that have semi-transparent pixels to opaque by blending with the specified color '
    img = image_from_data(img)
    canvas = create_canvas(img.width(), img.height(), bgcolor)
    overlay_image(img, canvas)
    return canvas
# }}}


# Image borders {{{

def add_borders_to_image(img, left=0, top=0, right=0, bottom=0, border_color='#ffffff'):
    img = image_from_data(img)
    if not (left > 0 or right > 0 or top > 0 or bottom > 0):
        return img
    canvas = create_canvas(img.width() + left + right, img.height() + top + bottom, border_color)
    overlay_image(img, canvas, left, top)
    return canvas


def remove_borders_from_image(img, fuzz=None):
    ''' Try to auto-detect and remove any borders from the image. Returns
    the image itself if no borders could be removed. `fuzz` is a measure of
    what colors are considered identical (must be a number between 0 and 255 in
    absolute intensity units). Default is from a tweak whose default value is 10. '''
    from PIL import Image, ImageChops
    fuzz = tweaks['cover_trim_fuzz_value'] if fuzz is None else fuzz
    img = image_from_data(img)
    if img.isNull():
        return img
    pil = img.pil.convert('RGB')
    bg = Image.new('RGB', pil.size, pil.getpixel((0, 0)))
    diff = ImageChops.difference(pil, bg).convert('L')
    threshold = int(max(0, fuzz))
    bbox = diff.point(lambda p: 255 if p > threshold else 0).getbbox()
    if not bbox or bbox == (0, 0) + pil.size:
        return img
    return QtImage(img.pil.crop(bbox))
# }}}


# Cropping/scaling of images {{{

def resize_image(img, width, height):
    return image_from_data(img).scaled(int(width), int(height))


def resize_to_fit(img, width, height):
    img = image_from_data(img)
    resize_needed, nw, nh = fit_image(img.width(), img.height(), width, height)
    if resize_needed:
        img = resize_image(img, nw, nh)
    return resize_needed, img


def clone_image(img):
    ''' Returns a copy of the image '''
    return image_from_data(img).copy()


def scale_image(data, width=60, height=80, compression_quality=70, as_png=False, preserve_aspect_ratio=True):
    ''' Scale an image, returning it as either JPEG or PNG data (bytestring).
    Transparency is alpha blended with white when converting to JPEG. '''
    img = image_from_data(data)
    if preserve_aspect_ratio:
        scaled, nwidth, nheight = fit_image(img.width(), img.height(), width, height)
        if scaled:
            img = img.scaled(int(nwidth), int(nheight))
    elif img.width() != width or img.height() != height:
        img = img.scaled(int(width), int(height))
    fmt = 'PNG' if as_png else 'JPEG'
    w, h = img.width(), img.height()
    return w, h, image_to_data(img, compression_quality=compression_quality, fmt=fmt)


def crop_image(img, x, y, width, height):
    '''
    Return the specified section of the image.

    :param x, y: The top left corner of the crop box
    :param width, height: The width and height of the crop box. Note that if
    the crop box exceeds the source images dimensions, width and height will be
    auto-truncated.
    '''
    img = image_from_data(img)
    width = min(width, img.width() - x)
    height = min(height, img.height() - y)
    return img.copy(int(x), int(y), int(width), int(height))

# }}}


# Image transformations {{{

def grayscale_image(img):
    img = image_from_data(img)
    if img.hasAlphaChannel():
        return QtImage(img.pil.convert('LA'))
    return QtImage(img.pil.convert('L'))


def set_image_opacity(img, alpha=0.5):
    ''' Change the opacity of `img`. Note that the alpha value is multiplied to
    any existing alpha values, so you cannot use this function to convert a
    semi-transparent image to an opaque one. For that use `blend_image()`. '''
    pil = image_from_data(img).pil.convert('RGBA')
    a = pil.getchannel('A').point(lambda x: int(x * alpha))
    pil.putalpha(a)
    return QtImage(pil)


def flip_image(img, horizontal=False, vertical=False):
    return image_from_data(img).mirrored(horizontal, vertical)


def image_has_transparent_pixels(img):
    ' Return True iff the image has at least one semi-transparent pixel '
    img = image_from_data(img)
    if img.isNull() or not img.hasAlphaChannel():
        return False
    return img.pil.convert('RGBA').getchannel('A').getextrema()[0] < 255


def rotate_image(img, degrees):
    # Positive angles rotate clockwise, like QTransform.rotate()
    Image = _pil()
    pil = image_from_data(img).pil
    return QtImage(pil.rotate(-degrees, resample=getattr(Image, 'Resampling', Image).BICUBIC, expand=True))


def gaussian_sharpen_image(img, radius=0, sigma=3, high_quality=True):
    from PIL import ImageFilter
    pil = image_from_data(img).pil
    return QtImage(pil.filter(ImageFilter.UnsharpMask(radius=max(radius, sigma), percent=150, threshold=0)))


def gaussian_blur_image(img, radius=-1, sigma=3):
    from PIL import ImageFilter
    pil = image_from_data(img).pil
    return QtImage(pil.filter(ImageFilter.GaussianBlur(radius=sigma)))


def despeckle_image(img):
    from PIL import ImageFilter
    pil = image_from_data(img).pil
    return QtImage(pil.filter(ImageFilter.MedianFilter(3)))


def oil_paint_image(img, radius=-1, high_quality=True):
    from PIL import ImageFilter
    pil = image_from_data(img).pil
    size = 2 * max(1, int(radius if radius > 0 else 2)) + 1
    return QtImage(pil.filter(ImageFilter.ModeFilter(size)))


def normalize_image(img):
    from PIL import ImageOps
    img = image_from_data(img)
    if img.hasAlphaChannel():
        img = blend_image(img)
    return QtImage(ImageOps.autocontrast(img.pil))


def quantize_image(img, max_colors=256, dither=True, palette=''):
    ''' Quantize the image to contain a maximum of `max_colors` colors. By
    default a palette is chosen automatically, if you want to use a fixed
    palette, then pass in a list of color names in the `palette` variable. If
    you, specify a palette `max_colors` is ignored. Note that it is possible
    for the actual number of colors used to be less than max_colors.

    :param max_colors: Max. number of colors in the auto-generated palette. Must be between 2 and 256.
    :param dither: Whether to use dithering or not. dithering is almost always a good thing.
    :param palette: Use a manually specified palette instead. For example: palette='red green blue #eee'
    '''
    from PIL import Image
    img = image_from_data(img)
    if img.hasAlphaChannel():
        img = blend_image(img)
    pil = img.pil.convert('RGB')
    if palette and isinstance(palette, (str, bytes)):
        if isinstance(palette, bytes):
            palette = palette.decode('utf-8')
        palette = palette.split()
    d = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    if palette:
        colors = [_color(x) for x in palette]
        pal = Image.new('P', (1, 1))
        flat = [c for rgb in colors for c in rgb]
        pal.putpalette(flat + flat[:3] * (256 - len(colors)))
        return QtImage(pil.quantize(palette=pal, dither=d))
    return QtImage(pil.quantize(colors=max(2, min(256, int(max_colors))), dither=d))


# 8x8 ordered dither threshold map, as used by ImageMagick's o8x8
_BAYER8 = (
    (0, 48, 12, 60, 3, 51, 15, 63),
    (32, 16, 44, 28, 35, 19, 47, 31),
    (8, 56, 4, 52, 11, 59, 7, 55),
    (40, 24, 36, 20, 43, 27, 39, 23),
    (2, 50, 14, 62, 1, 49, 13, 61),
    (34, 18, 46, 30, 33, 17, 45, 29),
    (10, 58, 6, 54, 9, 57, 5, 53),
    (42, 26, 38, 22, 41, 25, 37, 21),
)


def eink_dither_image(img):
    ''' Dither the source image down to the eInk palette of 16 shades of grey,
    using an ordered dither.

    NOTE: No need to call grayscale_image first, as this will inline a grayscaling pass if need be.

    Returns an image in grayscale (L) pixel format.
    '''
    from PIL import Image, ImageChops
    img = image_from_data(img)
    if img.hasAlphaChannel():
        img = blend_image(img)
    gray = img.pil.convert('L')
    # Each of the 16 levels spans 17 intensity units, add a per pixel
    # threshold offset from the dither matrix and truncate to the level
    tile = Image.new('L', (8, 8))
    tile.putdata([int(v * 17 / 64) for row in _BAYER8 for v in row])
    offsets = Image.new('L', gray.size)
    for y in range(0, gray.height, 8):
        for x in range(0, gray.width, 8):
            offsets.paste(tile, (x, y))
    return QtImage(ImageChops.add(gray, offsets).point(lambda p: (p // 17) * 17))

# }}}


# Optimization of images {{{
# calibre runs external tools (jpegtran, optipng, cjpeg, cwebp) for these.
# They are replaced by Pillow, the file is only replaced if the result is
# smaller. They return None on success or an error message.

def _replace_if_smaller(file_path, data):
    if data and len(data) < os.path.getsize(file_path):
        with open(file_path, 'wb') as f:
            f.write(data)


def run_optimizer(file_path, cmd, as_filter=False, input_data=None):
    return f'Running {cmd[0]} is not supported'


def optimize_jpeg(file_path):
    # jpegtran is lossless, Pillow cannot re-compress a JPEG without decoding
    # it, so leave the file as is.
    return None


def optimize_png(file_path, level=7):
    ' level goes from 1 to 7 with 7 being maximum compression '
    try:
        with open(file_path, 'rb') as f:
            img = _pil().open(BytesIO(f.read()))
            img.load()
        buf = BytesIO()
        img.save(buf, format='PNG', optimize=True)
        _replace_if_smaller(file_path, buf.getvalue())
    except Exception as err:
        return str(err)


def optimize_webp(file_path, q=100, m=6, metadata='all'):
    ' metadata can be a comma seaprated list of all, none, exif, icc, xmp '
    return encode_webp(file_path, q, m, metadata, lossless=True)


def encode_jpeg(file_path, quality=80):
    quality = max(0, min(100, int(quality)))
    try:
        with open(file_path, 'rb') as f:
            img = image_from_data(f.read())
        _replace_if_smaller(file_path, image_to_data(img, compression_quality=quality, fmt='JPEG', jpeg_progressive=True))
    except Exception as err:
        return str(err)


def encode_webp(file_path, quality=75, m=6, metadata='all', lossless=False):
    try:
        with open(file_path, 'rb') as f:
            img = image_from_data(f.read())
        buf = BytesIO()
        img.pil.save(buf, format='WEBP', quality=max(0, min(int(quality), 100)), method=max(0, min(int(m), 6)), lossless=lossless)
        _replace_if_smaller(file_path, buf.getvalue())
    except Exception as err:
        return str(err)

# }}}


# PIL images {{{
def align8to32(bytes, width, mode):
    '''
    converts each scanline of data from 8 bit to 32 bit aligned
    '''

    bits_per_pixel = {'1': 1, 'L': 8, 'P': 8, 'I;16': 16}[mode]

    # calculate bytes per line and the extra padding if needed
    bits_per_line = bits_per_pixel * width
    full_bytes_per_line, remaining_bits_per_line = divmod(bits_per_line, 8)
    bytes_per_line = full_bytes_per_line + (1 if remaining_bits_per_line else 0)

    extra_padding = -bytes_per_line % 4

    # already 32 bit aligned by luck
    if not extra_padding:
        return bytes

    new_data = [
        bytes[i * bytes_per_line : (i + 1) * bytes_per_line] + b'\x00' * extra_padding
        for i in range(len(bytes) // bytes_per_line)
    ]

    return b''.join(new_data)


def convert_PIL_image_to_pixmap(im, device_pixel_ratio=1.0):
    raise NotImplementedError('Qt pixmaps are not available in WASM')


def read_xmp_from_pil_image(im) -> str:
    fmt = (im.format or '').lower()
    xml = ''
    if fmt == 'jpeg':
        for segment, content in im.applist:
            if segment == 'APP1':
                marker, xmp_tags = content.split(b'\x00')[:2]
                if marker == b'http://ns.adobe.com/xap/1.0/':
                    xml = xmp_tags
                    break
    elif fmt == 'png':
        xml = im.info.get('XML:com.adobe.xmp', '')
    elif fmt == 'webp':
        xml = im.info.get('xmp', '')
    elif fmt == 'tiff':
        xml = im.tag_v2.get(700, '')
    return xml


def read_text_from_container(container, target_lang=''):
    lang_map = {}
    for li in container.xpath('descendant::*[local-name()="li"]'):
        if li.text:
            lang = li.attrib.get('{http://www.w3.org/XML/1998/namespace}lang', 'x-default')
            lang_map[lang] = li.text
    if not target_lang and 'x-default' in lang_map:
        return lang_map['x-default']
    if target_lang in lang_map:
        return lang_map[target_lang]
    from calibre.utils.localization import canonicalize_lang
    target_lang = canonicalize_lang(target_lang)
    if target_lang:
        for lang, ans in lang_map.items():
            if canonicalize_lang(lang) == target_lang:
                return ans
    return lang_map.get('x-default', '')


def read_alt_text_from_xmp(xmp, target_lang='') -> str:
    from lxml import etree

    from calibre.utils.xml_parse import safe_xml_fromstring
    try:
        root = safe_xml_fromstring(xmp)
    except Exception:
        return ''
    for a in root.xpath('//*[local-name()="AltTextAccessibility"]'):
        if ans := read_text_from_container(a, target_lang):
            return ans

    for d in etree.XPath('//dc:description', namespaces={'dc': 'http://purl.org/dc/elements/1.1/'})(root):
        if ans := read_text_from_container(d, target_lang):
            return ans
    return ''


def read_alt_text(pil_im_or_path, target_lang='') -> str:
    if isinstance(pil_im_or_path, str):
        from PIL import Image
        im = Image.open(pil_im_or_path)
    elif isinstance(pil_im_or_path, QtImage):
        im = pil_im_or_path.pil
    else:
        im = pil_im_or_path
    xmp = read_xmp_from_pil_image(im)
    if xmp:
        if alt := read_alt_text_from_xmp(xmp, target_lang).strip():
            return alt
    exif = im.getexif()
    if exif:
        if desc := exif.get(270):
            return desc.strip()
    return ''

# }}}
