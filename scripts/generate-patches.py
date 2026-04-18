#!/usr/bin/env python3
"""
Generate a unified .patch file from the inline WASM patches.

Clones calibre, copies the relevant source, applies all inline patches,
then generates a unified diff between the original and patched copies.

The result is saved to src/patches/calibre-wasm.patch and can be applied
by patch-calibre.py at build time using `patch -p0`.

Usage:
    python3 scripts/generate-patches.py
"""
import os
import re
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
PATCHES_DIR = os.path.join(PROJECT_DIR, 'src', 'patches')
PATCH_FILE = os.path.join(PATCHES_DIR, 'calibre-wasm.patch')

WORK_BASE = '/tmp/calibre-patchgen'
ORIGINAL_DIR = os.path.join(WORK_BASE, 'original')
PATCHED_DIR = os.path.join(WORK_BASE, 'patched')
CLONE_DIR = '/tmp/calibre-clone'

DOCKER_SOURCE_DIR = os.path.join(PROJECT_DIR, 'src', 'calibre-source')

CALIBRE_REPO = 'https://github.com/kovidgoyal/calibre.git'
CALIBRE_REF = 'master'

COPY_IGNORE = shutil.ignore_patterns(
    '__pycache__', '*.pyc', '*.pyo', '*.so', '*.pyd',
    'tests', 'test', 'gui2', 'gui_launch.py',
    'linux.py', 'headless', 'manual',
)

def find_or_clone_calibre():
    """Find pre-cloned calibre source or clone from upstream."""
    for candidate in [DOCKER_SOURCE_DIR, CLONE_DIR]:
        src_calibre = os.path.join(candidate, 'src', 'calibre')
        if os.path.isdir(src_calibre):
            print(f"Using existing calibre source at {candidate}")
            return candidate

    if os.path.exists(CLONE_DIR):
        shutil.rmtree(CLONE_DIR)

    print(f"Cloning {CALIBRE_REPO} (ref: {CALIBRE_REF})...")
    subprocess.check_call([
        'git', 'clone', '--depth', '1', '--branch', CALIBRE_REF,
        '--filter=blob:none', '--sparse',
        CALIBRE_REPO, CLONE_DIR
    ])
    subprocess.check_call(
        ['git', 'sparse-checkout', 'set', 'src/calibre', 'src/polyglot'],
        cwd=CLONE_DIR
    )
    return CLONE_DIR

def copy_calibre_source(reference_dir, dest_dir):
    """Copy calibre + polyglot source to dest_dir/calibre and dest_dir/polyglot."""
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)

    src_calibre = os.path.join(reference_dir, 'src', 'calibre')
    dst_calibre = os.path.join(dest_dir, 'calibre')
    shutil.copytree(src_calibre, dst_calibre, ignore=COPY_IGNORE)

    for root, dirs, files in os.walk(dst_calibre):
        for f in files:
            if f.endswith(('.c', '.cpp', '.h', '.pyx')) and not f.endswith('.py'):
                os.remove(os.path.join(root, f))
        dirs[:] = [d for d in dirs if d not in (
            '__pycache__', 'tests', 'test', 'gui2', 'headless', 'manual',
        )]

    for unneeded in ['gui2', 'headless', 'manual', 'srv', 'db', 'gui_launch.py']:
        path = os.path.join(dst_calibre, unneeded)
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.isfile(path):
            os.remove(path)

    src_polyglot = os.path.join(reference_dir, 'src', 'polyglot')
    dst_polyglot = os.path.join(dest_dir, 'polyglot')
    if os.path.isdir(src_polyglot):
        shutil.copytree(src_polyglot, dst_polyglot,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))

PATCHES = [
    ('calibre/customize/__init__.py', 'callable:_add_future_annotations'),
    ('calibre/ebooks/lit/lzx.py', 'callable:_guard_calibre_extensions_import'),
    ('calibre/ebooks/lit/reader.py', 'callable:_guard_calibre_extensions_import'),
    ('calibre/ebooks/lit/writer.py', 'callable:_guard_calibre_extensions_import'),
    ('calibre/ebooks/docx/writer/images.py',
     "fname += os.extsep + fmt.lower()",
     "fname += os.extsep + (fmt or 'png').lower()"),
    ('calibre/ebooks/oeb/transforms/rasterize.py', 'callable:_rasterize_qt_patch'),
    ('calibre/ebooks/oeb/transforms/rasterize.py', 'callable:_rasterize_init_attrs_patch'),
    ('calibre/ebooks/conversion/plugins/snb_output.py',
     'img.width(), img.height()',
     'img.width, img.height'),
    ('calibre/utils/zipfile.py', 'callable:_zipfile_disable_threading'),
    ('calibre/ebooks/docx/writer/styles.py',
     'return parent.makeelement(self.w(name), **{self.w(k):v for k, v in attrs.items()})',
     'return parent.makeelement(self.w(name), **{self.w(k):v for k, v in attrs.items() if v is not None})'),
    ('calibre/ebooks/mobi/mobiml.py',
     "                if cssdict[prop] != 'auto':",
     "                if cssdict.get(prop, 'auto') != 'auto':"),
    ('calibre/ebooks/docx/writer/links.py', 'callable:_links_page_break_guard'),
    ('calibre/ebooks/docx/writer/images.py', 'callable:_images_page_break_guard'),
    ('calibre/ebooks/pdf/reflow.py',
     'if self.pages[head_page].texts \\',
     'if head_page < len(self.pages) and self.pages[head_page].texts \\'),
]

