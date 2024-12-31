from pathlib import Path

from ptyx.latex_generator import Compiler

TEST_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = TEST_DIR / "assets"


def rstripped_lines(s: str) -> list[str]:
    return [line.rstrip() for line in s.split("\n")]


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
