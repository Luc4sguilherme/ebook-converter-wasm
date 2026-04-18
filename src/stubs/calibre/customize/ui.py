from calibre.customize.profiles import (
    InputProfile, OutputProfile,
    input_profiles as _ip, output_profiles as _op
)
from calibre.customize.conversion import InputFormatPlugin, OutputFormatPlugin
import importlib
import pkgutil

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

def get_file_type_metadata(stream, file_ext):
    import os
    from calibre.ebooks.metadata import MetaInformation
    from calibre.ebooks.metadata.meta import metadata_from_filename

    name = getattr(stream, 'name', None) or f'unknown.{file_ext}'
    name = os.path.basename(name)
    try:
        metadata = metadata_from_filename(name)
        return metadata
    except Exception:
        title = name.rsplit('.', 1)[0] or 'Unknown'
        return MetaInformation(title, ['Unknown'])

def set_file_type_metadata(stream, mi, file_ext):
    pass

all_metadata_plugins = []

def metadata_plugins(cap):
    return []

def metadata_readers():
    return []

def metadata_writers():
    return []

def run_plugins_on_preprocess(*args, **kwargs):
    return args[0] if args else None

def run_plugins_on_postprocess(*args, **kwargs):
    pass

def quick_metadata(mi=None, *a, **kw):
    from contextlib import contextmanager
    @contextmanager
    def _ctx():
        yield
    return _ctx()

def apply_null_metadata(mi=None, *a, **kw):
    from contextlib import contextmanager
    @contextmanager
    def _ctx():
        yield
    return _ctx()

def force_identifiers(*a, **kw):
    from contextlib import contextmanager
    @contextmanager
    def _ctx():
        yield
    return _ctx()

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
