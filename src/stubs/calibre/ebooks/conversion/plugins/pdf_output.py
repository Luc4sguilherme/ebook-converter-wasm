"""
WASM stub for calibre PDF output plugin.

Replaces the original Qt WebEngine-based PDF renderer with fpdf2,
a pure-Python PDF library that works in Pyodide/WASM.
"""
import glob
import os

from calibre.customize.conversion import OptionRecommendation, OutputFormatPlugin
from calibre.ptempfile import TemporaryDirectory

UNITS = ('millimeter', 'centimeter', 'point', 'inch', 'pica', 'didot',
         'cicero', 'devicepixel')

PAPER_SIZES = ('a0', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'b0', 'b1',
               'b2', 'b3', 'b4', 'b5', 'b6', 'legal', 'letter')

class PDFOutput(OutputFormatPlugin):

    name = 'PDF Output'
    author = 'ebook-converter-wasm'
    file_type = 'pdf'
    commit_name = 'pdf_output'
    ui_data = {
        'paper_sizes': PAPER_SIZES,
        'units': UNITS,
        'font_types': ('serif', 'sans', 'mono'),
    }

    options = {
        OptionRecommendation(
            name='use_profile_size', recommended_value=False,
            help='Use a paper size corresponding to the current output profile.'),
        OptionRecommendation(
            name='unit', recommended_value='inch',
            level=OptionRecommendation.LOW, short_switch='u', choices=UNITS,
            help='The unit of measure for page sizes. Default is inch.'),
        OptionRecommendation(
            name='paper_size', recommended_value='letter',
            level=OptionRecommendation.LOW, choices=PAPER_SIZES,
            help='The size of the paper. Default is letter.'),
        OptionRecommendation(
            name='custom_size', recommended_value=None,
            help='Custom size of the document. Use the form widthxheight.'),
        OptionRecommendation(
            name='preserve_cover_aspect_ratio', recommended_value=False,
            help='Preserve the aspect ratio of the cover.'),
        OptionRecommendation(
            name='pdf_serif_family', recommended_value='Times',
            help='The font family used to render serif fonts.'),
        OptionRecommendation(
            name='pdf_sans_family', recommended_value='Helvetica',
            help='The font family used to render sans-serif fonts.'),
        OptionRecommendation(
            name='pdf_mono_family', recommended_value='Courier',
            help='The font family used to render monospace fonts.'),
        OptionRecommendation(
            name='pdf_standard_font', choices=('serif', 'sans', 'mono'),
            recommended_value='serif',
            help='The default font family type.'),
        OptionRecommendation(
            name='pdf_default_font_size', recommended_value=20,
            help='The default font size (in pixels).'),
        OptionRecommendation(
            name='pdf_mono_font_size', recommended_value=16,
            help='The default font size for monospaced text (in pixels).'),
        OptionRecommendation(
            name='pdf_hyphenate', recommended_value=False,
            help='Break long words at the end of lines.'),
        OptionRecommendation(
            name='pdf_mark_links', recommended_value=False,
            help='Surround all links with a red box.'),
        OptionRecommendation(
            name='pdf_page_numbers', recommended_value=False,
            help='Add page numbers to the bottom of every page.'),
        OptionRecommendation(
            name='pdf_footer_template', recommended_value=None,
            help='An HTML template used to generate footers on every page.'),
        OptionRecommendation(
            name='pdf_header_template', recommended_value=None,
            help='An HTML template used to generate headers on every page.'),
        OptionRecommendation(
            name='pdf_add_toc', recommended_value=False,
            help='Add a Table of Contents at the end of the PDF.'),
        OptionRecommendation(
            name='toc_title', recommended_value=None,
            help='Title for generated table of contents.'),
        OptionRecommendation(
            name='pdf_page_margin_left', recommended_value=72.0,
            level=OptionRecommendation.LOW,
            help='The size of the left page margin, in pts.'),
        OptionRecommendation(
            name='pdf_page_margin_top', recommended_value=72.0,
            level=OptionRecommendation.LOW,
            help='The size of the top page margin, in pts.'),
        OptionRecommendation(
            name='pdf_page_margin_right', recommended_value=72.0,
            level=OptionRecommendation.LOW,
            help='The size of the right page margin, in pts.'),
        OptionRecommendation(
            name='pdf_page_margin_bottom', recommended_value=72.0,
            level=OptionRecommendation.LOW,
            help='The size of the bottom page margin, in pts.'),
        OptionRecommendation(
            name='pdf_use_document_margins', recommended_value=False,
            help='Use the page margins specified in the input document.'),
        OptionRecommendation(
            name='pdf_page_number_map', recommended_value=None,
            help='Adjust page numbers, as needed.'),
        OptionRecommendation(
            name='uncompressed_pdf', recommended_value=False,
            help='Generate an uncompressed PDF, useful for debugging.'),
        OptionRecommendation(
            name='pdf_odd_even_offset', recommended_value=0.0,
            level=OptionRecommendation.LOW,
            help='Shift the text horizontally by the specified offset (in pts).'),
        OptionRecommendation(
            name='pdf_no_cover', recommended_value=False,
            help='Do not insert the book cover as an image at the start.'),
    }

    def specialize_options(self, log, opts, input_fmt):
        self.input_fmt = input_fmt
        if opts.pdf_use_document_margins:
            opts.margin_left = opts.margin_right = -1
            opts.margin_top = opts.margin_bottom = -1

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        self.oeb = oeb_book
        self.input_plugin, self.opts, self.log = input_plugin, opts, log
        self.output_path = output_path
        self.cover_data = None

        from io import BytesIO
        from lxml import etree
        from calibre.ebooks.oeb.base import OPF, OPF2_NS
        package = etree.Element(
            OPF('package'),
            attrib={'version': '2.0', 'unique-identifier': 'dummy'},
            nsmap={None: OPF2_NS})
        from calibre.ebooks.metadata.opf2 import OPF
        self.oeb.metadata.to_opf2(package)
        self.metadata = OPF(BytesIO(etree.tostring(package))).to_book_metadata()

        if input_plugin.is_image_collection:
            log.debug('Converting input as an image collection...')
            self.convert_images(input_plugin.get_images())
        else:
            log.debug('Converting input as a text based book...')
            self.convert_text(oeb_book)

    def convert_images(self, images):
        from calibre.ebooks.pdf.image_writer import convert
        convert(images, self.output_path, self.opts, self.metadata,
                self.report_progress)

    def get_cover_data(self):
        oeb = self.oeb
        if (oeb.metadata.cover and
                str(oeb.metadata.cover[0]) in oeb.manifest.ids):
            cover_id = str(oeb.metadata.cover[0])
            item = oeb.manifest.ids[cover_id]
            if isinstance(item.data, bytes):
                self.cover_data = item.data

    def convert_text(self, oeb_book):
        if not self.opts.pdf_no_cover:
            self.get_cover_data()

        with TemporaryDirectory('_pdf_out') as oeb_dir:
            from calibre.customize.ui import plugin_for_output_format
            oeb_dir = os.path.realpath(oeb_dir)
            oeb_output = plugin_for_output_format('oeb')
            oeb_output.convert(
                oeb_book, oeb_dir, self.input_plugin, self.opts, self.log)
            opfpath = glob.glob(os.path.join(oeb_dir, '*.opf'))[0]
            from calibre.ebooks.pdf.html_writer import convert
            convert(
                opfpath, self.opts,
                metadata=self.metadata,
                output_path=self.output_path,
                log=self.log,
                cover_data=self.cover_data,
                report_progress=self.report_progress,
            )
