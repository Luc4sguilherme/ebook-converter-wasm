# ============================================================================
# Stage 1: Emscripten SDK + Build Dependencies
# ============================================================================
FROM emscripten/emsdk:3.1.56 AS emsdk-base

ENV DEBIAN_FRONTEND=noninteractive
ENV EMSDK=/emsdk
ENV EM_CONFIG=/emsdk/.emscripten
ENV PATH="${EMSDK}/upstream/emscripten:${PATH}"
ENV CFLAGS_WASM="-O2 -fPIC"
ENV CXXFLAGS_WASM="-O2 -fPIC"

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    build-essential \
    cmake \
    curl \
    git \
    libtool \
    pkg-config \
    python3 \
    python3-pip \
    python3-venv \
    unzip \
    wget \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /build/src /build/libs /build/dist /build/scripts

# ============================================================================
# Stage 2: Compile native C/C++ libraries to WASM
# ============================================================================
FROM emsdk-base AS native-libs

ARG SINGLE_FILE=1
ENV SINGLE_FILE=$SINGLE_FILE

WORKDIR /build/src

# ----------------------------------------------------------------------------
# zlib 1.3.2
# ----------------------------------------------------------------------------
RUN curl -fsSL https://github.com/madler/zlib/releases/download/v1.3.2/zlib-1.3.2.tar.gz | tar xz \
    && cd zlib-1.3.2 \
    && emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX=/build/libs \
        -DCMAKE_C_FLAGS="${CFLAGS_WASM}" \
        -DBUILD_SHARED_LIBS=OFF \
        -DZLIB_BUILD_EXAMPLES=OFF \
    && cmake --build build --target zlibstatic -j$(nproc) \
    && cmake --install build \
    && cd .. && rm -rf zlib-1.3.2

# ----------------------------------------------------------------------------
# libxml2 2.12.6 (without Python bindings)
# ----------------------------------------------------------------------------
RUN curl -fsSL https://gitlab.gnome.org/GNOME/libxml2/-/archive/v2.12.6/libxml2-v2.12.6.tar.gz | tar xz \
    && cd libxml2-v2.12.6 \
    && emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX=/build/libs \
        -DCMAKE_C_FLAGS="${CFLAGS_WASM}" \
        -DLIBXML2_WITH_PYTHON=OFF \
        -DLIBXML2_WITH_LZMA=OFF \
        -DLIBXML2_WITH_ZLIB=ON \
        -DLIBXML2_WITH_ICU=OFF \
        -DLIBXML2_WITH_THREADS=OFF \
        -DLIBXML2_WITH_HTTP=OFF \
        -DLIBXML2_WITH_FTP=OFF \
        -DBUILD_SHARED_LIBS=OFF \
        -DZLIB_LIBRARY=/build/libs/lib/libz.a \
        -DZLIB_INCLUDE_DIR=/build/libs/include \
    && cmake --build build -j$(nproc) \
    && cmake --install build \
    && cd .. && rm -rf libxml2-v2.12.6

# ----------------------------------------------------------------------------
# libxslt 1.1.39
# ----------------------------------------------------------------------------
RUN curl -fsSL https://gitlab.gnome.org/GNOME/libxslt/-/archive/v1.1.39/libxslt-v1.1.39.tar.gz | tar xz \
    && cd libxslt-v1.1.39 \
    && emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX=/build/libs \
        -DCMAKE_C_FLAGS="${CFLAGS_WASM}" \
        -DLIBXSLT_WITH_PYTHON=OFF \
        -DLIBXSLT_WITH_CRYPTO=OFF \
        -DBUILD_SHARED_LIBS=OFF \
        -DCMAKE_PREFIX_PATH=/build/libs \
        -DLibXml2_DIR=/build/libs/lib/cmake/libxml2-2.12.6 \
        -DZLIB_LIBRARY=/build/libs/lib/libz.a \
        -DZLIB_INCLUDE_DIR=/build/libs/include \
    && cmake --build build -j$(nproc) \
    && cmake --install build \
    && cd .. && rm -rf libxslt-v1.1.39

