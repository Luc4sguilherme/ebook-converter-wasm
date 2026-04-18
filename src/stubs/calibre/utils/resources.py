"""
WASM-compatible replacement for calibre.utils.resources

Resolves paths within the WASM virtual filesystem.
"""
import os
import sys

user_dir = '/tmp/calibre-config/resources'

class PathResolver:

    def __init__(self):

        self.default_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'data')
        sys.resources_location = self.default_path
        self.locations = [self.default_path]
        self.cache = {}
        self.using_develop_from = False
        self.user_path = None

        if os.path.isdir(user_dir):
            self.locations.insert(0, user_dir)
            self.user_path = user_dir

    def __call__(self, path, allow_user_override=True, data=False):
        path = path.replace(os.sep, '/')
        key = (path, allow_user_override)
        ans = self.cache.get(key, None)
        if ans is None:
            for base in self.locations:
                if not allow_user_override and base == self.user_path:
                    continue
                fpath = os.path.join(base, *path.split('/'))
                if os.path.exists(fpath):
                    ans = fpath
                    break
            if ans is None:
                ans = os.path.join(self.default_path, *path.split('/'))
            self.cache[key] = ans
        if data:
            try:
                with open(ans, 'rb') as f:
                    return f.read()
            except (OSError, IOError):
                return b''
        return ans

_resolver = PathResolver()
get_path = _resolver
get_image_path = _resolver
