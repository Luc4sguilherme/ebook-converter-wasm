#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include <libxml/parser.h>
#include <libxml/HTMLparser.h>
#include <libxml/tree.h>
#include <libxml/xmlmemory.h>

#include <libxslt/xslt.h>
#include <libxslt/transform.h>
#include <libxslt/xsltutils.h>

#include <zlib.h>

#ifdef HAVE_UCHARDET
#include <uchardet/uchardet.h>
#endif

#ifdef HAVE_JPEGLIB
#include <jpeglib.h>
#endif

#ifdef HAVE_PNG
#include <png.h>
#endif

static int g_initialized = 0;

#define CALIBRE_WASM_VERSION "7.9.0-wasm.1"

/**
 * Initialize the native libraries. Must be called once before any
 * other function.
 *
 * @return 0 on success, non-zero on error
 */
int calibre_init(void) {
    if (g_initialized) return 0;

    xmlInitParser();
    LIBXML_TEST_VERSION;

    xsltInit();

    g_initialized = 1;
    return 0;
}

/**
 * Return a version string for the WASM build.
 */
const char* calibre_get_version(void) {
    return CALIBRE_WASM_VERSION;
}

/**
 * Parse an HTML document and return a cleaned-up XHTML string.
 *
 * @param html_data     Pointer to HTML bytes
 * @param html_len      Length of HTML data
 * @param encoding      Encoding hint (e.g. "UTF-8") or NULL
 * @param out_len       Receives the length of the output
 * @return              Pointer to malloc'd XHTML string (caller must free)
 */
char* xml_parse_html(const char* html_data, int html_len,
                     const char* encoding, int* out_len) {
    if (!g_initialized) calibre_init();

    htmlDocPtr doc = htmlReadMemory(
        html_data, html_len, NULL,
        encoding ? encoding : "UTF-8",
        HTML_PARSE_RECOVER | HTML_PARSE_NOERROR | HTML_PARSE_NOWARNING |
        HTML_PARSE_NOBLANKS | HTML_PARSE_COMPACT
    );

    if (!doc) {
        *out_len = 0;
        return NULL;
    }

    xmlChar* mem = NULL;
    int size = 0;
    xmlDocDumpMemory(doc, &mem, &size);
    xmlFreeDoc(doc);

    if (mem && size > 0) {
        char* result = (char*)malloc(size + 1);
        if (result) {
            memcpy(result, mem, size);
            result[size] = '\0';
            *out_len = size;
        }
        xmlFree(mem);
        return result;
    }

    *out_len = 0;
    return NULL;
}

/**
 * Apply an XSLT stylesheet to an XML document.
 *
 * @param xml_data       XML document bytes
 * @param xml_len        Length of XML
 * @param xslt_data      XSLT stylesheet bytes
 * @param xslt_len       Length of XSLT
 * @param out_len        Receives the length of the output
 * @return               Pointer to malloc'd result string (caller must free)
 */
char* xml_transform_xslt(const char* xml_data, int xml_len,
                          const char* xslt_data, int xslt_len,
                          int* out_len) {
    if (!g_initialized) calibre_init();

    *out_len = 0;

    xmlDocPtr xml_doc = xmlReadMemory(xml_data, xml_len, NULL, "UTF-8",
                                       XML_PARSE_RECOVER | XML_PARSE_NOERROR);
    if (!xml_doc) return NULL;

    xmlDocPtr xslt_doc = xmlReadMemory(xslt_data, xslt_len, NULL, "UTF-8",
                                        XML_PARSE_RECOVER | XML_PARSE_NOERROR);
    if (!xslt_doc) {
        xmlFreeDoc(xml_doc);
        return NULL;
    }

    xsltStylesheetPtr stylesheet = xsltParseStylesheetDoc(xslt_doc);
    if (!stylesheet) {
        xmlFreeDoc(xml_doc);
        /* xslt_doc is freed by xsltParseStylesheetDoc on failure */
        return NULL;
    }

    xmlDocPtr result_doc = xsltApplyStylesheet(stylesheet, xml_doc, NULL);

    char* result = NULL;
    if (result_doc) {
        xmlChar* mem = NULL;
        int size = 0;
        xsltSaveResultToString(&mem, &size, result_doc, stylesheet);
        if (mem && size > 0) {
            result = (char*)malloc(size + 1);
            if (result) {
                memcpy(result, mem, size);
                result[size] = '\0';
                *out_len = size;
            }
            xmlFree(mem);
        }
        xmlFreeDoc(result_doc);
    }

    xsltFreeStylesheet(stylesheet); /* This also frees xslt_doc */
    xmlFreeDoc(xml_doc);

    return result;
}

