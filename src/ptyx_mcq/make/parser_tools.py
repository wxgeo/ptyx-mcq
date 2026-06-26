"""
Tools used to check mcq syntax.
"""

import re
from pathlib import Path

from ptyx.pretty_print import print_error


def is_new_exercise_start(line_of_code: str) -> bool:
    """Test whether this is the start of a new exercise."""
    return line_of_code[:2].rstrip() in ("*", ">") or line_of_code[:3].rstrip() == "OR"


def is_mcq_start(line_of_code: str) -> bool:
    """Test whether this is the start of the mcq.

    The line of code must be right-stripped before.
    """
    return len(line_of_code) >= 3 and all(c == "<" for c in line_of_code)


def is_mcq_end(line_of_code: str) -> bool:
    """Test whether this is the start of the mcq.

    The line of code must be right-stripped before.
    """
    return len(line_of_code) >= 3 and all(c == ">" for c in line_of_code)


def is_section_start(line_of_code: str) -> bool:
    """Test whether this is the start of a new section of the mcq.

    The line of code must be right-stripped before.
    """
    return len(line_of_code) >= 3 and line_of_code.startswith("=") and line_of_code.endswith("=")


def autodetect_smallgraphlib(text: str) -> list[str]:
    smallgraphlib_detected = (
        re.search("(^import smallgraphlib)|(^from smallgraphlib import)", text, re.MULTILINE) is not None
    )
    if smallgraphlib_detected:
        try:
            # noinspection PyUnresolvedReferences
            from smallgraphlib.printers.tikz import TikzPrinter

            preamble_additions = TikzPrinter.latex_preamble_additions()
            preamble_additions.remove(r"\usepackage{tikz}")
            return preamble_additions
        except ImportError:
            print_error(
                "This file tries to import `smallgraphlib` library, but it is not installed.\n"
                "You can install it with the following command:\npip install smallgraphlib"
            )
    return []


def split_around_mcq(
    *,
    ptyx_file: Path | None = None,
    code: str | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """
    Split the lines in 3 sub-lists:
    - the lines before the MCQ, including <<<
    - the lines inside the MCQ (the part between <<< and >>>).
    - the lines after the MCQ, including >>>

    Raise NoMCQSectionFound if <<< or >>> is not found.
    """
    if code is None:
        if ptyx_file is None:
            raise ValueError("Either `ptyx_file` or `code` argument must be given.")
        else:
            code = ptyx_file.read_text()
    lines = code.splitlines()
    for start, line in enumerate(lines):
        if line.startswith("<<<"):
            break
    else:
        raise NoMCQSectionFound(f"`<<<` not found in '{ptyx_file}'.")
    start += 1

    for end, line in enumerate(lines[start:]):
        if line.startswith(">>>"):
            break
    else:
        raise NoMCQSectionFound(f"`>>>` not found in '{ptyx_file}'.")
    end += start
    return lines[:start], lines[start:end], lines[end:]


class NoMCQSectionFound(RuntimeError):
    """
    Error raised when the file to update does not contain any MCQ section.

    The MCQ section must be surrounded by `<<<` and `>>>` lines.
    """
