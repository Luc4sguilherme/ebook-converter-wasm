#!/usr/bin/env bash
# ==========================================================================
# build-native-libs.sh — Compile Calibre's C/C++ dependencies to WASM
#
# This script is run inside the Docker container where Emscripten is already
# available. Libraries are installed into /build/libs.
# ==========================================================================
set -euo pipefail

PREFIX="/build/libs"
SRC="/build/src"
JOBS=$(nproc)

export CFLAGS="-O2 -fPIC"
export CXXFLAGS="-O2 -fPIC"

echo "=== Building native libraries for WASM ==="
echo "PREFIX=${PREFIX}"
echo "JOBS=${JOBS}"

mkdir -p "${PREFIX}/lib" "${PREFIX}/include"

# ------------------------------------------------------------------
# zlib
# ------------------------------------------------------------------
build_zlib() {
    echo ">>> Building zlib..."
    cd "${SRC}"
    if [ ! -d zlib-1.3.2 ]; then
        curl -fsSL https://github.com/madler/zlib/releases/download/v1.3.2/zlib-1.3.2.tar.gz | tar xz
    fi
    cd zlib-1.3.2
    emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_C_FLAGS="${CFLAGS}" \
        -DBUILD_SHARED_LIBS=OFF
    cmake --build build -j${JOBS}
    cmake --install build
    echo "<<< zlib done"
}

# ------------------------------------------------------------------
# libxml2
# ------------------------------------------------------------------
build_libxml2() {
    echo ">>> Building libxml2..."
    cd "${SRC}"
    if [ ! -d libxml2-v2.12.6 ]; then
        curl -fsSL https://gitlab.gnome.org/GNOME/libxml2/-/archive/v2.12.6/libxml2-v2.12.6.tar.gz | tar xz
    fi
    cd libxml2-v2.12.6
    emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_C_FLAGS="${CFLAGS}" \
        -DLIBXML2_WITH_PYTHON=OFF \
        -DLIBXML2_WITH_LZMA=OFF \
        -DLIBXML2_WITH_ZLIB=ON \
        -DLIBXML2_WITH_ICU=OFF \
        -DLIBXML2_WITH_THREADS=OFF \
        -DLIBXML2_WITH_HTTP=OFF \
        -DLIBXML2_WITH_FTP=OFF \
        -DBUILD_SHARED_LIBS=OFF \
        -DZLIB_LIBRARY="${PREFIX}/lib/libz.a" \
        -DZLIB_INCLUDE_DIR="${PREFIX}/include"
    cmake --build build -j${JOBS}
    cmake --install build
    echo "<<< libxml2 done"
}

# ------------------------------------------------------------------
# libxslt
# ------------------------------------------------------------------
build_libxslt() {
    echo ">>> Building libxslt..."
    cd "${SRC}"
    if [ ! -d libxslt-v1.1.39 ]; then
        curl -fsSL https://gitlab.gnome.org/GNOME/libxslt/-/archive/v1.1.39/libxslt-v1.1.39.tar.gz | tar xz
    fi
    cd libxslt-v1.1.39
    emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_C_FLAGS="${CFLAGS}" \
        -DLIBXSLT_WITH_PYTHON=OFF \
        -DLIBXSLT_WITH_CRYPTO=OFF \
        -DBUILD_SHARED_LIBS=OFF \
        -DCMAKE_PREFIX_PATH="${PREFIX}"
    cmake --build build -j${JOBS}
    cmake --install build
    echo "<<< libxslt done"
}

# ------------------------------------------------------------------
# libjpeg-turbo
# ------------------------------------------------------------------
build_libjpeg() {
    echo ">>> Building libjpeg-turbo..."
    cd "${SRC}"
    if [ ! -d libjpeg-turbo-3.0.2 ]; then
        curl -fsSL https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/3.0.2/libjpeg-turbo-3.0.2.tar.gz | tar xz
    fi
    cd libjpeg-turbo-3.0.2
    emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_C_FLAGS="${CFLAGS}" \
        -DWITH_SIMD=OFF \
        -DWITH_TURBOJPEG=OFF \
        -DENABLE_SHARED=OFF \
        -DENABLE_STATIC=ON
    cmake --build build -j${JOBS}
    cmake --install build
    echo "<<< libjpeg-turbo done"
}

# ------------------------------------------------------------------
# libpng
# ------------------------------------------------------------------
build_libpng() {
    echo ">>> Building libpng..."
    cd "${SRC}"
    if [ ! -d libpng-1.6.43 ]; then
        curl -fsSL https://github.com/pnggroup/libpng/archive/refs/tags/v1.6.43.tar.gz | tar xz
    fi
    cd libpng-1.6.43
    emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_C_FLAGS="${CFLAGS}" \
        -DPNG_SHARED=OFF \
        -DPNG_STATIC=ON \
        -DPNG_TESTS=OFF \
        -DPNG_HARDWARE_OPTIMIZATIONS=OFF \
        -DZLIB_LIBRARY="${PREFIX}/lib/libz.a" \
        -DZLIB_INCLUDE_DIR="${PREFIX}/include"
    cmake --build build -j${JOBS}
    cmake --install build
    echo "<<< libpng done"
}

