import re
from typing import Any, Dict, Optional, Tuple

from utils.yaml import parse_yaml


def parse_front_matter(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Extract front matter from a markdown string.
    Returns a tuple of (metadata_dict, content_string).
    If no front matter is found, metadata_dict is None.
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if match:
        metadata = parse_yaml(match.group(1))
        content = text[match.end() :].strip()
        return metadata, content
    return None, text.strip()


def strip_markdown(text: str) -> str:
    """Strip common Markdown markers while preserving paragraph breaks."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if re.fullmatch(r"`{3,}.*|~{3,}.*|[-*_ ]{3,}", line):
            continue
        line = re.sub(r"^(?:>\s*)+", "", line)
        line = re.sub(r"^(?:#{1,6}|[-+*]|\d+[.)])\s+", "", line)
        line = re.sub(r"!?\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)", r"\1", line)
        line = re.sub(r"(`+)(.+?)\1", r"\2", line)
        line = re.sub(r"(\*{1,3}|~~)(?=\S)(.*?\S)\1(?!\*)", r"\2", line)
        line = re.sub(r"(?<!\w)(_{1,3})(?=\S)(.*?\S)\1(?!\w)", r"\2", line)
        lines.append(line)
    return "\n".join(lines).strip()
