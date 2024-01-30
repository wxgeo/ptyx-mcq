# from enum import Enum, unique
#
# @unique
# class Levels(Enum):
#     ROOT, QCM, SECTION, QUESTION, VERSION, ANSWERS_BLOCK, NEW_ANSWER = range(7)
import sys
import re
from typing import Iterable

from ptyx.utilities import extract_verbatim_tag_content, restore_verbatim_tag_content, find_closing_bracket

from ptyx_mcq import print_error
from ptyx_mcq.make.parser_tools import is_new_exercise_start, is_mcq_start, is_mcq_end, is_section_start


def parse_at_directive(line: str) -> str:
    r"""Parse @-directives.

    @-directives are lines starting by an `@` character, and preceding answers.
    There used to declare a formatter for all the answers of the same question.

    One may change of f

    Examples of formatter definition:
        * "@formatting_function"
        * "@\texttt{%s}"
        * "@@\texttt{%s}"

    Note that `%s` will be replaced by the provided answer string.

    The last one, with two @ characters, is a raw formatter.
    In that case, \texttt{} will be escaped, so that answer "hello"
    will be converted to "\\texttt\{hello\}".
    """
    assert line.startswith("@")
    raw = line.startswith("@@")
    formatting = line[(2 if raw else 1) :].strip()
    if formatting == "":
        formatting = "%s"
    return f"#{{RAW_CODE={raw};APPLY_TO_ANSWERS={formatting!r};}}"


