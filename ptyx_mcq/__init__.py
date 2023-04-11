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

from ptyx.extensions import extended_python
from ptyx.latex_generator import Compiler
from ptyx_mcq.tools.io_tools import print_error

from .make.extend_latex_generator import MCQLatexGenerator
from .make.generate_ptyx_code import generate_ptyx_code
from .tools.include_parser import IncludeParser

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
    "QCM_HEADER": (2, 0, None),
    "QUESTION_CONFIG": (1, 0, None),
    "DEBUG_MCQ": (0, 0, None),
    # Deprecated tags
    "L_ANSWERS": (1, 0, None),
}
__latex_generator_extension__ = MCQLatexGenerator


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

    try:
        text = IncludeParser(compiler.dir_path).parse(text, strict=True)
    except FileNotFoundError:
        print_error(
            "File not found when trying to resolve inclusions (see error message above).\n"
            f"Hint: command `mcq update-include {getattr(compiler.file_path, 'name', 'FILENAME')}` "
            "may fix it."
        )
    additional_header_lines = autodetect_smallgraphlib(text)

    # Call extended_python extension.
    text = extended_python.main(text, compiler)

    code = generate_ptyx_code(text, additional_header_lines=additional_header_lines)
    assert isinstance(code, str)
    return code
