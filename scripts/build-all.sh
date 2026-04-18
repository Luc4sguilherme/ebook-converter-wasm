#!/usr/bin/env bash
# ==========================================================================
# build-all.sh — Orchestrate the final WASM link step.
#
# Links all native WASM libraries + Calibre C extensions into a single
# WASM module that provides a C-level entry point, plus generates the
# JS loader and Pyodide-based conversion engine.
# ==========================================================================
set -euo pipefail

PREFIX="/build/libs"
DIST="/build/dist"
WRAPPER_SRC="/build/src/wrapper"
JS_SRC="/build/src/js"
JOBS=$(nproc)
SINGLE_FILE="${SINGLE_FILE:-1}"

echo "=== Building final WASM module ==="

mkdir -p "${DIST}"

# ------------------------------------------------------------------
# 1. Compile the C wrapper that provides a small entry point
# ------------------------------------------------------------------
echo ">>> Compiling ebook_convert_wrapper.c"
emcc -O2 \
    -I"${PREFIX}/include" \
    -I"${PREFIX}/include/libxml2" \
    -c "${WRAPPER_SRC}/ebook_convert_wrapper.c" \
    -o "${DIST}/ebook_convert_wrapper.o"

# ------------------------------------------------------------------
# 2. Link everything into a WASM module
# ------------------------------------------------------------------
echo ">>> Linking ebook-convert.wasm"

LIBS=(
    "${PREFIX}/lib/libxml2.a"
    "${PREFIX}/lib/libxslt.a"
    "${PREFIX}/lib/libexslt.a"
    "${PREFIX}/lib/libz.a"
    "${PREFIX}/lib/libjpeg.a"
    "${PREFIX}/lib/libpng16.a"
    "${PREFIX}/lib/libfreetype.a"
    "${PREFIX}/lib/libhunspell-1.7.a"
    "${PREFIX}/lib/libuchardet.a"
    "${PREFIX}/lib/libwebp.a"
    "${PREFIX}/lib/libchm.a"
)

EXISTING_LIBS=()
for lib in "${LIBS[@]}"; do
    if [ -f "${lib}" ]; then
        EXISTING_LIBS+=("${lib}")
    else
        echo "WARN: ${lib} not found, skipping"
    fi
done

if [ -f "${PREFIX}/lib/libcalibre_ext.a" ]; then
    EXISTING_LIBS+=("${PREFIX}/lib/libcalibre_ext.a")
fi

emcc -O2 \
    "${DIST}/ebook_convert_wrapper.o" \
    "${EXISTING_LIBS[@]}" \
    -o "${DIST}/ebook-convert-native.js" \
    -sEXPORTED_FUNCTIONS='["_malloc","_free","_calibre_init","_calibre_get_version","_xml_parse_html","_xml_transform_xslt","_detect_encoding","_process_image"]' \
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
    -sSINGLE_FILE=${SINGLE_FILE} \
    --no-entry \
    -lembind

rm -f "${DIST}/ebook_convert_wrapper.o"

# ------------------------------------------------------------------
# 3. Copy poppler WASM tools (pdftohtml, pdfinfo)
# ------------------------------------------------------------------
echo ">>> Copying poppler WASM tools"
for tool in pdftohtml pdfinfo; do
    if [ -f "${PREFIX}/bin/${tool}.cjs" ]; then
        cp "${PREFIX}/bin/${tool}.cjs" "${DIST}/"
        if [ -f "${PREFIX}/bin/${tool}.wasm" ]; then
            cp "${PREFIX}/bin/${tool}.wasm" "${DIST}/"
            echo "  ${tool}.cjs + ${tool}.wasm"
        else
            echo "  ${tool}.cjs (SINGLE_FILE)"
        fi
    else
        echo "  WARN: ${tool} not found"
    fi
done

if [ -f "${PREFIX}/bin/pdftohtml.js" ]; then
    cp "${PREFIX}/bin/pdftohtml.js" "${DIST}/"
    echo "  pdftohtml.js (browser build, shares pdftohtml.wasm)"
else
    echo "  WARN: pdftohtml.js (browser) not found (PDF input in browser disabled)"
fi

if [ -f "${PREFIX}/bin/pdfinfo.js" ]; then
    cp "${PREFIX}/bin/pdfinfo.js" "${DIST}/"
    echo "  pdfinfo.js (browser build, shares pdfinfo.wasm)"
else
    echo "  WARN: pdfinfo.js (browser) not found (PDF metadata in browser disabled)"
fi

# ------------------------------------------------------------------
# 4. Copy the main JS API and worker (flat dist for bundling input)
# ------------------------------------------------------------------
echo ">>> Copying JS files"
if [ -d "/build/src-host/js" ]; then
    cp /build/src-host/js/*.js "${DIST}/" 2>/dev/null || true
elif [ -d "${JS_SRC}" ]; then
    cp "${JS_SRC}"/*.js "${DIST}/" 2>/dev/null || true
fi

# ------------------------------------------------------------------
# 5. Bundle into node/ and browser/ production builds
# ------------------------------------------------------------------
echo ""
echo ">>> Building production bundles (node + browser)"
if [ -f "/build/scripts/build-dist.mjs" ] && command -v node >/dev/null 2>&1; then
    cd /build
    node /build/scripts/build-dist.mjs
    echo "  Production bundles created"
else
    echo "  WARN: build-dist.mjs or node not available, skipping production bundles"
fi

# ------------------------------------------------------------------
# 6. Clean up flat dist files (only node/ and browser/ should remain)
# ------------------------------------------------------------------
echo ""
echo ">>> Cleaning flat dist files"
rm -f "${DIST}"/ebook-convert.js "${DIST}"/worker.js
rm -f "${DIST}"/ebook-convert-native.js "${DIST}"/ebook-convert-native.wasm
rm -f "${DIST}"/pdftohtml.cjs "${DIST}"/pdftohtml.wasm "${DIST}"/pdftohtml.js
rm -f "${DIST}"/pdfinfo.cjs "${DIST}"/pdfinfo.wasm "${DIST}"/pdfinfo.js
rm -f "${DIST}"/calibre-python.zip
rm -rf "${DIST}"/calibre-python/
echo "  Flat files removed"

echo ""
echo "=== Build complete ==="
echo "Artifacts in ${DIST}:"
ls -laR "${DIST}/"
echo ""
echo "Total size:"
du -sh "${DIST}/"
