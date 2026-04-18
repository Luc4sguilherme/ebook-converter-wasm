"""
WASM-compatible pkg_resources stub.

Provides resource_filename() that resolves paths relative to the
calibre package location in the virtual filesystem.
"""
import os
import sys

def resource_filename(package_name, resource_name):
    """Resolve a resource path relative to a package.

    In WASM, packages are extracted to known paths in the virtual FS.
    """

    if package_name in sys.modules:
        mod = sys.modules[package_name]
        if hasattr(mod, '__file__') and mod.__file__:
            pkg_dir = os.path.dirname(mod.__file__)
            return os.path.join(pkg_dir, resource_name)

    for path in sys.path:
        candidate = os.path.join(path, package_name.replace('.', os.sep), resource_name)
        if os.path.exists(candidate):
            return candidate

    return os.path.join(package_name.replace('.', os.sep), resource_name)

def resource_string(package_name, resource_name):
    """Read a resource as bytes."""
    path = resource_filename(package_name, resource_name)
    with open(path, 'rb') as f:
        return f.read()

def resource_stream(package_name, resource_name):
    """Return a file-like object for a resource."""
    import io
    path = resource_filename(package_name, resource_name)
    return open(path, 'rb')

def resource_isdir(package_name, resource_name):
    """Check if resource is a directory."""
    path = resource_filename(package_name, resource_name)
    return os.path.isdir(path)

def resource_listdir(package_name, resource_name):
    """List contents of a resource directory."""
    path = resource_filename(package_name, resource_name)
    if os.path.isdir(path):
        return os.listdir(path)
    return []
