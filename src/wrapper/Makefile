CC = emcc
CXX = em++
AR = emar

PREFIX ?= /build/libs
DIST ?= /build/dist

CFLAGS = -O2 -fPIC \
	-I$(PREFIX)/include \
	-I$(PREFIX)/include/libxml2

WRAPPER_SRC = ebook_convert_wrapper.c
WRAPPER_OBJ = $(DIST)/ebook_convert_wrapper.o

SINGLE_FILE ?= 1

LIBS = \
	$(PREFIX)/lib/libxml2.a \
	$(PREFIX)/lib/libxslt.a \
	$(PREFIX)/lib/libz.a \
	$(PREFIX)/lib/libjpeg.a \
	$(PREFIX)/lib/libpng16.a \
	$(PREFIX)/lib/libfreetype.a \
	$(PREFIX)/lib/libhunspell-1.7.a \
	$(PREFIX)/lib/libuchardet.a \
	$(PREFIX)/lib/libwebp.a \
	$(PREFIX)/lib/libchm.a

EXISTING_LIBS = $(wildcard $(LIBS))

LDFLAGS = \
	-sEXPORTED_FUNCTIONS='["_malloc","_free","_calibre_init","_calibre_get_version","_xml_parse_html","_xml_transform_xslt","_detect_encoding","_process_image","_decompress_gzip"]' \
	-sEXPORTED_RUNTIME_METHODS='["ccall","cwrap","FS","MEMFS","UTF8ToString","stringToUTF8","lengthBytesUTF8","getValue","setValue"]' \
	-sMODULARIZE=1 \
	-sEXPORT_NAME='CalibreNative' \
	-sALLOW_MEMORY_GROWTH=1 \
	-sINITIAL_MEMORY=67108864 \
	-sMAXIMUM_MEMORY=2147483648 \
	-sFILESYSTEM=1 \
	-sFORCE_FILESYSTEM=1 \
	-sENVIRONMENT='web,worker,node' \
	-sNO_EXIT_RUNTIME=1 \
	-sSINGLE_FILE=$(SINGLE_FILE) \
	--no-entry

.PHONY: all clean

all: $(DIST)/ebook-convert-native.js

$(WRAPPER_OBJ): $(WRAPPER_SRC)
	@mkdir -p $(DIST)
	$(CC) $(CFLAGS) -c $< -o $@

$(DIST)/ebook-convert-native.js: $(WRAPPER_OBJ) $(EXISTING_LIBS)
	$(CC) -O2 $^ -o $@ $(LDFLAGS)

clean:
	rm -f $(WRAPPER_OBJ) $(DIST)/ebook-convert-native.js $(DIST)/ebook-convert-native.wasm
