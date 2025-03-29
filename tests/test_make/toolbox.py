import re
from pathlib import Path

from ptyx.latex_generator import Compiler


def normalize_text(s: str) -> str:
    """Remove indentation and more than two consecutive line breaks."""
    s = re.sub("^ +", "", s, flags=re.MULTILINE)
    s = re.sub("\n{2,}", "\n\n", s)
    return s


def test_normalize_text():
    assert normalize_text("  a\nb\n\n \n \n c") == "a\nb\n\nc"


# def has_same_rstripped_lines(s1: str, s2: str) -> bool:
#     return with_rstripped_lines(s1) == with_rstripped_lines(s2)


def load_ptyx_file(ptyx_file_path: Path):
    """Load ptyx file, create a `Compiler` instance and call extensions to
    generate a plain ptyx file.

    Return the `Compiler` instance."""
    c = Compiler()
    c.read_file(ptyx_file_path)
    c.preparse()
    return c
