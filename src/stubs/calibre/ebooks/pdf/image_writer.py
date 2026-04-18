"""
WASM stub for calibre.ebooks.pdf.image_writer

Converts a collection of images to a PDF using fpdf2.
Replaces the original Qt-based implementation.
"""
import os
import tempfile

PAGE_SIZES = {
    'a0': (2383.94, 3370.39), 'a1': (1683.78, 2383.94),
    'a2': (1190.55, 1683.78), 'a3': (841.89, 1190.55),
    'a4': (595.28, 841.89), 'a5': (419.53, 595.28),
    'a6': (297.64, 419.53),
    'b0': (2834.65, 4008.19), 'b1': (2004.09, 2834.65),
    'b2': (1417.32, 2004.09), 'b3': (1000.63, 1417.32),
    'b4': (708.66, 1000.63), 'b5': (498.90, 708.66),
    'b6': (354.33, 498.90),
    'letter': (612.0, 792.0), 'legal': (612.0, 1008.0),
}

UNIT_FACTORS = {
    'point': 1.0, 'inch': 72.0, 'millimeter': 72.0 / 25.4,
    'centimeter': 72.0 / 2.54, 'pica': 12.0,
    'didot': 0.375 * (72.0 / 25.4),
    'cicero': 12 * 0.375 * (72.0 / 25.4),
    'devicepixel': 1.0,
}

class PDFMetadata:
    def __init__(self, mi=None):
        self.title = 'Unknown'
        self.author = 'Unknown'
        self.tags = ''
        self.mi = mi
        if mi is not None:
            if mi.title:
                self.title = str(mi.title)
            if mi.authors:
                from calibre.ebooks.metadata import authors_to_string
                self.author = authors_to_string(mi.authors)
            if mi.tags:
                self.tags = ', '.join(mi.tags)

def get_page_layout(opts, for_comic=False):
    """Return page layout info as a simple dict (replaces Qt QPageLayout)."""
    paper = getattr(opts, 'paper_size', 'letter') or 'letter'
    pts = PAGE_SIZES.get(paper.lower(), PAGE_SIZES['letter'])

    if getattr(opts, 'custom_size', None):
        parts = opts.custom_size.lower().split('x')
        if len(parts) == 2:
            try:
                w, h = float(parts[0].strip()), float(parts[1].strip())
                factor = UNIT_FACTORS.get(getattr(opts, 'unit', 'inch'), 72.0)
                pts = (w * factor, h * factor)
            except (ValueError, TypeError):
                pass

    def m(which):
        return max(0, getattr(opts, 'pdf_page_margin_' + which, 0) or
                   getattr(opts, 'margin_' + which, 0))

    return {
        'width_pt': pts[0],
        'height_pt': pts[1],
        'margin_left': m('left'),
        'margin_top': m('top'),
        'margin_right': m('right'),
        'margin_bottom': m('bottom'),
    }

def convert(images, output_path, opts, metadata, report_progress=None):
    """
    Convert a list of images to a PDF file using fpdf2.

    Args:
        images:          List of image file paths
        output_path:     Where to write the PDF
        opts:            Conversion options
        metadata:        PDFMetadata instance or book metadata
        report_progress: Progress callback
    """
    from fpdf import FPDF

    paper = getattr(opts, 'paper_size', 'letter') or 'letter'
    pts = PAGE_SIZES.get(paper.lower(), PAGE_SIZES['letter'])

    page_w_mm = pts[0] / (72.0 / 25.4)
    page_h_mm = pts[1] / (72.0 / 25.4)

    pdf = FPDF(unit='mm', format=(page_w_mm, page_h_mm))
    pdf.set_auto_page_break(False)
    pdf.set_margins(0, 0, 0)

    if metadata:
        if hasattr(metadata, 'title'):
            pdf.set_title(str(metadata.title))
        if hasattr(metadata, 'author'):
            pdf.set_author(str(metadata.author))

    preserve_aspect = getattr(opts, 'preserve_cover_aspect_ratio', False)

    image_list = list(images)
    total = len(image_list)

    for idx, img_path in enumerate(image_list):
        if report_progress:
            report_progress(idx / max(total, 1),
                            f'Adding image {idx + 1}/{total}')

        pdf.add_page()

        if isinstance(img_path, bytes):
            suffix = '.jpg'
            if img_path[:4] == b'\x89PNG':
                suffix = '.png'
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(img_path)
                img_file = tmp.name
            cleanup = True
        elif isinstance(img_path, str):
            img_file = img_path
            cleanup = False
        else:

            img_file = str(img_path)
            cleanup = False

        try:
            if preserve_aspect:
                pdf.image(img_file, x=0, y=0, w=page_w_mm, h=0,
                          keep_aspect_ratio=True)
            else:
                pdf.image(img_file, x=0, y=0, w=page_w_mm, h=page_h_mm)
        except Exception:
            pass  
        finally:
            if cleanup:
                try:
                    os.unlink(img_file)
                except OSError:
                    pass

    pdf.output(output_path)

    if report_progress:
        report_progress(1.0, 'Done')
