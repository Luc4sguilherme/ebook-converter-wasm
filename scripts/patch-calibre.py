#!/usr/bin/env python3
"""
Patch the calibre source with WASM-compatible stubs.

Clones the original calibre project (kovidgoyal/calibre), extracts the
conversion pipeline, applies WASM patches from src/patches/calibre-wasm.patch,
overlays WASM stubs, and packages into calibre-python.zip.

To regenerate the .patch file, run: python3 scripts/generate-patches.py

Usage:
    python3 scripts/patch-calibre.py
"""
import os
import sys
import zipfile
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DIST_DIR = os.path.join(PROJECT_DIR, 'dist')
ZIP_PATH = os.path.join(DIST_DIR, 'calibre-python.zip')
STUBS_DIR = os.path.join(PROJECT_DIR, 'src', 'stubs')
PATCHES_DIR = os.path.join(PROJECT_DIR, 'src', 'patches')
PATCH_FILE = os.path.join(PATCHES_DIR, 'calibre-wasm.patch')
WORK_DIR = '/tmp/calibre-patch'
CLONE_DIR = '/tmp/calibre-clone'

DOCKER_SOURCE_DIR = os.path.join(PROJECT_DIR, 'src', 'calibre-source')

CALIBRE_REPO = 'https://github.com/kovidgoyal/calibre.git'
CALIBRE_REF = 'master'

def find_or_clone_calibre():
    """Find pre-cloned calibre source or clone from upstream."""
    import subprocess

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
        ['git', 'sparse-checkout', 'set', 'src/calibre', 'src/polyglot', 'src/tinycss'],
        cwd=CLONE_DIR
    )

    return CLONE_DIR

