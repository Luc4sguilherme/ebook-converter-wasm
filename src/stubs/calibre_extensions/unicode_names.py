"""Stub for calibre_extensions.unicode_names"""
import unicodedata

def name_for_codepoint(cp):
    try:
        return unicodedata.name(chr(cp), '')
    except (ValueError, TypeError):
        return ''

def codepoints_for_word(word):
    results = []
    word = word.upper()
    for cp in range(0x110000):
        try:
            name = unicodedata.name(chr(cp), '')
            if word in name:
                results.append(cp)
        except (ValueError, TypeError):
            continue
    return results
