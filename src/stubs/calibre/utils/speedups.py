"""Pure Python replacements for calibre.utils.speedups C extension."""
import os

class ReadOnlyFileBuffer:
    """A zero copy implementation of a file like object. Uses memoryviews for efficiency."""

    def __init__(self, raw, name=''):
        self.sz, self.mv = len(raw), (raw if isinstance(raw, memoryview) else memoryview(raw))
        self.pos = 0
        self.name = name

    def tell(self):
        return self.pos

    def read(self, n=None):
        if n is None:
            ans = self.mv[self.pos:]
            self.pos = self.sz
            return ans
        ans = self.mv[self.pos:self.pos + n]
        self.pos = min(self.pos + n, self.sz)
        return ans

    def seek(self, pos, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self.pos = pos
        elif whence == os.SEEK_END:
            self.pos = self.sz + pos
        else:
            self.pos += pos
        self.pos = max(0, min(self.pos, self.sz))
        return self.pos

    def seekable(self):
        return True

    def getvalue(self):
        return self.mv

    def close(self):
        pass
