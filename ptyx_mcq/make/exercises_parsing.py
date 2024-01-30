import re
from pathlib import Path
from typing import Any

from ptyx.extensions.extended_python import PYTHON_DELIMITER
from ptyx.latex_generator import Compiler
from ptyx.utilities import extract_verbatim_tag_content, restore_verbatim_tag_content

import ptyx_mcq
from ptyx_mcq.make.parser_tools import is_new_exercise_start
from ptyx_mcq.tools.io_tools import get_file_or_sysexit, print_info, print_warning


def wrap_exercise(code: str, doc_path: Path = None) -> str:
    """Add a minimal header to mcq exercises to make them compilation-ready."""
    template = (Path(ptyx_mcq.__file__).parent / "templates/original/new.ptyx").read_text()
    code = improve_ex_file_content(code, ex_file_path=doc_path)
    # re.sub() doesn't seem to work when "\dfrac" is in the replacement string... using re.split() instead.
    before, _, after = re.split("(<<<.+>>>)", template, flags=re.MULTILINE | re.DOTALL)
    return f"{before}\n<<<\n{code}\n>>>\n{after}"


def generate_exercise_latex_code_for_preview(*, code: str = None, path: Path = None) -> str:
    """Generate the LaTeX code corresponding to an exercise, for preview.

    One must provide either the code of the exercise, or the path of a `.ex` file, but not both.

    The header generated before the exercise is minimal (no document id for example).
    """
    if code is None and path is None:
        raise ValueError("One of `code` or `path` argument must be set.")
    if code is not None and path is not None:
        raise ValueError("Only one of `code` or `path` argument must be set, not both.")
    if path is not None:
        ex_filename = get_file_or_sysexit(path, extension=".ex")
        code = ex_filename.read_text(encoding="utf8")
    else:
        ex_filename = None
    assert code is not None
    code = wrap_exercise(code, ex_filename)
    context: dict[str, Any] = {
        "MCQ_REMOVE_HEADER": True,
        "MCQ_PREVIEW_MODE": True,
        "MCQ_KEEP_ALL_VERSIONS": True,
    }
    compiler = Compiler()
    # Create temporary document
    return compiler.parse(code=code, **context)


def improve_ex_file_content(file_content: str, ex_file_path: Path = None) -> str:
    """Improve the content of the exercise file, escaping `*` characters notably."""
    # Search for lines starting inadvertently with `* `, since a star is the symbol used to
    # start a new exercise.
    # If we found any, we will insert a space before, so it is not interpreted as the start of
    # a new exercise (unless we are in a verbatim block, which we can't modify for now, so,
    # in this last case, we'll have to be careful when we will generate PTYX code later.).
    file_content, verbatim_contents = extract_verbatim_tag_content(file_content)

    def substitute(m: re.Match) -> str:
        print_info("`* ` at the start of a line is used to declare a new exercise.")
        print_info("A space will be inserted before to prevent this in the following line:")
        star_prefixed_line = m.group(0)
        print_info(star_prefixed_line + "\n")
        return " " + star_prefixed_line

    # Search for lines containing only a star, or starting with `* `.
    file_content = re.sub("^\\*(?: .*)?$", substitute, file_content, flags=re.MULTILINE)

    # Insert `*\n` to mark the start of a new exercise.
    # Nota: Add a line break (instead of a space) after the star,
    #       in case the .ex file starts with python code.
    #       This avoids to get something like "* .............",
    #       where the line of dots introduces python code.
    file_content = "*\n" + file_content

    # Test for unbalanced python delimiters.
    if sum(1 for _ in re.finditer(PYTHON_DELIMITER, file_content)) % 2 == 1:
        print_warning(f"A lonely line of multiple dots was found in exercise '{ex_file_path}'.")
        print_warning("This may lead to strange bugs, since a line of multiple dots is meant")
        print_warning(" to declare python code.")
        print_warning("Hint: prefix the line with empty brackets, for example `{}............`.")

    lines: list[str] = []
    for line in file_content.split("\n"):
        lines.append(line)
        if is_new_exercise_start(line):
            lines.append(f'#PRINT{{\u001b[36mIMPORTING\u001b[0m "{_prettify_path(ex_file_path)}"}}')
            question_name = ex_file_path.name.replace("#", "##") if ex_file_path is not None else "?"
            lines.append(f"#QUESTION_NAME{{{question_name}}}")
    file_content = "\n".join(lines) + "\n"
    return restore_verbatim_tag_content(file_content, verbatim_contents)


def _prettify_path(ex_file_path: Path = None) -> str:
    if ex_file_path is None:
        return "?"
    return str(ex_file_path.parent / f"\u001b[36m{ex_file_path.name}\u001b[0m").replace("#", "##")


def _get_ex_file_content(ex_file_path: Path, exercise=True) -> str:
    """Get the content of the file to include, with a few enhancements.

    - Prefix the file content with `*` if needed (each pTyX exercise must begin with `*`).
    - Inject some meta-information into the pTyX code to make debugging easier."""

    with open(ex_file_path) as file:
        file_content = file.read().strip()
        # Remove all comments
        file_content = re.sub("( # .+)|(^# .+\n)", "", file_content, flags=re.MULTILINE)

        # Each exercise must start with a star. Since each included file is supposed to be an exercise,
        # add the initial star if missing.
        if exercise:
            return improve_ex_file_content(file_content, ex_file_path=ex_file_path)
        else:
            return f'#PRINT{{\u001b[36mIMPORTING\u001b[0m "{_prettify_path(ex_file_path)}"}}\n' + file_content
