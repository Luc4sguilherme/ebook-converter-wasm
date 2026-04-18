import sys, traceback as TB

DEBUG = 0
INFO = 1
WARN = 2
ERROR = 3

class Stream:
    def __init__(self, stream=None):
        self.stream = stream or sys.stderr
    def write(self, text):
        self.stream.write(text)
    def flush(self):
        self.stream.flush()

class ANSIStream(Stream):
    pass

class FileStream(Stream):
    def __init__(self, path=None):
        import io
        self._buf = io.StringIO()
        super().__init__(self._buf)
    @property
    def value(self):
        return self._buf.getvalue()

class HTMLStream(Stream):
    color = None
    def __init__(self):
        super().__init__(None)
        self.data = []
    def write(self, text):
        self.data.append(text)
    @property
    def html(self):
        return ''.join(self.data)

class Log:
    DEBUG = DEBUG
    INFO = INFO
    WARN = WARN
    ERROR = ERROR
    def __init__(self, level=INFO):
        self.filter_level = level
        self.outputs = [Stream()]
    def prints(self, level, *args, **kw):
        if level < self.filter_level:
            return
        sep = kw.get('sep', ' ')
        end = kw.get('end', '\n')
        text = sep.join(str(a) for a in args) + end
        for o in self.outputs:
            o.write(text)
            o.flush()
    def info(self, *args, **kw):
        self.prints(INFO, *args, **kw)
    def warn(self, *args, **kw):
        self.prints(WARN, *args, **kw)
    warning = warn
    def error(self, *args, **kw):
        self.prints(ERROR, *args, **kw)
    def debug(self, *args, **kw):
        self.prints(DEBUG, *args, **kw)
    def exception(self, *args, **kw):
        self.prints(ERROR, *args, **kw)
        self.prints(ERROR, TB.format_exc())
    def __call__(self, *args, **kw):
        self.info(*args, **kw)

class DevNull(Log):
    def prints(self, *a, **kw):
        pass

default_log = Log()
