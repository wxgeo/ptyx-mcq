r"""
ptyx MCQ

This extension enables computer corrected quizzes.

This is an example of a source file, to be compiled by ptyx-mcq to a pdf file:

```
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
    - Master Yoda

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
```

One may include some PTYX code of course.

"""

from importlib import metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ptyx.extensions import CompilerExtension
    from ptyx.latex_generator import Compiler


__version__ = metadata.version(__package__)
__all__ = ["__version__", "main", "extend_compiler"]


def extend_compiler() -> "CompilerExtension":
    """This function is called by pTyX extension machinery to add new tags to the compiler.

    This function will be automatically called by the compiler when loading this extension."""
    from ptyx_mcq.make.extend_latex_generator import MCQLatexGenerator

    # Note for closing tags:
    # '@END' means closing tag #END must be consumed, unlike 'END'.
    # So, use '@END_QUESTIONS_BLOCK' to close QUESTIONS_BLOCK,
    # but use 'END_QUESTIONS_BLOCK' to close QUESTION, since
    # #END_QUESTIONS_BLOCK must not be consumed then (it must close
    # QUESTIONS_BLOCK too).
    tags = {
        # Tags used to structure MCQ
        "QCM": (0, 0, ["@END_QCM"]),
        "SECTION": (0, 0, ["SECTION", "END_QCM"]),
        "NEW_QUESTION": (0, 0, ["NEW_QUESTION", "CONSECUTIVE_QUESTION", "SECTION", "END_QCM"]),
        "CONSECUTIVE_QUESTION": (0, 0, ["NEW_QUESTION", "CONSECUTIVE_QUESTION", "SECTION", "END_QCM"]),
        "QUESTION_NAME": (1, 0, None),
        "VERSION": (1, 0, ["VERSION", "NEW_QUESTION", "CONSECUTIVE_QUESTION", "SECTION", "END_QCM"]),
        "ANSWERS_BLOCK": (0, 0, ["@END_ANSWERS_BLOCK"]),
        "NEW_ANSWER": (2, 0, ["NEW_ANSWER", "END_ANSWERS_BLOCK"]),
        "ANSWERS_LIST": (2, 0, None),
        # Other tags
        "QCM_HEADER": (1, 0, None),
        "BARCODE": (0, 0, None),
        "STUDENT_IDENTIFIER_INPUT": (0, 0, None),
        "QCM_FOOTER": (0, 0, None),
        "QUESTION_CONFIG": (1, 0, None),
        "DEBUG_MCQ": (0, 0, None),
        # Deprecated tags
        "L_ANSWERS": (1, 0, None),
    }
    return {"latex_generator": MCQLatexGenerator, "tags": tags}


# TODO: `main` is commonly used in python as the main entry point for scripts.
# TODO: So, on other name should be chosen for the pTyX extension parser (maybe `preparse()`?).
def main(text: str, compiler: "Compiler") -> str:
    """This function is automatically called by pTyX extension machinery to preparse MCQ code and return pTyX code."""
    from ptyx.extensions import extended_python
    from ptyx_mcq.make.generate_ptyx_code import generate_ptyx_code
    from ptyx_mcq.make.include_directives_parsing import resolve_includes
    from ptyx_mcq.tools.io_tools import print_error, FatalError
    from ptyx_mcq.make.parser_tools import autodetect_smallgraphlib

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
        text = resolve_includes(text, compiler.dir_path, strict=True)
    except FileNotFoundError:
        print_error(
            "File not found when trying to resolve inclusions (see error message above).\n"
            f"Hint: command `mcq update {getattr(compiler.file_path, 'name', '<PTYX-FILE-PATH>')}` "
            "may fix it."
        )
        raise FatalError

    # Smallgraphlib needs some specific tikz packages and latex commands
    # to generate its figures. Though user could add them manually in the .ptyx file,
    # we will add them automatically if `import smallgraphlib` or `from smallgraphlib import `
    # is found in the code, for convenience. (False positives will only result in a slight slowdown,
    # and false negatives should almost never occur, and can be fixed by manual import of the missing
    # latex packages and commands).
    additional_header_lines = autodetect_smallgraphlib(text)

    # Call extended_python extension.
    text = extended_python.main(text, compiler)

    code = generate_ptyx_code(text, additional_header_lines=additional_header_lines)
    assert isinstance(code, str)
    return code
