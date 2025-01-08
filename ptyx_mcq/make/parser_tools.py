"""
Tools used to check mcq syntax.
"""

import re

from ptyx.shell import print_error


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
            from smallgraphlib.tikz_export import TikzPrinter

            preamble_additions = TikzPrinter.latex_preamble_additions()
            preamble_additions.remove(r"\usepackage{tikz}")
            return preamble_additions
        except ImportError:
            print_error(
                "This file tries to import `smallgraphlib` library, but it is not installed.\n"
                "You can install it with the following command:\npip install smallgraphlib"
            )
    return []
