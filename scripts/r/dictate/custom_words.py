"""Handy-style fuzzy correction after transcription.

Algorithm reference: https://github.com/cjpais/Handy/blob/main/src-tauri/src/audio_toolkit/text.rs
"""

from pathlib import Path
import re


def load_custom_words(path: Path) -> list[str]:
    """Read one word or phrase per line; blank lines and # comments are ignored."""
    if not path.exists():
        return []
    return list(dict.fromkeys(
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ))


def _key(text: str) -> str:
    return "".join(c.lower() for c in text if c.isalnum())


def _supported(key: str) -> bool:
    return bool(key) and key.isascii() and key.isalnum()


def _soundex(word: str) -> str:
    groups = {c: str(i) for i, chars in enumerate(
        ("bfpv", "cgjkqsxz", "dt", "l", "mn", "r"), 1
    ) for c in chars}
    word = word.lower()
    result = word[0].upper()
    previous = groups.get(word[0], "0")
    for char in word[1:]:
        if char in "hw":
            continue
        code = groups.get(char, "0")
        if code != "0" and code != previous:
            result += code
        previous = code
    return (result + "000")[:4]


def _distance(left: str, right: str) -> int:
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        new = [i]
        for j, b in enumerate(right, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j - 1] + (a != b)))
        row = new
    return row[-1]


def _punctuation(word: str) -> tuple[str, str]:
    positions = [i for i, char in enumerate(word) if char.isalnum()]
    if not positions:
        return word, word
    return word[:positions[0]], word[positions[-1] + 1:]


def apply_custom_words(
    text: str, custom_words: list[str], threshold: float = 0.18
) -> str:
    """Match up to three words using edit distance and English Soundex.

    Skip non-ASCII terms and keep punctuation and case patterns.
    Lower thresholds accept fewer corrections; zero disables correction.
    """
    keys = []
    for word in custom_words:
        variants = dict.fromkeys((_key(word), _key(word.replace("&", " and "))))
        keys.extend((word, key) for key in variants if _supported(key))
    if not keys or threshold <= 0:
        return text

    tokens = list(re.finditer(r"\S+", text))
    result = []
    cursor = 0
    i = 0
    while i < len(tokens):
        best = None
        best_score = threshold
        for n in range(min(3, len(tokens) - i), 0, -1):
            words = [token.group() for token in tokens[i:i + n]]
            if any(_punctuation(word)[1] for word in words[:-1]):
                continue
            candidate = "".join(_key(word) for word in words)
            if not _supported(candidate) or len(candidate) > 50:
                continue
            for replacement, key in keys:
                length = max(len(candidate), len(key))
                if abs(len(candidate) - len(key)) > max(length * 0.25, 2):
                    continue
                score = _distance(candidate, key) / length
                if (candidate.isalpha() and key.isalpha()
                        and _soundex(candidate) == _soundex(key)):
                    score *= 0.3
                if score < best_score:
                    best_score = score
                    best = n, replacement
        if best is None:
            i += 1
            continue
        n, replacement = best
        first, last = tokens[i], tokens[i + n - 1]
        original = first.group()
        if original.isupper():
            replacement = replacement.upper()
        elif original[0].isupper():
            replacement = replacement[:1].upper() + replacement[1:]
        prefix, _ = _punctuation(original)
        _, suffix = _punctuation(last.group())
        result.extend((text[cursor:first.start()], prefix, replacement, suffix))
        cursor = last.end()
        i += n
    result.append(text[cursor:])
    return "".join(result)
