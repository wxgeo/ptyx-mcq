import re
from pathlib import Path

from ptyx.latex_generator import Compiler


def normalize_text(s: str) -> str:
    """
    Remove LaTeX comments, indentation, and more than
    two consecutive line breaks.
    """
    # Remove LaTeX comments:
    # Look for a '%' that is NOT preceded by a backslash
    # and remove everything until the end of the line.
    s = re.sub(r"(?<!\\)%.*", "", s)

    # Remove indentation at the start of lines
    s = re.sub(r"^ +", "", s, flags=re.MULTILINE)

    # Remove any trailing spaces at the end of the lines.
    s = re.sub(r" +$", "", s, flags=re.MULTILINE)

    # Collapse 3+ line breaks into exactly two
    s = re.sub(r"\n{3,}", "\n\n", s)

    s = s.replace("\\begin{document}\n\n", "\\begin{document}\n")

    return s.strip()


def test_normalize_text():
    # Original test case: handles indentation and line breaks
    assert normalize_text("  a\nb\n\n \n \n c") == "a\nb\n\nc"

    # Test case: Standard LaTeX comment removal
    assert normalize_text("Hello world % this is a comment") == "Hello world"

    # Test case: Escaped percent signs should be preserved
    assert normalize_text(r"The tax rate is 15\% % check this") == r"The tax rate is 15\%"

    # Test case: Multiple lines with comments and extra spacing
    input_text = """
    \section{Introduction} % Start of section


    This is text. % Hidden note

    % Entirely commented line
    Final line.
    """
    # Expected: Comments gone, indentation stripped, max 2 newlines
    expected_output = "\section{Introduction}\n\nThis is text.\n\nFinal line."
    assert normalize_text(input_text) == expected_output

    # Test case: Commented out empty lines
    assert normalize_text("Line 1\n%\nLine 2") == "Line 1\n\nLine 2"


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