# ----------------------------------------------------------------------------
# libjpeg-turbo 3.0.2
# ----------------------------------------------------------------------------
RUN curl -fsSL https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/3.0.2/libjpeg-turbo-3.0.2.tar.gz | tar xz \
    && cd libjpeg-turbo-3.0.2 \
    && emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX=/build/libs \
        -DCMAKE_C_FLAGS="${CFLAGS_WASM}" \
        -DWITH_SIMD=OFF \
        -DWITH_TURBOJPEG=OFF \
        -DENABLE_SHARED=OFF \
        -DENABLE_STATIC=ON \
    && cmake --build build -j$(nproc) \
    && cmake --install build \
    && cd .. && rm -rf libjpeg-turbo-3.0.2

# ----------------------------------------------------------------------------
# libpng 1.6.43
# ----------------------------------------------------------------------------
RUN curl -fsSL https://github.com/pnggroup/libpng/archive/refs/tags/v1.6.43.tar.gz | tar xz \
    && cd libpng-1.6.43 \
    && emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX=/build/libs \
        -DCMAKE_C_FLAGS="${CFLAGS_WASM}" \
        -DPNG_SHARED=OFF \
        -DPNG_STATIC=ON \
        -DPNG_TESTS=OFF \
        -DPNG_HARDWARE_OPTIMIZATIONS=OFF \
        -DZLIB_LIBRARY=/build/libs/lib/libz.a \
        -DZLIB_INCLUDE_DIR=/build/libs/include \
    && cmake --build build -j$(nproc) \
    && cmake --install build \
    && cd .. && rm -rf libpng-1.6.43

# ----------------------------------------------------------------------------
# FreeType 2.13.2
# ----------------------------------------------------------------------------
RUN curl -fsSL https://github.com/freetype/freetype/archive/refs/tags/VER-2-13-2.tar.gz | tar xz \
    && cd freetype-VER-2-13-2 \
    && emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX=/build/libs \
        -DCMAKE_C_FLAGS="${CFLAGS_WASM}" \
        -DBUILD_SHARED_LIBS=OFF \
        -DFT_DISABLE_BROTLI=ON \
        -DFT_DISABLE_HARFBUZZ=ON \
        -DFT_DISABLE_BZIP2=ON \
        -DZLIB_LIBRARY=/build/libs/lib/libz.a \
        -DZLIB_INCLUDE_DIR=/build/libs/include \
        -DPNG_LIBRARY=/build/libs/lib/libpng16.a \
        -DPNG_PNG_INCLUDE_DIR=/build/libs/include \
    && cmake --build build -j$(nproc) \
    && cmake --install build \
    && cd .. && rm -rf freetype-VER-2-13-2

# ----------------------------------------------------------------------------
# HunSpell 1.7.2
# ----------------------------------------------------------------------------
RUN curl -fsSL https://github.com/hunspell/hunspell/releases/download/v1.7.2/hunspell-1.7.2.tar.gz | tar xz \
    && cd hunspell-1.7.2 \
    && curl -fsSL 'https://git.savannah.gnu.org/cgit/config.git/plain/config.sub' > config.sub \
    && curl -fsSL 'https://git.savannah.gnu.org/cgit/config.git/plain/config.guess' > config.guess \
    && emconfigure ./configure \
        --prefix=/build/libs \
        --host=wasm32-unknown-emscripten \
        --enable-static \
        --disable-shared \
        --with-ui=no \
        --with-readline=no \
        CXXFLAGS="${CXXFLAGS_WASM}" \
    && emmake make -j$(nproc) \
    && emmake make install \
    && cd .. && rm -rf hunspell-1.7.2

# ----------------------------------------------------------------------------
# chmlib 0.40
# ----------------------------------------------------------------------------
RUN curl -fsSL https://github.com/jedwing/CHMLib/archive/refs/heads/master.tar.gz | tar xz \
    && cd CHMLib-master/src \
    && emcc ${CFLAGS_WASM} -I. -c chm_lib.c -o chm_lib.o \
    && emcc ${CFLAGS_WASM} -I. -c lzx.c -o lzx.o \
    && emar rcs /build/libs/lib/libchm.a chm_lib.o lzx.o \
    && cp chm_lib.h /build/libs/include/ \
    && cd ../.. && rm -rf CHMLib-master

