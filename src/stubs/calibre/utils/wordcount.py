"""Stub calibre.utils.wordcount for WASM."""

import re

class WordCount:
    def __init__(self, text=''):
        words = re.findall(r'\S+', text)
        self.words = len(words)
        self.chars = len(text)

def get_wordcount_obj(text):
    return WordCount(text)
