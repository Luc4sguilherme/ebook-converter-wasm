import json, os, copy
from calibre.constants import config_dir
from calibre.utils.localization import _

tweaks = {
    'authors_split_regex': r'(?i),?\s+(and|with)\s+',
    'author_sort_copy_method': 'comma',
    'author_name_copywords': ('Corporation', 'Company', 'Co.', 'Agency', 'Council',
        'Committee', 'Inc.', 'Institute', 'National', 'Society', 'Club',
        'Team', 'Press', 'University', 'Ltd.', 'Limited', 'LLC',
        'Press', 'Publishing', 'Publications', 'Magazines', 'Media',
        'Group', 'Studios', 'International'),
    'author_name_prefixes': ('Mr', 'Mrs', 'Ms', 'Dr', 'Prof'),
    'author_name_suffixes': ('Jr', 'Sr', 'PhD', 'MD', 'DDS', 'III', 'II', 'IV'),
    'author_surname_prefixes': ('da', 'de', 'di', 'la', 'le', 'van', 'von'),
    'author_use_surname_prefixes': False,
    'categories_use_field_for_author_name': 'author_sort',
    'default_language_for_title_sort': 'eng',
    'gui_last_modified_display_format': 'dd MMM yyyy',
    'gui_pubdate_display_format': 'MMM yyyy',
    'gui_timestamp_display_format': 'dd MMM yyyy',
    'per_language_title_sort_articles': {
        'eng': (r'A\s+', r'The\s+', r'An\s+'),
        'deu': (r'Der\s+', r'Die\s+', r'Das\s+', r'Ein\s+', r'Eine\s+', r'Einer\s+'),
        'fra': (r"L[ae]\s+", r"L'", r'Les\s+', r'Un\s+', r'Une\s+'),
        'ita': (r"L[ao]\s+", r"L'", r'I\s+', r'Gli\s+', r'Le\s+', r'Un\s+', r"Un'", r'Uno\s+', r'Una\s+'),
        'spa': (r'El\s+', r'La\s+', r'Los\s+', r'Las\s+', r'Un\s+', r'Una\s+'),
        'por': (r'O\s+', r'A\s+', r'Os\s+', r'As\s+', r'Um\s+', r'Uma\s+'),
    },
    'restrict_output_formats': [],
    'save_template_title_series_sorting': 'library_order',
    'series_index_auto_increment': 'next',
    'skip_network_check': False,
    'sony_collection_name_template': '{value}',
    'sony_collection_renaming_rules': {},
    'sony_collection_sorting_rules': {},
    'sort_dates_using_visible_fields': False,
    'title_series_sorting': 'library_order',
    'use_series_auto_increment_tweak_when_importing': False,
}
plugin_dir = os.path.join(config_dir, 'plugins')

def from_json(obj):
    return obj

def to_json(obj):
    return obj

def json_loads(raw):
    return json.loads(raw)

def json_dumps(obj):
    return json.dumps(obj, indent=2, default=str)

def commit_data(path):
    pass

def read_data(path):
    return b''

def make_config_dir():
    os.makedirs(config_dir, exist_ok=True)

prefs = {
    'read_file_metadata': True,
    'output_format': 'epub',
    'input_format_order': ['epub', 'azw3', 'mobi', 'docx', 'html', 'txt', 'pdf', 'rtf', 'odt', 'fb2'],
    'filename_pattern': r'(?P<title>.+) - (?P<author>[^_]+)',
    'swap_author_names': False,
}

class Option:
    def __init__(self, name, switches=None, help='', type=None, choices=None,
                 check=None, group=None, default=None, action=None, metavar=None):
        self.name = name
        self.switches = switches or []
        self.help = help
        self.type = type
        self.choices = choices
        self.check = check
        self.group = group
        self.default = default
        self.action = action
        self.metavar = metavar

class OptionValues:
    def __init__(self):
        pass
    def __getattr__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return None

class OptionSet:
    def __init__(self, description=''):
        self.description = description
        self.preferences = []
        self.groups = {}
        self.defaults = {}
    def add_opt(self, name, switches=None, help='', type=None, choices=None,
                check=None, group=None, default=None, action=None, metavar=None):
        opt = Option(name, switches, help, type, choices, check, group, default, action, metavar)
        self.preferences.append(opt)
        self.defaults[name] = default
        return opt
    def add_group(self, name, description=''):
        self.groups[name] = description
        return name
    def option_by_name(self, name):
        for o in self.preferences:
            if o.name == name:
                return o
        return None
    def parse_string(self, src):
        v = OptionValues()
        for k, val in self.defaults.items():
            setattr(v, k, copy.deepcopy(val))
        return v

class Config:
    def __init__(self, basename, description=''):
        self.basename = basename
        self.description = description
        self.option_set = OptionSet(description)
        self.option_set.add_group('DEFAULT')
    def add_opt(self, name, **kw):
        self.option_set.add_opt(name, **kw)
    def parse(self):
        return self.option_set.parse_string('')

class StringConfig:
    def __init__(self, src='', **kw):
        self.option_set = OptionSet()
        self.src = src
    def add_opt(self, name, **kw):
        self.option_set.add_opt(name, **kw)
    def parse(self):
        return self.option_set.parse_string(self.src)

class ConfigProxy:
    def __init__(self, config):
        self.__config = config
        self.__opts = config.parse() if hasattr(config, 'parse') else OptionValues()
    def __getitem__(self, key):
        return getattr(self.__opts, key, None)
    def __setitem__(self, key, val):
        setattr(self.__opts, key, val)
    def __getattr__(self, name):
        if name.startswith('_ConfigProxy__'):
            return object.__getattribute__(self, name)
        return getattr(self.__opts, name, None)

class ConfigInterface:
    pass