def package_from_calibre():
    """Clone, patch, and package the calibre project with WASM stubs."""
    reference_dir = find_or_clone_calibre()
    print(f"Packaging from calibre source: {reference_dir}")

    if os.path.exists(WORK_DIR):
        shutil.rmtree(WORK_DIR)
    os.makedirs(WORK_DIR)

    src_calibre = os.path.join(reference_dir, 'src', 'calibre')
    dst_calibre = os.path.join(WORK_DIR, 'calibre')

    if not os.path.isdir(src_calibre):
        print(f"ERROR: calibre source not found at {src_calibre}")
        sys.exit(1)

    shutil.copytree(src_calibre, dst_calibre,
                    ignore=shutil.ignore_patterns(
                        '__pycache__', '*.pyc', '*.pyo', '*.so', '*.pyd',
                        'tests', 'test', 'gui2', 'gui_launch.py',
                        'linux.py', 'headless', 'manual',
                    ))
    print(f"  Copied calibre package")

    src_polyglot = os.path.join(reference_dir, 'src', 'polyglot')
    dst_polyglot = os.path.join(WORK_DIR, 'polyglot')

    if os.path.isdir(src_polyglot):
        shutil.copytree(src_polyglot, dst_polyglot,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
        print(f"  Copied polyglot package")
    else:
        print(f"  WARNING: polyglot not found at {src_polyglot}")

    src_tinycss = os.path.join(reference_dir, 'src', 'tinycss')
    dst_tinycss = os.path.join(WORK_DIR, 'tinycss')

    if os.path.isdir(src_tinycss):
        shutil.copytree(src_tinycss, dst_tinycss,
                        ignore=shutil.ignore_patterns(
                            '__pycache__', '*.pyc', '*.pyo', '*.c', '*.so',
                            'tests',
                        ))
        print(f"  Copied tinycss package")
    else:
        print(f"  WARNING: tinycss not found at {src_tinycss}")

    for root, dirs, files in os.walk(dst_calibre):
        for f in files:
            if f.endswith(('.c', '.cpp', '.h', '.pyx')) and not f.endswith('.py'):
                fpath = os.path.join(root, f)
                os.remove(fpath)

        dirs[:] = [d for d in dirs if d not in (
            '__pycache__', 'tests', 'test', 'gui2', 'headless', 'manual',
        )]

    for unneeded in ['gui2', 'headless', 'manual', 'srv', 'db',
                     'gui_launch.py']:
        path = os.path.join(dst_calibre, unneeded)
        if os.path.isdir(path):
            shutil.rmtree(path)
            print(f"  Removed {unneeded}/")
        elif os.path.isfile(path):
            os.remove(path)
            print(f"  Removed {unneeded}")

    apply_wasm_patches(WORK_DIR)

    overlay_stubs(WORK_DIR, STUBS_DIR)

    bundle_python_deps(WORK_DIR)

    build_zip(WORK_DIR, ZIP_PATH)

def apply_wasm_patches(work_dir):
    """Apply WASM-specific patches from the .patch file."""
    print(f"\nApplying WASM patches...")

    if not os.path.isfile(PATCH_FILE):
        print(f"ERROR: Patch file not found: {PATCH_FILE}")
        print(f"Run 'python3 scripts/generate-patches.py' to generate it.")
        sys.exit(1)

    import subprocess
    result = subprocess.run(
        ['patch', '-p0', '--forward', '-i', PATCH_FILE],
        cwd=work_dir,
        capture_output=True, text=True,
    )

    if result.returncode != 0:

        if 'previously applied' in result.stdout or 'Reversed' in result.stdout:
            print(f"  Patches already applied (skipped)")
        else:
            print(f"  stdout: {result.stdout}")
            print(f"  stderr: {result.stderr}")
            print(f"ERROR: patch failed (exit code {result.returncode})")
            sys.exit(1)
    else:
        print(f"  Applied {PATCH_FILE}")

def bundle_python_deps(work_dir):
    """Bundle pure-Python dependencies (odfpy, defusedxml) into work_dir."""
    print(f"\nBundling pure-Python dependencies...")
    dep_count = 0

    for pkg_name in ['odf', 'defusedxml']:
        try:
            mod = __import__(pkg_name)
            src_dir = os.path.dirname(mod.__file__)
        except ImportError:
            print(f"  WARNING: {pkg_name} not installed (pip install {'odfpy' if pkg_name == 'odf' else pkg_name})")
            continue

        dst_dir = os.path.join(work_dir, pkg_name)
        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
        dep_count += 1
        print(f"  {pkg_name} — copied from {src_dir}")

    print(f"  Bundled {dep_count} dependency packages")

def overlay_stubs(work_dir, stubs_dir):
    """Overlay WASM stubs onto the work directory."""
    print(f"\nOverlaying stubs from {stubs_dir}...")
    stub_count = 0

    if not os.path.isdir(stubs_dir):
        print(f"  No stubs directory found at {stubs_dir}")
        return

    for root, dirs, files in os.walk(stubs_dir):

        dirs[:] = [d for d in dirs if d not in ('__pycache__', 'ebook_converter')]
        for fname in sorted(files):
            if fname.endswith('.pyc'):
                continue
            src_path = os.path.join(root, fname)
            rel_path = os.path.relpath(src_path, stubs_dir)
            dst_path = os.path.join(work_dir, rel_path)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)
            stub_count += 1
            print(f"  {rel_path}")

    print(f"\n  Overlaid {stub_count} stub files.")

def build_zip(work_dir, zip_path):
    """Build zip archive from work directory."""
    print(f"\nBuilding {zip_path}...")

    os.makedirs(os.path.dirname(zip_path), exist_ok=True)

    file_count = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(work_dir):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for fname in sorted(files):
                if fname.endswith('.pyc'):
                    continue
                fullpath = os.path.join(root, fname)
                arcname = os.path.relpath(fullpath, work_dir)
                zf.write(fullpath, arcname)
                file_count += 1

    new_size = os.path.getsize(zip_path)
    print(f"  Files: {file_count}")
    print(f"  Size:  {new_size:,} bytes ({new_size // 1024}KB)")
    print("\nDone!")

if __name__ == '__main__':
    package_from_calibre()