def generate_ptyx_code(text: str, additional_header_lines: Iterable[str] = ()) -> str:
    """This function translates MCQ syntax into proper pTyX code."""

    # TODO: improve ability to customize this part ?

    code = []

    level_names = ("ROOT", "QCM", "SECTION", "QUESTION", "VERSION", "ANSWERS_BLOCK", "NEW_ANSWER")
    # noinspection PyTypeChecker
    levels = dict(enumerate(level_names))
    depth = {name: i for i, name in enumerate(level_names)}
    #    stack = StaticStack(levels)
    current_level = levels[0]

    def next_level(level):
        return levels[depth[level] + 1]

    def previous_level(level):
        return levels[depth[level] - 1]

    def begin(level, **kw):
        nonlocal current_level

        if level not in level_names:
            raise RuntimeError(f"Unknown level: {level}")

        # Current level must be the parent one before opening level.
        target = depth[level] - 1
        while depth[current_level] > target:
            close(current_level)
        while depth[current_level] < target:
            begin(next_level(current_level))
        assert depth[current_level] == target

        current_level = level
        content = []
        if level == "QUESTION":
            content.append("#CONSECUTIVE_QUESTION" if kw.get("consecutive") else "#NEW_QUESTION")
        else:
            content.append(f"#{level}")

        if level == "QCM":
            if kw.get("shuffle", True):
                # Shuffle sections.
                content.append("[shuffle]")
        elif level == "SECTION":
            if "title" in kw:
                content.append("[%s]" % kw["title"])
        elif level == "VERSION":
            try:
                content.append("{%s}" % kw["n"])
            except KeyError:
                print_error(
                    "Unable to compile document. Maybe a missing `*` at the beginning of the question?"
                )
                sys.exit(1)
        elif level == "NEW_ANSWER":
            content.append("{%s}{%s}" % (kw["n"], kw["correct"]))

        code.append("".join(content))

    def close(level):
        """Close `level` (and any opened upper one).

        For example, close('SECTION') will close levels until returning
        to a level lower than SECTION ('ROOT' or 'QCM').
        Any opened upper level ('QUESTION_BLOCK' or 'ANSWERS') will be closed first.
        """
        nonlocal current_level

        if depth[current_level] < depth[level]:
            raise RuntimeError(f"I can not close level {level}, since it is not opened !")
        while depth[current_level] > depth[level]:
            close(current_level)

        current_level = previous_level(level)
        if level == "QCM":
            code.append("#END_QCM")

        elif level == "ANSWERS_BLOCK":
            # If there are any blank lines after an answer, they must appear
            # *after* #END_ANSWERS_BLOCK, so move them.
            i = 0
            while code[-1].strip() == "":
                code.pop()
                i += 1
            code.append("#END_ANSWERS_BLOCK")
            code.extend(i * [""])
            # Note that since a single blank line is used to separate answers
            # blocks, user must use two consecutive blanks lines to generate
            # a new LaTeX paragraph (the first one is automatically stripped).
            # XXX: This must appear in doc.

    previous_line = None
    before_mcq = True
    is_header = False
    is_header_raw_code = False
    header = ["#QCM_HEADER{"]
    question_num = 0

    # Don't use ASK_ONLY: if one insert Python code here, it would be removed
    # silently when generating the pdf files with the answers !
    intro = ["#ASK % (introduction)"]

    text, verbatim_contents = extract_verbatim_tag_content(text)

    answer_num = None
    for _line_ in text.split("\n"):
        line = _line_.rstrip()
        n = len(line)

        if is_mcq_start(line):  # <<<
            # MCQ start tag detected.
            # First, we must close the header.
            if not is_header_raw_code:
                header.append("}{")
            header.extend(additional_header_lines)
            header.append("}")
            code.extend(header)
            is_header = is_header_raw_code = False
            # Now, let's start the MCQ body.
            intro.append("#END % (introduction)")
            code.extend(intro)
            print("Parsing MCQ...\n")
            print("STRUCTURE:\n")
            begin("QCM")
            before_mcq = False

        elif before_mcq:
            if n >= 3 and all(c == "=" for c in line):  # ===
                # Enter (or leave) header section.
                is_header = not is_header
            elif is_header:
                if line.startswith("---") and not is_header_raw_code:
                    # A line of --- is used as a delimiter between the `key = value` entries
                    # and the optional LaTeX code.
                    is_header_raw_code = True
                    header.append("}{")
                else:
                    header.append(_line_)
            else:
                intro.append(_line_)

        elif is_section_start(_line_):
            # === title ===
            # Start a new section.
            begin("SECTION", title=line.strip("= "))

        # Nota: for a new version of a question, line must start with 'OR ',
        # with a trailing space, or line must be 'OR', without trailing space.
        elif is_new_exercise_start(line):
            # * question
            # Start a question block, with possibly several versions of a question.

            if line[:2] != "OR":
                # If line starts with 'OR', this is not a new block, only another
                # version of current question block.
                # In all other cases, this is a new question.

                begin("QUESTION", consecutive=(line[0] == ">"))
            question_num += 1
            begin("VERSION", n=question_num)
            answer_num = 0
            code.append(line[2:])

        # elif line.startswith("#ANSWERS_LIST"):
        #     # End question.
        #     # (Usually, questions are closed when seeing answers, i.e. lines
        #     # introduced by '-' or '+').
        #     code.append(line)

        elif line.startswith("<->"):
            # Examples:
            # <->2cm
            # <->.5
            width = line[3:]
            code.append(f"#{{ANSWER_WIDTH={width!r};}}")

        elif re.match("[-+!] |\\?{.+} ", line):
            # - incorrect answer
            # + correct answer
            # ! neutralized answer (neither really true nor false, this is useful when there was a problem
            # in an answer).
            # ?{condition} conditional answer (correct iff condition is true)

            if previous_line is None:
                raise RuntimeError("No question before answers list !")
            elif previous_line.startswith("@"):
                # An @-directive have to be written in the line preceding an answer.
                code[-1] = parse_at_directive(previous_line)

            # A blank line is used to separate answers groups.
            if previous_line == "" and current_level == "NEW_ANSWER":
                # This blank line should not appear in final pdf, so remove it.
                # (NB: This must *not* be done for the first answer !)
                code.pop()

            if previous_line == "" or previous_line.startswith("@"):
                # Answers are shuffled inside their respective groups,
                # however groups are kept separate.
                if previous_line.startswith("@"):
                    cut_and_paste = code.pop()
                begin("ANSWERS_BLOCK")
                if previous_line.startswith("@"):
                    # noinspection PyUnboundLocalVariable
                    code.append(cut_and_paste)

            if answer_num is None:
                raise RuntimeError("No question before answers list !")
            answer_num += 1
            end = 2
            match line[0]:
                case "+":
                    correct = True
                case "-":
                    correct = False
                case "!":
                    correct = None
                case "?":
                    try:
                        end = find_closing_bracket(line, 2)
                    except ValueError:
                        raise RuntimeError(f"Unbalanced brackets in line {line!r}")
                    correct = line[2:end]
                    end += 1  # to skip closing bracket.
                case _:
                    assert False, f"{line[0]} should be either '+', '-', '!' or '?'."
            begin("NEW_ANSWER", n=answer_num, correct=correct)

            code.append(line[end:])

        elif is_mcq_end(line):  # >>>
            # End MCQ
            close("QCM")

        else:
            code.append(_line_)

        previous_line = line

    code.append("#QCM_FOOTER")

    text = "\n".join(code)
    return restore_verbatim_tag_content(text, verbatim_contents)
