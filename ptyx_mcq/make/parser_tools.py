"""
Tools used to check mcq syntax.
"""


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
