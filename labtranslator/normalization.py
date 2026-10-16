"""Name-only normalization. Never apply these functions to values or units."""
import re
import unicodedata


def normalize(text):
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('−', '-')
    text = re.sub(r'\s+', ' ', text).strip()
    return re.sub(r'\s*([()])\s*', r'\1', text)


def key(text):
    return re.sub(r'\s+', '', normalize(text)).casefold()