# ----------------------------------------------------------------------------
# uchardet 0.0.8
# ----------------------------------------------------------------------------
RUN curl -fsSL https://gitlab.freedesktop.org/uchardet/uchardet/-/archive/v0.0.8/uchardet-v0.0.8.tar.gz | tar xz \
    && cd uchardet-v0.0.8 \
    && emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX=/build/libs \
        -DCMAKE_CXX_FLAGS="${CXXFLAGS_WASM}" \
        -DBUILD_BINARY=OFF \
        -DBUILD_SHARED_LIBS=OFF \
    && cmake --build build -j$(nproc) \
    && cmake --install build \
    && cd .. && rm -rf uchardet-v0.0.8

# ----------------------------------------------------------------------------
# libwebp 1.3.2
# ----------------------------------------------------------------------------
RUN curl -fsSL https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-1.3.2.tar.gz | tar xz \
    && cd libwebp-1.3.2 \
    && emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX=/build/libs \
        -DCMAKE_C_FLAGS="${CFLAGS_WASM}" \
        -DBUILD_SHARED_LIBS=OFF \
        -DWEBP_BUILD_ANIM_UTILS=OFF \
        -DWEBP_BUILD_CWEBP=OFF \
        -DWEBP_BUILD_DWEBP=OFF \
        -DWEBP_BUILD_GIF2WEBP=OFF \
        -DWEBP_BUILD_IMG2WEBP=OFF \
        -DWEBP_BUILD_VWEBP=OFF \
        -DWEBP_BUILD_WEBPMUX=OFF \
        -DWEBP_BUILD_EXTRAS=OFF \
        -DWEBP_BUILD_WEBPINFO=OFF \
    && cmake --build build -j$(nproc) \
    && cmake --install build \
    && cd .. && rm -rf libwebp-1.3.2

# ----------------------------------------------------------------------------
# poppler 21.04.0 (provides pdftohtml, pdfinfo)
# Compiled to WASM as standalone CLI tools using NODERAWFS
# Using 21.04.0 — proven to work with Emscripten cross-compilation
# ----------------------------------------------------------------------------
RUN mkdir -p /build/libs/bin \
    && curl -fsSL https://poppler.freedesktop.org/poppler-21.04.0.tar.xz | tar xJ \
    && cd poppler-21.04.0 && mkdir -p build && cd build \
    && emcmake cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/build/libs \
        -DCMAKE_C_FLAGS="${CFLAGS_WASM}" \
        -DCMAKE_CXX_FLAGS="${CXXFLAGS_WASM}" \
        -DFONT_CONFIGURATION=generic \
        -DENABLE_LIBOPENJPEG=none \
        -DENABLE_CMS=none \
        -DENABLE_DCTDECODER=libjpeg \
        -DENABLE_GLIB=OFF \
        -DENABLE_GOBJECT_INTROSPECTION=OFF \
        -DENABLE_QT5=OFF \
        -DENABLE_QT6=OFF \
        -DENABLE_CPP=OFF \
        -DENABLE_UTILS=ON \
        -DBUILD_SHARED_LIBS=OFF \
        -DBUILD_GTK_TESTS=OFF \
        -DBUILD_QT5_TESTS=OFF \
        -DBUILD_QT6_TESTS=OFF \
        -DBUILD_CPP_TESTS=OFF \
        -DCMAKE_DISABLE_FIND_PACKAGE_TIFF=ON \
        -DCMAKE_DISABLE_FIND_PACKAGE_NSS3=ON \
        -DCMAKE_FIND_ROOT_PATH=/build/libs \
        -DCMAKE_PREFIX_PATH=/build/libs \
        -DJPEG_LIBRARY=/build/libs/lib/libjpeg.a \
        -DJPEG_INCLUDE_DIR=/build/libs/include \
        -DPNG_LIBRARY=/build/libs/lib/libpng16.a \
        -DPNG_PNG_INCLUDE_DIR=/build/libs/include \
        -DFREETYPE_LIBRARY=/build/libs/lib/libfreetype.a \
        -DFREETYPE_INCLUDE_DIRS=/build/libs/include/freetype2 \
        -DZLIB_LIBRARY=/build/libs/lib/libz.a \
        -DZLIB_INCLUDE_DIR=/build/libs/include \
        -DCMAKE_EXE_LINKER_FLAGS="-sALLOW_MEMORY_GROWTH -sENVIRONMENT=node -sNODERAWFS -sEXIT_RUNTIME=1 -sSINGLE_FILE=${SINGLE_FILE}" \
    && emmake make pdftohtml pdfinfo -j$(nproc) \
    && cp utils/pdftohtml.js /build/libs/bin/pdftohtml.cjs \
    && (cp utils/pdftohtml.wasm /build/libs/bin/pdftohtml.wasm 2>/dev/null || true) \
    && cp utils/pdfinfo.js /build/libs/bin/pdfinfo.cjs \
    && (cp utils/pdfinfo.wasm /build/libs/bin/pdfinfo.wasm 2>/dev/null || true) \
    && rm -f utils/pdftohtml.js utils/pdftohtml.wasm \
    && rm -f utils/pdfinfo.js utils/pdfinfo.wasm \
    && emcmake cmake .. \
        -DCMAKE_EXE_LINKER_FLAGS="-sALLOW_MEMORY_GROWTH -sENVIRONMENT=web,worker -sMODULARIZE=1 -sEXPORT_NAME=createPdftohtml -sEXPORT_ES6=1 -sEXIT_RUNTIME=0 -sEXPORTED_RUNTIME_METHODS=FS,callMain -sINVOKE_RUN=0 -sSINGLE_FILE=${SINGLE_FILE}" \
    && emmake make pdftohtml -j$(nproc) \
    && cp utils/pdftohtml.js /build/libs/bin/pdftohtml.js \
    && rm -f utils/pdftohtml.js utils/pdftohtml.wasm \
    && emcmake cmake .. \
        -DCMAKE_EXE_LINKER_FLAGS="-sALLOW_MEMORY_GROWTH -sENVIRONMENT=web,worker -sMODULARIZE=1 -sEXPORT_NAME=createPdfinfo -sEXPORT_ES6=1 -sEXIT_RUNTIME=0 -sEXPORTED_RUNTIME_METHODS=FS,callMain -sINVOKE_RUN=0 -sSINGLE_FILE=${SINGLE_FILE}" \
    && emmake make pdfinfo -j$(nproc) \
    && cp utils/pdfinfo.js /build/libs/bin/pdfinfo.js \
    && cd /build/src && rm -rf poppler-21.04.0