/**
 * Detect the character encoding of a byte buffer.
 *
 * @param data      Pointer to the data
 * @param data_len  Length of data
 * @return          Pointer to a static encoding name string, or "UTF-8"
 */
const char* detect_encoding(const char* data, int data_len) {
#ifdef HAVE_UCHARDET
    uchardet_t ud = uchardet_new();
    if (uchardet_handle_data(ud, data, data_len) != 0) {
        uchardet_delete(ud);
        return "UTF-8";
    }
    uchardet_data_end(ud);
    const char* encoding = uchardet_get_charset(ud);
    /* Must copy — uchardet_delete frees the string */
    static char enc_buf[64];
    strncpy(enc_buf, encoding && encoding[0] ? encoding : "UTF-8",
            sizeof(enc_buf) - 1);
    enc_buf[sizeof(enc_buf) - 1] = '\0';
    uchardet_delete(ud);
    return enc_buf;
#else
    (void)data;
    (void)data_len;
    return "UTF-8";
#endif
}

/**
 * Re-encode an image to JPEG with a given quality.
 * Minimal placeholder — full implementation would use libjpeg + libpng.
 *
 * @param img_data    Image bytes (JPEG or PNG input)
 * @param img_len     Length of image data
 * @param quality     JPEG quality (1-100)
 * @param out_len     Receives length of output
 * @return            Pointer to malloc'd JPEG data (caller must free)
 */
unsigned char* process_image(const unsigned char* img_data, int img_len,
                              int quality, int* out_len) {
    (void)quality;

    unsigned char* result = (unsigned char*)malloc(img_len);
    if (result) {
        memcpy(result, img_data, img_len);
        *out_len = img_len;
    } else {
        *out_len = 0;
    }
    return result;
}

/**
 * Decompress gzip data.
 *
 * @param data        Compressed data
 * @param data_len    Length of compressed data
 * @param out_len     Receives length of decompressed output
 * @return            Pointer to malloc'd decompressed data (caller must free)
 */
unsigned char* decompress_gzip(const unsigned char* data, int data_len,
                                int* out_len) {
    int buf_size = data_len * 4;
    if (buf_size < 4096) buf_size = 4096;

    unsigned char* buf = (unsigned char*)malloc(buf_size);
    if (!buf) {
        *out_len = 0;
        return NULL;
    }

    z_stream strm;
    memset(&strm, 0, sizeof(strm));
    strm.next_in = (unsigned char*)data;
    strm.avail_in = data_len;
    strm.next_out = buf;
    strm.avail_out = buf_size;

    /* windowBits = 15 + 32 for auto-detect gzip/zlib header */
    if (inflateInit2(&strm, 15 + 32) != Z_OK) {
        free(buf);
        *out_len = 0;
        return NULL;
    }

    int ret;
    while (1) {
        ret = inflate(&strm, Z_NO_FLUSH);
        if (ret == Z_STREAM_END) break;
        if (ret != Z_OK) {
            inflateEnd(&strm);
            free(buf);
            *out_len = 0;
            return NULL;
        }
        if (strm.avail_out == 0) {
            int new_size = buf_size * 2;
            unsigned char* new_buf = (unsigned char*)realloc(buf, new_size);
            if (!new_buf) {
                inflateEnd(&strm);
                free(buf);
                *out_len = 0;
                return NULL;
            }
            buf = new_buf;
            strm.next_out = buf + buf_size;
            strm.avail_out = new_size - buf_size;
            buf_size = new_size;
        }
    }

    inflateEnd(&strm);
    *out_len = strm.total_out;
    return buf;
}
