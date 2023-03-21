r"""
ptyx MCQ

This extension enables computer corrected quizzes.

An example:

    #LOAD{mcq}
    #SEED{8737545887}

    ===========================
    sty=my_custom_sty_file
    scores=1 0 0
    mode=all
    ids=~/my_students.csv
    ===========================


    <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    ======= Mathematics ===========

    * 1+1 =
    - 1
    + 2
    - 3
    - 4

    - another answer

    ======= Litterature ==========

    * "to be or not to be", but who actually wrote that ?
    + W. Shakespeare
    - I. Newton
    - W. Churchill
    - Queen Victoria
    - Some bloody idiot

    * Jean de la Fontaine was a famous French
    - pop singer
    - dancer
    + writer
    - detective
    - cheese maker

    > his son is also famous for
    @{\color{blue}%s}
    - dancing french cancan
    - conquering Honolulu
    - walking for the first time on the moon
    - having breakfast at Tiffany

    + none of the above is correct

    >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>


One may include some PTYX code of course.

    """

import re
from pathlib import Path
from re import Match

from ptyx.extensions import extended_python
from ptyx.latex_generator import Compiler

from ptyx_mcq.tools.io_tools import print_warning, print_info
from .make.extend_latex_generator import MCQLatexGenerator
from .make.generate_ptyx_code import generate_ptyx_code

# Note for closing tags:
# '@END' means closing tag #END must be consumed, unlike 'END'.
# So, use '@END_QUESTIONS_BLOCK' to close QUESTIONS_BLOCK,
# but use 'END_QUESTIONS_BLOCK' to close QUESTION, since
# #END_QUESTIONS_BLOCK must not be consumed then (it must close
# QUESTIONS_BLOCK too).


__tags__ = {
    # Tags used to structure MCQ
    "QCM": (0, 0, ["@END_QCM"]),
    "SECTION": (0, 0, ["SECTION", "END_QCM"]),
    "NEW_QUESTION": (0, 0, ["NEW_QUESTION", "CONSECUTIVE_QUESTION", "SECTION", "END_QCM"]),
    "CONSECUTIVE_QUESTION": (0, 0, ["NEW_QUESTION", "CONSECUTIVE_QUESTION", "SECTION", "END_QCM"]),
    "VERSION": (1, 0, ["VERSION", "NEW_QUESTION", "CONSECUTIVE_QUESTION", "SECTION", "END_QCM"]),
    "ANSWERS_BLOCK": (0, 0, ["@END_ANSWERS_BLOCK"]),
    "NEW_ANSWER": (2, 0, ["NEW_ANSWER", "END_ANSWERS_BLOCK"]),
    "ANSWERS_LIST": (2, 0, None),
    # Other tags
    "QCM_HEADER": (1, 0, None),
    "DEBUG_MCQ": (0, 0, None),
    # Deprecated tags
    "L_ANSWERS": (1, 0, None),
}
__latex_generator_extension__ = MCQLatexGenerator


class IncludeParser:
    """Parser used to include files in a ptyx file.

    Ptyx-mcq accept the following syntax to include a file:
    -- path/to/file

    By default, when relative, paths to files refer to the directory where the ptyx file
    is located.

    The following syntax allows to change the directory where the files are searched.
    -- ROOT: /path/to/main/directory
    This will change the search directory for every subsequent path, at least
    until another `-- ROOT:` directive occurs (search directory may be changed
    several times).
    """
    def __init__(self, compiler: Compiler):
        self.compiler = compiler
        self.root: Path = compiler.dir_path

    def _parse_include(self, match: Match) -> str:
        pattern = match.group(1).strip()
        if pattern.startswith("ROOT:"):
            path = Path(pattern[5:].strip()).expanduser()
            if not path.is_absolute():
                path = (self.compiler.dir_path / path).resolve()
            print_info(f"Directory for files inclusion changed to '{path}'.")
            if not path.is_dir():
                raise FileNotFoundError(f"Directory '{self.root}' not found.\n"
                                        f"HINT: Change \"-- {pattern}\" in {self.compiler.file_path}.")
            self.root = path
            return "\n"
        else:
            file_found = False
            contents = []
            for path in sorted(self.root.glob(pattern)):
                if path.is_file():
                    file_found = True
                    contents.append(self._include_file(path))
            if not file_found:
                print_warning(f"No file corresponding to {pattern!r} in '{self.root}'!")
            return "\n\n" + "\n\n".join(contents) + "\n\n"

    def _include_file(self, path: Path) -> str:
        lines: list[str] = []
        with open(path) as file:
            file_content = self.compiler.syntax_tree_generator.remove_comments(file.read().strip())
            if file_content[:2].strip() != "*":
                file_content = "*\n" + file_content
            for line in file_content.split("\n"):
                lines.append(line)
                if (
                        line.startswith("* ")
                        or line.startswith("> ")
                        or line.startswith("OR ")
                        or line.rstrip() in ("*", ">", "OR")
                ):
                    prettified_path = path.parent / f"\u001b[36m{path.name}\u001b[0m"
                    lines.append(f'#PRINT{{\u001b[36mIMPORTING\u001b[0m "{prettified_path}"}}')
        return "\n".join(lines)

    def parse(self, text: str) -> str:
        return re.sub(r"^-- (.+)$", self._parse_include, text, flags=re.MULTILINE)


def main(text: str, compiler: Compiler) -> str:
    # Generation algorithm is the following:
    # 1. Parse AutoQCM code, to convert it to plain pTyX code.
    #    Doing this, we now know the number of questions, the number
    #    of answers per question and the students names.
    #    However, we can't know for know the number of the correct answer for
    #    each question, since questions numbers and answers numbers too will
    #    change during shuffling, when compiling pTyX code (and keeping track of
    #    them through shuffling is not so easy).
    # 2. Generate syntax tree, and then compile pTyX code many times to generate
    #    one test for each student. For each compilation, keep track of correct
    #    answers.
    #    All those data are stored in `latex_generator.mcq_data['answers']`.
    #    `latex_generator.mcq_data['answers']` is a dict
    #    with the following structure:
    #    {1:  [          <-- test n°1 (test id is stored in NUM)
    #         [0,3,5],   <-- 1st question: list of correct answers
    #         [2],       <-- 2nd question: list of correct answers
    #         [1,5],     ...
    #         ],
    #     2:  [          <-- test n°2
    #         [2,3,4],   <-- 1st question: list of correct answers
    #         [0],       <-- 2nd question: list of correct answers
    #         [1,2],     ...
    #         ],
    #    }

    text = IncludeParser(compiler).parse(text)

    # Call extended_python extension.
    text = extended_python.main(text, compiler)

    code = generate_ptyx_code(text)
    assert isinstance(code, str)
    return code
