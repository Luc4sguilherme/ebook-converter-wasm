#!/usr/bin/env bash
# ==========================================================================
# build-calibre-extensions.sh — Compile Calibre's C/C++ extension modules
# to WASM as static libraries for linking into the final module.
# ==========================================================================
set -euo pipefail

PREFIX="/build/libs"
CALIBRE_SRC="/build/src/calibre"
EXT_OUT="/build/libs/calibre-ext"
JOBS=$(nproc)

CFLAGS="-O2 -fPIC -I${PREFIX}/include -I${CALIBRE_SRC}/src"
CXXFLAGS="-O2 -fPIC -I${PREFIX}/include -I${CALIBRE_SRC}/src"

mkdir -p "${EXT_OUT}"

echo "=== Building Calibre C extensions for WASM ==="

# ------------------------------------------------------------------
# speedup.c — General performance utilities
# ------------------------------------------------------------------
echo ">>> speedup.c"
emcc ${CFLAGS} -c \
    "${CALIBRE_SRC}/src/calibre/utils/speedup.c" \
    -o "${EXT_OUT}/speedup.o" 2>/dev/null || echo "WARN: speedup.c skipped (may need patches)"

# ------------------------------------------------------------------
# fast_html_entities.c — HTML entity encoding
# ------------------------------------------------------------------
echo ">>> html_as_json"
if [ -f "${CALIBRE_SRC}/src/calibre/utils/fast_html_entities.cpp" ]; then
    em++ ${CXXFLAGS} -c \
        "${CALIBRE_SRC}/src/calibre/utils/fast_html_entities.cpp" \
        -o "${EXT_OUT}/fast_html_entities.o" 2>/dev/null || echo "WARN: fast_html_entities skipped"
fi

# ------------------------------------------------------------------
# tokenizer.c — Text tokenization
# ------------------------------------------------------------------
echo ">>> tokenizer"
if [ -f "${CALIBRE_SRC}/src/calibre/utils/tokenizer.c" ]; then
    emcc ${CFLAGS} -c \
        "${CALIBRE_SRC}/src/calibre/utils/tokenizer.c" \
        -o "${EXT_OUT}/tokenizer.o" 2>/dev/null || echo "WARN: tokenizer.c skipped"
fi

# ------------------------------------------------------------------
# cPalmdoc.c — PalmDOC compression
# ------------------------------------------------------------------
echo ">>> cPalmdoc"
if [ -f "${CALIBRE_SRC}/src/calibre/ebooks/compression/palmdoc.c" ]; then
    emcc ${CFLAGS} -c \
        "${CALIBRE_SRC}/src/calibre/ebooks/compression/palmdoc.c" \
        -o "${EXT_OUT}/palmdoc.o" 2>/dev/null || echo "WARN: palmdoc.c skipped"
fi

# ------------------------------------------------------------------
# lzx decompression
# ------------------------------------------------------------------
echo ">>> lzx"
for f in "${CALIBRE_SRC}/src/calibre/utils/lzx/"*.c; do
    if [ -f "$f" ]; then
        name=$(basename "$f" .c)
        emcc ${CFLAGS} -c "$f" -o "${EXT_OUT}/lzx_${name}.o" 2>/dev/null || echo "WARN: lzx/${name}.c skipped"
    fi
done

# ------------------------------------------------------------------
# bzzdec — BZZ decompression (DjVu)
# ------------------------------------------------------------------
echo ">>> bzzdec"
if [ -f "${CALIBRE_SRC}/src/calibre/utils/bzzdec.c" ]; then
    emcc ${CFLAGS} -c \
        "${CALIBRE_SRC}/src/calibre/utils/bzzdec.c" \
        -o "${EXT_OUT}/bzzdec.o" 2>/dev/null || echo "WARN: bzzdec.c skipped"
fi

# ------------------------------------------------------------------
# hunspell_wrapper — Hunspell bindings
# ------------------------------------------------------------------
echo ">>> hunspell_wrapper"
if [ -f "${CALIBRE_SRC}/src/calibre/utils/hunspell_wrapper.cpp" ]; then
    em++ ${CXXFLAGS} \
        -I"${PREFIX}/include/hunspell" \
        -c "${CALIBRE_SRC}/src/calibre/utils/hunspell_wrapper.cpp" \
        -o "${EXT_OUT}/hunspell_wrapper.o" 2>/dev/null || echo "WARN: hunspell_wrapper skipped"
fi

# ------------------------------------------------------------------
# icu bindings
# ------------------------------------------------------------------
echo ">>> icu"
if [ -f "${CALIBRE_SRC}/src/calibre/utils/icu.c" ]; then
    emcc ${CFLAGS} -c \
        "${CALIBRE_SRC}/src/calibre/utils/icu.c" \
        -o "${EXT_OUT}/icu.o" 2>/dev/null || echo "WARN: icu.c skipped (ICU not built)"
fi

# ------------------------------------------------------------------
# imageops — Image processing utilities
# ------------------------------------------------------------------
echo ">>> imageops"
if [ -f "${CALIBRE_SRC}/src/calibre/utils/imageops/imageops.cpp" ]; then
    em++ ${CXXFLAGS} \
        -I"${PREFIX}/include" \
        -c "${CALIBRE_SRC}/src/calibre/utils/imageops/imageops.cpp" \
        -o "${EXT_OUT}/imageops.o" 2>/dev/null || echo "WARN: imageops skipped (needs Qt)"
fi

# ------------------------------------------------------------------
# Package all compiled objects into a single static lib
# ------------------------------------------------------------------
echo ">>> Creating libcalibre_ext.a"
OBJ_FILES=$(find "${EXT_OUT}" -name '*.o' 2>/dev/null)
if [ -n "${OBJ_FILES}" ]; then
    emar rcs "${PREFIX}/lib/libcalibre_ext.a" ${OBJ_FILES}
    echo "<<< libcalibre_ext.a created"
else
    emar rcs "${PREFIX}/lib/libcalibre_ext.a"
    echo "<<< libcalibre_ext.a created (empty — extensions need patches)"
fi

echo ""
echo "=== Calibre C extensions build complete ==="
ls -la "${EXT_OUT}/"