def apply_inline_patches(work_dir):
    """Apply all inline patches to the work directory."""
    callable_map = {
        '_add_future_annotations': _add_future_annotations_fn,
        '_guard_calibre_extensions_import': _guard_calibre_extensions_import_fn,
        '_rasterize_qt_patch': _rasterize_qt_patch_fn,
        '_rasterize_init_attrs_patch': _rasterize_init_attrs_patch_fn,
        '_zipfile_disable_threading': _zipfile_disable_threading_fn,
        '_links_page_break_guard': _links_page_break_guard_fn,
        '_images_page_break_guard': _images_page_break_guard_fn,
    }

    for entry in PATCHES:
        filepath = os.path.join(work_dir, entry[0])
        if not os.path.isfile(filepath):
            print(f'  SKIP (not found): {entry[0]}')
            continue

        with open(filepath, 'r') as f:
            content = f.read()

        if isinstance(entry[1], str) and entry[1].startswith('callable:'):
            fn_name = entry[1].split(':', 1)[1]
            fn = callable_map[fn_name]
            new_content = fn(content)
            if new_content != content:
                with open(filepath, 'w') as f:
                    f.write(new_content)
                print(f'  PATCHED: {entry[0]}')
            else:
                print(f'  SKIP (already patched): {entry[0]}')
        else:
            old_str, new_str = entry[1], entry[2]
            if old_str not in content:
                print(f'  SKIP (already patched or pattern changed): {entry[0]}')
                continue
            content = content.replace(old_str, new_str, 1)
            with open(filepath, 'w') as f:
                f.write(content)
            print(f'  PATCHED: {entry[0]}')

def _add_future_annotations_fn(content):
    """Add 'from __future__ import annotations' to make type annotations lazy."""
    if 'from __future__ import annotations' in content:
        return content
    return 'from __future__ import annotations\n' + content

def _guard_calibre_extensions_import_fn(content):
    """Wrap calibre_extensions imports in try/except."""
    if 'calibre_extensions' not in content:
        return content

    pattern = r'^(from calibre_extensions import .+)$'

    def replacer(m):
        line = m.group(1)
        indent = len(line) - len(line.lstrip())
        indent_str = ' ' * indent
        imports = line.split('import')[1].strip()
        names = [n.strip() for n in imports.split(',')]
        nones = '\n'.join(f'{indent_str}    {n} = None' for n in names)
        return f'{indent_str}try:\n{indent_str}    {line.strip()}\n{indent_str}except ImportError:\n{nones}'

    return re.sub(pattern, replacer, content, flags=re.MULTILINE)

def _rasterize_qt_patch_fn(content):
    """Add HAS_QT guard to rasterize.py."""
    content = re.sub(
        r'^from qt\.core import [^\n]+\n', '', content, count=1, flags=re.MULTILINE
    )

    if 'HAS_QT' in content:
        return content

    qt_import = (
        "\n\ntry:\n"
        "    from qt.core import (QByteArray, QSvgRenderer, QImage, QPainter,\n"
        "                          QColor, QBuffer, QIODevice, Qt)\n"
        "    HAS_QT = True\n"
        "except ImportError:\n"
        "    HAS_QT = False\n"
    )

    if "\nIMAGE_TAGS = {" in content:
        content = content.replace(
            "\nIMAGE_TAGS = {",
            qt_import + "\nIMAGE_TAGS = {",
        )
    elif "IMAGE_TAGS" not in content:
        content = qt_import + "\n" + content

    content = content.replace(
        "        from calibre.gui2 import must_use_qt\n        must_use_qt()",
        "        try:\n"
        "            from calibre.gui2 import must_use_qt\n"
        "            must_use_qt()\n"
        "        except ImportError:\n"
        "            pass",
    )

    if "    def __call__(self, oeb, context):" in content:
        content = content.replace(
            "    def __call__(self, oeb, context):\n        oeb.logger.info('Rasterizing SVG images...')",
            "    def __call__(self, oeb, context):\n"
            "        if not HAS_QT:\n"
            "            self.stylizer_cache = {}\n"
            "            self.oeb = oeb\n"
            "            self.opts = context\n"
            "            self.profile = context.dest\n"
            "            self.images = {}\n"
            "            self.svg_originals = {}\n"
            "            oeb.logger.warning('Qt not available, skipping SVG rasterization')\n"
            "            return\n"
            "        oeb.logger.info('Rasterizing SVG images...')",
        )

    if "def rasterize_svg(self," in content:
        content = content.replace(
            "    def rasterize_svg(self, elem, width=0, height=0, format='PNG'):\n        view_box",
            "    def rasterize_svg(self, elem, width=0, height=0, format='PNG'):\n"
            "        if not HAS_QT:\n"
            "            self.oeb.logger.warning('Qt not available, skipping SVG rasterization')\n"
            "            return b''\n"
            "        view_box",
        )

    if "def rasterize_external(self," in content:
        content = content.replace(
            "    def rasterize_external(self, elem, style, item, svgitem):\n        width = style",
            "    def rasterize_external(self, elem, style, item, svgitem):\n"
            "        if not HAS_QT:\n"
            "            self.oeb.logger.warning('Qt not available, skipping external SVG rasterization')\n"
            "            return\n"
            "        width = style",
        )

    return content

