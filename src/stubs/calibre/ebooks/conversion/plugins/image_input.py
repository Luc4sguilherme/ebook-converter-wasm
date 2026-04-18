"""Input plugin for standalone image files (jpg, png, gif, webp, svg, bmp)."""
import os
import base64

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation

class ImageInput(InputFormatPlugin):

    name = 'Image Input'
    author = 'ebook-converter-wasm'
    file_types = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'tiff', 'tif'}
    supported_platforms = ['linux']
    commit_name = 'image_input'
    is_image_collection = True

    recommendations = set()
    options = set()

    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.ebooks.metadata import MetaInformation
        from calibre.ebooks.metadata.meta import metadata_from_filename
        from calibre.ebooks.oeb.base import OEBBook

        mi = metadata_from_filename(stream.name)

        if hasattr(stream, 'read'):
            img_data = stream.read()
        else:
            with open(stream, 'rb') as f:
                img_data = f.read()

        ext = file_ext.lower()
        if ext in ('jpg', 'jpeg'):
            mime = 'image/jpeg'
        elif ext == 'png':
            mime = 'image/png'
        elif ext == 'gif':
            mime = 'image/gif'
        elif ext == 'webp':
            mime = 'image/webp'
        elif ext == 'svg':
            mime = 'image/svg+xml'
        elif ext in ('tiff', 'tif'):
            mime = 'image/tiff'
        elif ext == 'bmp':
            mime = 'image/bmp'
        else:
            mime = 'image/' + ext

        b64 = base64.b64encode(img_data).decode('ascii')
        html = f'''<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{mi.title}</title></head>
<body>
<div style="text-align:center">
<img src="data:{mime};base64,{b64}" alt="{mi.title}" style="max-width:100%;max-height:100%"/>
</div>
</body>
</html>'''

        from calibre.ptempfile import PersistentTemporaryDirectory
        tdir = PersistentTemporaryDirectory('_image_input')
        htmlpath = os.path.join(tdir, 'index.xhtml')
        with open(htmlpath, 'w', encoding='utf-8') as f:
            f.write(html)

        imgpath = os.path.join(tdir, f'cover.{ext}')
        with open(imgpath, 'wb') as f:
            f.write(img_data)
        mi.cover = imgpath

        from calibre.ebooks.conversion.plugins.html_input import HTMLInput
        html_input = HTMLInput(None)
        with open(htmlpath, 'rb') as f:
            oeb = html_input.create_oebbook(f.name, tdir, options, log, mi)

        return oeb
