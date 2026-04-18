#!/usr/bin/env bash
# ==========================================================================
# package-calibre.sh — Bundle the calibre source project into a zip archive
# that can be loaded into Pyodide's virtual filesystem.
#
# Uses the original calibre project (kovidgoyal/calibre) as the source for
# the conversion pipeline.
# ==========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
REFERENCE_DIR="${PROJECT_DIR}/src/calibre-source"
STUBS_DIR="${PROJECT_DIR}/src/stubs"
PKG_DIR="${PROJECT_DIR}/dist/calibre-python"
ZIP_OUT="${PROJECT_DIR}/dist/calibre-python.zip"

echo "=== Packaging calibre for WASM ==="
echo "Reference: ${REFERENCE_DIR}"
echo "Stubs:     ${STUBS_DIR}"
echo "Output:    ${ZIP_OUT}"

rm -rf "${PKG_DIR}"
mkdir -p "${PKG_DIR}"

# ------------------------------------------------------------------
# 1. Copy the calibre and polyglot packages from source
# ------------------------------------------------------------------
echo ""
echo "--- Copying calibre package ---"

if [ -d "${REFERENCE_DIR}/src/calibre" ]; then
    CALIBRE_SRC="${REFERENCE_DIR}/src/calibre"
elif [ -d "${REFERENCE_DIR}/calibre" ]; then
    CALIBRE_SRC="${REFERENCE_DIR}/calibre"
else
    echo "ERROR: calibre source not found in ${REFERENCE_DIR}"
    exit 1
fi

cp -r "${CALIBRE_SRC}" "${PKG_DIR}/calibre"

if [ -d "${REFERENCE_DIR}/src/polyglot" ]; then
    cp -r "${REFERENCE_DIR}/src/polyglot" "${PKG_DIR}/polyglot"
    echo "  Copied polyglot package"
elif [ -d "${REFERENCE_DIR}/polyglot" ]; then
    cp -r "${REFERENCE_DIR}/polyglot" "${PKG_DIR}/polyglot"
    echo "  Copied polyglot package"
fi

# Remove unnecessary files (compiled C extensions, tests, __pycache__, GUI)
find "${PKG_DIR}" -name '*.pyc' -delete
find "${PKG_DIR}" -name '*.pyo' -delete
find "${PKG_DIR}" -name '*.c' ! -name '*.py' -delete 2>/dev/null || true
find "${PKG_DIR}" -name '*.cpp' -delete 2>/dev/null || true
find "${PKG_DIR}" -name '*.h' -delete 2>/dev/null || true
find "${PKG_DIR}" -name '*.pyx' -delete 2>/dev/null || true
find "${PKG_DIR}" -name '*.so' -delete 2>/dev/null || true
find "${PKG_DIR}" -name '*.pyd' -delete 2>/dev/null || true
find "${PKG_DIR}" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "${PKG_DIR}" -type d -name 'tests' -exec rm -rf {} + 2>/dev/null || true
find "${PKG_DIR}" -type d -name 'test' -exec rm -rf {} + 2>/dev/null || true

# Remove large subdirectories not needed for ebook conversion
for dir in gui2 headless manual srv db; do
    if [ -d "${PKG_DIR}/calibre/${dir}" ]; then
        rm -rf "${PKG_DIR}/calibre/${dir}"
        echo "  Removed calibre/${dir}/"
    fi
done

echo "  Copied calibre package"

# ------------------------------------------------------------------
# 1b. Apply WASM patches
# ------------------------------------------------------------------
echo ""
echo "--- Applying WASM patches ---"
PATCH_FILE="${PROJECT_DIR}/src/patches/calibre-wasm.patch"
if [ -f "${PATCH_FILE}" ]; then
    patch -p0 --forward -d "${PKG_DIR}" -i "${PATCH_FILE}" || {
        if [ $? -eq 1 ]; then
            echo "  Patches already applied (skipped)"
        else
            echo "  ERROR: patch failed"
            exit 1
        fi
    }
    echo "  Applied ${PATCH_FILE}"