def _rasterize_init_attrs_patch_fn(content):
    """Ensure SVGRasterizer.__init__ sets attrs before HAS_QT check,
    and guard stylizer() against None data."""
    init_pattern = (
        r"(    def __init__\(self, base_css=''\):\n)"
        r"(        if not HAS_QT:\n"
        r"            .*\n"
        r"            return\n)"
    )
    init_repl = (
        r"\1"
        "        self.base_css = base_css\n"
        "        self.images = {}\n"
        r"\2"
    )
    content = re.sub(init_pattern, init_repl, content)

    content = content.replace(
        "stylizer = Stylizer(data,",
        "if data is None:\n"
        "                    continue\n"
        "                stylizer = Stylizer(data,",
    )

    return content

def _zipfile_disable_threading_fn(content):
    """Disable ThreadPoolExecutor and Lock in calibre/utils/zipfile.py."""
    content = content.replace(
        'from concurrent.futures import ThreadPoolExecutor',
        '# ThreadPoolExecutor disabled for WASM',
    )
    content = content.replace(
        'from threading import Lock',
        '# threading.Lock disabled for WASM\n'
        'class Lock:\n'
        '    def acquire(self): pass\n'
        '    def release(self): pass\n'
        '    def __enter__(self): return self\n'
        '    def __exit__(self, *a): pass',
    )
    content = content.replace(
        "        with ThreadPoolExecutor(max_workers=12, thread_name_prefix='ZipFile-') as e:\n"
        "            tuple(e.map(do_one, args))",
        "        for a in args:\n"
        "            do_one(a)",
    )
    return content

def _links_page_break_guard_fn(content):
    """Guard pageBreakBefore xpath result in docx/writer/links.py."""
    content = content.replace(
        "        pbb = body[0].xpath('//*[local-name()=\"pageBreakBefore\"]')[0]\n"
        "        pbb.set('{{{}}}val'.format(self.namespace.namespaces['w']), 'on')",
        "        pbb_list = body[0].xpath('//*[local-name()=\"pageBreakBefore\"]')\n"
        "        if pbb_list:\n"
        "            pbb_list[0].set('{{{}}}val'.format(self.namespace.namespaces['w']), 'on')",
    )
    return content

def _images_page_break_guard_fn(content):
    """Guard pageBreakBefore xpath result in docx/writer/images.py."""
    content = content.replace(
        "        pbb = body[0].xpath('//*[local-name()=\"pageBreakBefore\"]')[0]\n"
        "        pbb.set('{{{}}}val'.format(namespaces['w']), 'on')",
        "        pbb_list = body[0].xpath('//*[local-name()=\"pageBreakBefore\"]')\n"
        "        if pbb_list:\n"
        "            pbb_list[0].set('{{{}}}val'.format(namespaces['w']), 'on')",
    )
    return content

def generate_patch_file():
    """Generate src/patches/calibre-wasm.patch from inline patches."""
    reference_dir = find_or_clone_calibre()
    print(f"Using calibre source: {reference_dir}")

    print("Copying original source...")
    copy_calibre_source(reference_dir, ORIGINAL_DIR)
    print("Copying source for patching...")
    copy_calibre_source(reference_dir, PATCHED_DIR)

    print("\nApplying inline patches...")
    apply_inline_patches(PATCHED_DIR)

    print(f"\nGenerating unified diff...")
    result = subprocess.run(
        ['diff', '-ruN', 'original', 'patched'],
        capture_output=True, text=True,
        cwd=WORK_BASE
    )

    if result.returncode == 2:
        print(f"ERROR: diff failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    patch_content = result.stdout
    if not patch_content:
        print("WARNING: No differences found — patches may already be applied or patterns changed.")
        sys.exit(1)

    patch_content = patch_content.replace('--- original/', '--- ')
    patch_content = patch_content.replace('+++ patched/', '+++ ')

    os.makedirs(PATCHES_DIR, exist_ok=True)
    with open(PATCH_FILE, 'w') as f:
        f.write(patch_content)

    lines = patch_content.count('\n')
    print(f"\nGenerated {PATCH_FILE}")
    print(f"  {lines} lines")

    shutil.rmtree(WORK_BASE, ignore_errors=True)
    print("Done!")

if __name__ == '__main__':
    generate_patch_file()