# ------------------------------------------------------------------
# FreeType
# ------------------------------------------------------------------
build_freetype() {
    echo ">>> Building FreeType..."
    cd "${SRC}"
    if [ ! -d freetype-VER-2-13-2 ]; then
        curl -fsSL https://github.com/freetype/freetype/archive/refs/tags/VER-2-13-2.tar.gz | tar xz
    fi
    cd freetype-VER-2-13-2
    emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_C_FLAGS="${CFLAGS}" \
        -DBUILD_SHARED_LIBS=OFF \
        -DFT_DISABLE_BROTLI=ON \
        -DFT_DISABLE_HARFBUZZ=ON \
        -DFT_DISABLE_BZIP2=ON \
        -DZLIB_LIBRARY="${PREFIX}/lib/libz.a" \
        -DZLIB_INCLUDE_DIR="${PREFIX}/include" \
        -DPNG_LIBRARY="${PREFIX}/lib/libpng16.a" \
        -DPNG_PNG_INCLUDE_DIR="${PREFIX}/include"
    cmake --build build -j${JOBS}
    cmake --install build
    echo "<<< FreeType done"
}

# ------------------------------------------------------------------
# hunspell
# ------------------------------------------------------------------
build_hunspell() {
    echo ">>> Building hunspell..."
    cd "${SRC}"
    if [ ! -d hunspell-1.7.2 ]; then
        curl -fsSL https://github.com/hunspell/hunspell/releases/download/v1.7.2/hunspell-1.7.2.tar.gz | tar xz
    fi
    cd hunspell-1.7.2
    # Update config.sub/config.guess for wasm32 support
    curl -fsSL 'https://git.savannah.gnu.org/cgit/config.git/plain/config.sub' > config.sub
    curl -fsSL 'https://git.savannah.gnu.org/cgit/config.git/plain/config.guess' > config.guess
    emconfigure ./configure \
        --prefix="${PREFIX}" \
        --host=wasm32-unknown-emscripten \
        --enable-static \
        --disable-shared \
        --with-ui=no \
        --with-readline=no \
        CXXFLAGS="${CXXFLAGS}"
    emmake make -j${JOBS}
    emmake make install
    echo "<<< hunspell done"
}

# ------------------------------------------------------------------
# uchardet
# ------------------------------------------------------------------
build_uchardet() {
    echo ">>> Building uchardet..."
    cd "${SRC}"
    if [ ! -d uchardet-v0.0.8 ]; then
        curl -fsSL https://gitlab.freedesktop.org/uchardet/uchardet/-/archive/v0.0.8/uchardet-v0.0.8.tar.gz | tar xz
    fi
    cd uchardet-v0.0.8
    emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_CXX_FLAGS="${CXXFLAGS}" \
        -DBUILD_BINARY=OFF \
        -DBUILD_SHARED_LIBS=OFF
    cmake --build build -j${JOBS}
    cmake --install build
    echo "<<< uchardet done"
}

# ------------------------------------------------------------------
# libwebp
# ------------------------------------------------------------------
build_libwebp() {
    echo ">>> Building libwebp..."
    cd "${SRC}"
    if [ ! -d libwebp-1.3.2 ]; then
        curl -fsSL https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-1.3.2.tar.gz | tar xz
    fi
    cd libwebp-1.3.2
    emcmake cmake -B build \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_C_FLAGS="${CFLAGS}" \
        -DBUILD_SHARED_LIBS=OFF \
        -DWEBP_BUILD_ANIM_UTILS=OFF \
        -DWEBP_BUILD_CWEBP=OFF \
        -DWEBP_BUILD_DWEBP=OFF \
        -DWEBP_BUILD_GIF2WEBP=OFF \
        -DWEBP_BUILD_IMG2WEBP=OFF \
        -DWEBP_BUILD_VWEBP=OFF \
        -DWEBP_BUILD_WEBPMUX=OFF \
        -DWEBP_BUILD_EXTRAS=OFF \
        -DWEBP_BUILD_WEBPINFO=OFF
    cmake --build build -j${JOBS}
    cmake --install build
    echo "<<< libwebp done"
}

# ------------------------------------------------------------------
# chmlib
# ------------------------------------------------------------------
build_chmlib() {
    echo ">>> Building chmlib..."
    cd "${SRC}"
    if [ ! -d CHMLib-master ]; then
        curl -fsSL https://github.com/jedwing/CHMLib/archive/refs/heads/master.tar.gz | tar xz
    fi
    cd CHMLib-master/src
    emcc ${CFLAGS} -I. -c chm_lib.c -o chm_lib.o
    emcc ${CFLAGS} -I. -c lzx.c -o lzx.o
    emar rcs "${PREFIX}/lib/libchm.a" chm_lib.o lzx.o
    cp chm_lib.h "${PREFIX}/include/"
    echo "<<< chmlib done"
}

build_zlib
build_libjpeg
build_libpng
build_libxml2
build_libxslt
build_freetype
build_hunspell
build_uchardet
build_libwebp
build_chmlib

echo ""
echo "=== All native libraries built ==="
echo "Installed to: ${PREFIX}"
ls -la "${PREFIX}/lib/"
