"""Stub for calibre_extensions.winutil"""
def get_file_id(path):
    return 0
def move_file(src, dst):
    import shutil
    shutil.move(src, dst)
def filesystem_type_name(path):
    return 'memfs'
def get_long_path_name(path):
    return path
