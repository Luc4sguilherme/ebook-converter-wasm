from calibre.customize.profiles import (
    InputProfile, OutputProfile,
    input_profiles as _input_profile_classes, output_profiles as _output_profile_classes
)
from calibre.customize.conversion import InputFormatPlugin, OutputFormatPlugin
import importlib
import pkgutil

_ip = [cls(None) for cls in _input_profile_classes]
_op = [cls(None) for cls in _output_profile_classes]

def input_profiles():
    return _ip

def output_profiles():
    return _op

_input_plugins = None
_output_plugins = None

def _load_plugins():
    global _input_plugins, _output_plugins
    if _input_plugins is not None:
        return
    _input_plugins = []
    _output_plugins = []
    import sys

    discovered_input = []
    discovered_output = []
    seen_classes = set()

    try:
        import calibre.ebooks.conversion.plugins as plugin_pkg
        module_names = sorted(
            f'{plugin_pkg.__name__}.{m.name}'
            for m in pkgutil.iter_modules(plugin_pkg.__path__)
            if not m.name.startswith('_')
        )
    except Exception as e:
        module_names = []
        print(f'WARNING: Failed to discover conversion plugins: {e}', file=sys.stderr)

    for mod_name in module_names:
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print(f'WARNING: Failed to import plugin module {mod_name}: {e}', file=sys.stderr)
            continue

        for attr_name in dir(mod):
            obj = getattr(mod, attr_name, None)
            if not isinstance(obj, type):
                continue
            if obj in (InputFormatPlugin, OutputFormatPlugin):
                continue

            class_key = (obj.__module__, obj.__name__)
            if class_key in seen_classes:
                continue

            try:
                if issubclass(obj, InputFormatPlugin):
                    file_types = getattr(obj, 'file_types', None)
                    if file_types:
                        discovered_input.append(obj)
                        seen_classes.add(class_key)
                elif issubclass(obj, OutputFormatPlugin):
                    file_type = getattr(obj, 'file_type', None)
                    if file_type:
                        discovered_output.append(obj)
                        seen_classes.add(class_key)
            except Exception:
                continue

    for plugin_cls in sorted(discovered_input, key=lambda c: (c.__module__, c.__name__)):
        try:
            _input_plugins.append(plugin_cls(None))
        except Exception as e:
            print(f'WARNING: Failed to load input plugin {plugin_cls.__name__}: {e}', file=sys.stderr)

    output_by_type = {}
    for plugin_cls in discovered_output:
        ft = getattr(plugin_cls, 'file_type', None)
        if ft:
            ft = ft.lower()
            existing = output_by_type.get(ft)
            if existing is None:
                output_by_type[ft] = plugin_cls
            else:

                mod_name = plugin_cls.__module__.rsplit('.', 1)[-1]
                if mod_name.startswith(ft):
                    output_by_type[ft] = plugin_cls

    for plugin_cls in sorted(output_by_type.values(), key=lambda c: (c.__module__, c.__name__)):
        try:
            _output_plugins.append(plugin_cls(None))
        except Exception as e:
            print(f'WARNING: Failed to load output plugin {plugin_cls.__name__}: {e}', file=sys.stderr)

def input_plugins():
    _load_plugins()
    return _input_plugins

def output_plugins():
    _load_plugins()
    return _output_plugins

def plugin_for_input_format(fmt):
    for p in input_plugins():
        if fmt.lower() in [x.lower() for x in p.file_types]:
            return p
    return None

def plugin_for_output_format(fmt):
    fmt = fmt.lower()

    _format_aliases = {
        'html': 'htmlz',
        'htm': 'htmlz',
    }
    fmt = _format_aliases.get(fmt, fmt)
    for p in output_plugins():
        if fmt == p.file_type.lower():
            return p
    return None

def available_input_formats():
    fmts = set()
    for p in input_plugins():
        for f in getattr(p, 'file_types', ()):
            fmts.add(f.lower())
    return fmts