else
    echo "  WARNING: Patch file not found: ${PATCH_FILE}"
    echo "  Run 'python3 scripts/generate-patches.py' to generate it."
fi

# ------------------------------------------------------------------
# 2. Overlay WASM-compatible stubs
# ------------------------------------------------------------------
echo ""
echo "--- Overlaying WASM stubs ---"
stub_count=0
if [ -d "${STUBS_DIR}" ]; then
    for src_file in $(find "${STUBS_DIR}" -type f -not -path '*/__pycache__/*' -not -path '*/ebook_converter/*' -not -name '*.pyc'); do
        rel_path="${src_file#${STUBS_DIR}/}"
        dst_file="${PKG_DIR}/${rel_path}"
        mkdir -p "$(dirname "${dst_file}")"
        cp "${src_file}" "${dst_file}"
        stub_count=$((stub_count + 1))
        echo "  ${rel_path}"
    done
fi
echo "  Overlaid ${stub_count} stub files"

# ------------------------------------------------------------------
# 3. Bundle pure-Python dependencies not available via micropip
#    (odfpy for ODT support, defusedxml as odfpy dependency)
# ------------------------------------------------------------------
echo ""
echo "--- Bundling pure-Python dependencies ---"
dep_count=0

ODF_SRC="$(python3 -c "import odf, os; print(os.path.dirname(odf.__file__))" 2>/dev/null || true)"
if [ -n "${ODF_SRC}" ] && [ -d "${ODF_SRC}" ]; then
    cp -r "${ODF_SRC}" "${PKG_DIR}/odf"
    find "${PKG_DIR}/odf" -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    dep_count=$((dep_count + 1))
    echo "  odf (odfpy) — copied from ${ODF_SRC}"
else
    echo "  WARNING: odfpy not found — install with: pip install odfpy"
fi

DEFUSEDXML_SRC="$(python3 -c "import defusedxml, os; print(os.path.dirname(defusedxml.__file__))" 2>/dev/null || true)"
if [ -n "${DEFUSEDXML_SRC}" ] && [ -d "${DEFUSEDXML_SRC}" ]; then
    cp -r "${DEFUSEDXML_SRC}" "${PKG_DIR}/defusedxml"
    find "${PKG_DIR}/defusedxml" -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    dep_count=$((dep_count + 1))
    echo "  defusedxml — copied from ${DEFUSEDXML_SRC}"
else
    echo "  WARNING: defusedxml not found — install with: pip install defusedxml"
fi

echo "  Bundled ${dep_count} dependency packages"

# ------------------------------------------------------------------
# 4. Verify data files
# ------------------------------------------------------------------
echo ""
echo "--- Verifying data files ---"
if [ -d "${PKG_DIR}/calibre/data" ]; then
    data_count=$(find "${PKG_DIR}/calibre/data" -type f | wc -l)
    echo "  ${data_count} data files present"
else
    echo "  WARNING: No data directory found!"
fi

# ------------------------------------------------------------------
# 5. Create the zip archive
# ------------------------------------------------------------------
echo ""
echo "--- Creating ZIP archive ---"
mkdir -p "$(dirname "${ZIP_OUT}")"

cd "${PKG_DIR}"
file_count=0
zip -r -q "${ZIP_OUT}" . -x '*/__pycache__/*' '*.pyc'
file_count=$(unzip -l "${ZIP_OUT}" | tail -1 | awk '{print $2}')

zip_size=$(stat -c%s "${ZIP_OUT}" 2>/dev/null || stat -f%z "${ZIP_OUT}")
echo ""
echo "=== Package Complete ==="
echo "Files:    ${file_count}"
echo "Size:     ${zip_size} bytes ($((zip_size / 1024))KB)"
echo "Output:   ${ZIP_OUT}"