# ============================================================================
# Stage 3: Package calibre Python code
# ============================================================================
FROM native-libs AS calibre-python-build

ARG SINGLE_FILE=1
ENV SINGLE_FILE=$SINGLE_FILE

ARG CALIBRE_REPO=https://github.com/kovidgoyal/calibre.git
ARG CALIBRE_REF=master
RUN git clone --depth 1 --branch "${CALIBRE_REF}" \
        --filter=blob:none --sparse \
        "${CALIBRE_REPO}" /build/src/calibre-source \
    && cd /build/src/calibre-source \
    && git sparse-checkout set src/calibre src/polyglot src/tinycss \
    && rm -rf /build/src/calibre-source/.git

COPY scripts/ /build/scripts/
COPY src/stubs/ /build/src/stubs/
COPY src/patches/ /build/src/patches/

RUN chmod +x /build/scripts/*.sh

RUN pip3 install --no-cache-dir odfpy defusedxml

RUN python3 /build/scripts/patch-calibre.py

RUN /build/scripts/build-calibre-extensions.sh

RUN /build/scripts/package-calibre.sh

# ============================================================================
# Stage 4: Build final WASM module
# ============================================================================
FROM calibre-python-build AS final-build

ARG SINGLE_FILE=1
ENV SINGLE_FILE=$SINGLE_FILE

COPY src/wrapper/ /build/src/wrapper/
COPY src/js/ /build/src/js/
COPY src/types/ /build/src/types/
COPY scripts/build-dist.mjs /build/scripts/build-dist.mjs
COPY package.json /build/package.json

RUN npm install --prefix /build --no-save esbuild

RUN /build/scripts/build-all.sh

# ============================================================================
# Stage 5: Export artifacts
# ============================================================================
FROM scratch AS export
COPY --from=final-build /build/dist/ /dist/