def available_output_formats():
    fmts = {
        p.file_type.lower()
        for p in output_plugins()
        if getattr(p, 'file_type', None)
    }
    if 'htmlz' in fmts or 'zip' in fmts:
        fmts.update({'html', 'htm', 'htmlz'})
    return fmts

class _Flag:

    def __init__(self, attr):
        self.attr = attr
        setattr(self, attr, False)

    def __enter__(self):
        setattr(self, self.attr, True)

    def __exit__(self, *args):
        setattr(self, self.attr, False)


quick_metadata = _Flag('quick')
apply_null_metadata = _Flag('apply_null')
force_identifiers = _Flag('force_identifiers')


# Metadata readers and writers, mirroring the MetadataReaderPlugin and
# MetadataWriterPlugin classes in calibre/customize/builtins.py, which cannot
# be imported in WASM as it also pulls in the device drivers and the GUI.
# file type -> (module, function, extra keyword arguments)
_METADATA_READERS = {
    'chm': ('calibre.ebooks.chm.metadata', 'get_metadata'),
    'epub': ('calibre.ebooks.metadata.epub', 'get_metadata'),
    'kepub': ('calibre.ebooks.metadata.epub', 'get_metadata'),
    'fb2': ('calibre.ebooks.metadata.fb2', 'get_metadata'),
    'fbz': ('calibre.ebooks.metadata.fb2', 'get_metadata'),
    'html': ('calibre.ebooks.metadata.html', 'get_metadata'),
    'htmlz': ('calibre.ebooks.metadata.extz', 'get_metadata'),
    'imp': ('calibre.ebooks.metadata.imp', 'get_metadata'),
    'lit': ('calibre.ebooks.metadata.lit', 'get_metadata'),
    'lrf': ('calibre.ebooks.lrf.meta', 'get_metadata'),
    'lrx': ('calibre.ebooks.metadata.lrx', 'get_metadata'),
    'odt': ('calibre.ebooks.metadata.odt', 'get_metadata'),
    'docx': ('calibre.ebooks.metadata.docx', 'get_metadata'),
    'opf': ('calibre.ebooks.metadata.opf', 'get_metadata'),
    'pdb': ('calibre.ebooks.metadata.pdb', 'get_metadata'),
    'updb': ('calibre.ebooks.metadata.pdb', 'get_metadata'),
    'pdf': ('calibre.ebooks.metadata.pdf', 'get_metadata'),
    'pml': ('calibre.ebooks.metadata.pml', 'get_metadata'),
    'pmlz': ('calibre.ebooks.metadata.pml', 'get_metadata'),
    'rb': ('calibre.ebooks.metadata.rb', 'get_metadata'),
    'rtf': ('calibre.ebooks.metadata.rtf', 'get_metadata'),
    'snb': ('calibre.ebooks.metadata.snb', 'get_metadata'),
    'tpz': ('calibre.ebooks.metadata.topaz', 'get_metadata'),
    'azw1': ('calibre.ebooks.metadata.topaz', 'get_metadata'),
    'txt': ('calibre.ebooks.metadata.txt', 'get_metadata'),
    'txtz': ('calibre.ebooks.metadata.extz', 'get_metadata'),
    'zip': ('calibre.ebooks.metadata.zip', 'get_metadata'),
    'oebzip': ('calibre.ebooks.metadata.zip', 'get_metadata'),
}
for _fmt in ('mobi', 'prc', 'azw', 'azw3', 'azw4', 'pobi'):
    _METADATA_READERS[_fmt] = ('calibre.ebooks.metadata.mobi', 'get_metadata')

_METADATA_WRITERS = {
    'epub': ('calibre.ebooks.metadata.epub', 'set_metadata'),
    'kepub': ('calibre.ebooks.metadata.epub', 'set_metadata'),
    'fb2': ('calibre.ebooks.metadata.fb2', 'set_metadata'),
    'fbz': ('calibre.ebooks.metadata.fb2', 'set_metadata'),
    'htmlz': ('calibre.ebooks.metadata.extz', 'set_metadata'),
    'txtz': ('calibre.ebooks.metadata.extz', 'set_metadata'),
    'lrf': ('calibre.ebooks.lrf.meta', 'set_metadata'),
    'pdb': ('calibre.ebooks.metadata.pdb', 'set_metadata'),
    'pdf': ('calibre.ebooks.metadata.pdf', 'set_metadata'),
    'rtf': ('calibre.ebooks.metadata.rtf', 'set_metadata'),
    'tpz': ('calibre.ebooks.metadata.topaz', 'set_metadata'),
    'azw1': ('calibre.ebooks.metadata.topaz', 'set_metadata'),
    'odt': ('calibre.ebooks.metadata.odt', 'set_metadata'),
    'docx': ('calibre.ebooks.metadata.docx', 'set_metadata'),
}
for _fmt in ('mobi', 'prc', 'azw', 'azw3', 'azw4'):
    _METADATA_WRITERS[_fmt] = ('calibre.ebooks.metadata.mobi', 'set_metadata')


def _metadata_function(table, ftype):
    entry = table.get((ftype or '').lower().strip())
    if entry is None:
        return None
    mod, func = entry
    return getattr(importlib.import_module(mod), func)


def get_file_type_metadata(stream, ftype):
    import traceback
    from calibre.ebooks.metadata.book.base import Metadata
    mi = Metadata(None, None)
    ftype = (ftype or '').lower().strip()
    try:
        reader = _metadata_function(_METADATA_READERS, ftype)
    except Exception:
        traceback.print_exc()
        return mi
    if reader is None:
        return mi
    if hasattr(stream, 'seek'):
        stream.seek(0)
    try:
        if ftype in ('epub', 'kepub'):
            if quick_metadata.quick:
                from calibre.ebooks.metadata.epub import get_quick_metadata
                return get_quick_metadata(stream, ftype=ftype)
            return reader(stream, ftype=ftype)
        if ftype == 'pdf' and quick_metadata.quick:
            from calibre.ebooks.metadata.pdf import get_quick_metadata
            return get_quick_metadata(stream)
        ans = reader(stream)
        if ftype == 'opf':
            ans = ans[0]
        return ans
    except Exception:
        traceback.print_exc()
    return mi


def set_file_type_metadata(stream, mi, ftype, report_error=None):
    import traceback
    ftype = (ftype or '').lower().strip()
    try:
        writer = _metadata_function(_METADATA_WRITERS, ftype)
        if writer is None:
            return
        if ftype in ('epub', 'kepub'):
            writer(stream, mi, apply_null=apply_null_metadata.apply_null,
                   force_identifiers=force_identifiers.force_identifiers)
        elif ftype in ('fb2', 'fbz'):
            writer(stream, mi, apply_null=apply_null_metadata.apply_null)
        else:
            writer(stream, mi)
        stream.flush()
    except Exception:
        if report_error is None:
            traceback.print_exc()
        else:
            report_error(mi, ftype, traceback.format_exc())

all_metadata_plugins = []

def metadata_plugins(cap):
    return []

def metadata_readers():
    return set(_METADATA_READERS)

def metadata_writers():
    return set(_METADATA_WRITERS)

def run_plugins_on_preprocess(*args, **kwargs):
    return args[0] if args else None

def run_plugins_on_postprocess(*args, **kwargs):
    pass

def find_plugin(name):
    return None

def customize_plugin(plugin, custom):
    pass

def add_plugin(path_or_plugin):
    pass

def has_external_plugins():
    return False

def initialized_plugins():
    return []

config = {}

def plugin_customization(plugin):
    return ''

def patch_metadata_plugins(*a, **kw):
    pass

def device_plugins(*a, **kw):
    return []

def disabled_device_plugins():
    return []

def available_ai_provider_plugins():
    return []
