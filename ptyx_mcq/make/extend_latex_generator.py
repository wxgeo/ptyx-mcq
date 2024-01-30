#!/usr/bin/env python3
import re
from dataclasses import dataclass

# --------------------------------------
#               Compiler
#    Generate all MCQ versions
# --------------------------------------
#    PTYX
#    Python LaTeX preprocessor
#    Copyright (C) 2009-2020  Nicolas Pourcelot
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


from functools import partial
from pathlib import Path
from typing import TypedDict, Optional, Set, List, Tuple, Dict, Callable

from ptyx.printers import sympy2latex
from ptyx.latex_generator import LatexGenerator
from ptyx.syntax_tree import Node, Tag
from ptyx.utilities import latex_verbatim

from ptyx_mcq.tools.config_parser import (
    Configuration,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    StudentId,
    StudentName,
)
from ptyx_mcq.tools.io_tools import print_warning
from .header import (
    packages_and_macros,
    id_band,
    extract_students_id_and_name_from_csv,
    extract_students_name_from_csv,
    student_id_table,
    students_checkboxes,
    IdentifiantError,
)


SCORE_CONFIG_KEYS = {
    "mode": str,
    "weight": float,
    "correct": float,
    "incorrect": float,
    "skipped": float,
    "floor": float,
    "ceil": float,
}


class MCQCache(TypedDict):
    header: Optional[str]
    check_id_or_name: Optional[str]
    data: Configuration


@dataclass
class CurrentState:
    """Stores internal information to make debugging easier."""

    question_text: str = ""
    question_number: int = 0
    version_number: int = 0


def _handle_multiline_answers(s):
    s = s.strip()
    if "\n" in s:
        if "\n\n" in s:
            print_warning("Blank line detected in the following answer:")
            print(10 * "-")
            print(s)
            print(10 * "-")
            print_warning("This may be caused by a missing `*` before the next question.")
        s = s.replace("\n", r"\\")
        return r"\begin{tabular}[t]{l}" + s + r"\end{tabular}"
    else:
        return s


def _has_option(node: Node, option: str) -> bool:
    options_list = node.options.split(",") if node.options else []
    return option in [opt.strip() for opt in options_list]


def _analyze_ids(ids: List[str]) -> Tuple[int, int, List[Tuple[str, ...]]]:
    """Given a list of IDs (str), return:
    - the length of an ID (or raise an error if they don't have the same size),
    - the maximal number of different digits in an ID caracter,
    - a list of sets corresponding to the different digits used for each ID caracter.

    >>> _analyze_ids(['18', '19', '20', '21'])
    (2, 4, [{'1', '2'}, {'8', '9', '0', '1'}])
    """
    lengths = {len(iD) for iD in ids}
    if len(lengths) != 1:
        print(ids)
        raise IdentifiantError("All students ID must have the same length !")
    id_length = lengths.pop()
    # Create the list of the sets of all possible values for each digit.
    digits: List[Set[str]] = [set() for _ in range(id_length)]
    for iD in ids:
        for i, digit in enumerate(iD):
            digits[i].add(digit)

    max_ndigits = max(len(set_) for set_ in digits)
    # Make digits elements immutable (safer...)
    # Don't use frozenset, as it isn't easily serializable to JSON.
    return id_length, max_ndigits, [tuple(s) for s in digits]


class IdFormat(TypedDict):
    students_ids: dict[StudentId, StudentName]
    id_format: tuple[int, int, list[tuple[str, ...]]]


def _detect_id_format(ids: Dict[StudentId, StudentName], id_format: str) -> IdFormat:
    """Return IDs and ID format data.

    `ids` is a dictionary who contains students names and ids.
    `id_format` is a string, specifying a number of digits ('8 digits'...).

    Returned ID format data will consist of:
    - the length of an ID,
    - the maximal number of different digits in an ID character,
    - a list of sets corresponding to the different digits used for each ID character.
    """
    id_length = max_ndigits = digits = None

    if not ids and not id_format:
        raise RuntimeError("Unknown format for students' IDs.")
    if ids:
        # Analyze the IDs list even if `id_format` is provided.
        # This enables to check the consistency between the IDs list and the
        # given ID format.
        id_length, max_ndigits, digits = _analyze_ids(list(ids))

    if id_format:
        # Analyze the ID format even if students ids are provided.
        # This enables to check the consistency between the IDs list and the
        # given ID format.
        num, ext = id_format.split()
        # Test format syntax
        if ext not in ("digit", "digits"):
            raise ValueError(f"Unknown format : {id_format!r}")
        try:
            n = int(num)
        except ValueError:
            raise ValueError(f"Unknown format : {id_format!r}")
        # Test consistency between format and IDs
        if id_length is not None and id_length != n:
            raise IdentifiantError("Identifiers don't match given format !")
        # Generate format data
        id_length = n
        max_ndigits = 10
        digits = n * [tuple("0123456789")]
    assert id_length is not None
    assert max_ndigits is not None
    assert digits is not None
    return {"students_ids": ids, "id_format": (id_length, max_ndigits, digits)}


class SameAnswerError(RuntimeError):
    pass


# Extend LatexGenerator with new tags.


class MCQLatexGenerator(LatexGenerator):
    """Extension of LatexGenerator handling new tags."""

    def __init__(self, compiler=None):
        super().__init__(compiler=compiler)
        self.mcq_current_state = CurrentState()

    def reset(self):
        super().reset()
        self._mcq_reset_cache()

    def _test_singularity_and_append(self, code: str, answers_list: list) -> str:
        code = code.strip()
        if code in answers_list:
            msg = [
                "ERROR: Same answer proposed twice in MCQ !",
                f"Answer {code!r} appeared at least twice for the same question.",
                "Question was:",
                repr(self.mcq_current_state.question_text),
                "",
                "Nota: if this is really desired behaviour, insert",
                "following lines in the header of the ptyx file:",
                "#PYTHON",
                "ALLOW_SAME_ANSWER_TWICE=True",
                "#END",
            ]
            n = max(len(s) for s in msg)
            stars = (n + 4) * "*"
            print(stars)
            for s in msg:
                print("* " + s)
            print(stars)
            raise SameAnswerError(
                "Same answer proposed twice in MCQ (see message above for more information) !"
            )
        else:
            answers_list.append(code)
        return code

    def _mcq_shuffle_and_parse_children(
        self, node: Node, children: list = None, target: Tag = "ITEM"
    ) -> None:
        if self.context.get("MCQ_KEEP_ALL_VERSIONS"):
            self._parse_children(node.children)
        else:
            self._shuffle_and_parse_children(node, children, target=target)

    def _mcq_pick_and_parse_children(self, node: Node, children: list = None, target: Tag = "ITEM") -> None:
        if self.context.get("MCQ_KEEP_ALL_VERSIONS"):
            self._parse_children(node.children)
        else:
            self._pick_and_parse_children(node, children, target=target)

    def _mcq_reset_cache(self) -> None:
        """Reset MCQ plugin cache.

        Some tags use cache, for code which don't change between two successive compilation.
        (Typically, this is used for (most of) the header)."""
        self.cache["mcq"] = {
            "header": None,
            "check_id_or_name": None,
            "data": Configuration(),
        }

    @property
    def mcq_cache(self) -> MCQCache:
        if "mcq" not in self.cache:
            self._mcq_reset_cache()
        return self.cache["mcq"]

    @property
    def mcq_data(self) -> Configuration:
        return self.mcq_cache["data"]

    # TODO: Rename QCM tag to `MCQ`.
    def _parse_QCM_tag(self, node: Node) -> None:
        # Reinitialize current state (used mostly for debugging and review mode).
        self.mcq_current_state = CurrentState()
        self.write("\n")  # A new line is mandatory here if there is no text before MCQ.
        # ~ self.mcq_correct_answers = []
        self.mcq_data.ordering[self.NUM] = {"questions": [], "answers": {}}
        #    self.mcq_data['answers'] = {}
        # ~ self.mcq_data['question_num'] =
        # Global context for all the MCQ.
        self.mcq_context = self.context.copy()
        if _has_option(node, "shuffle"):
            self._mcq_shuffle_and_parse_children(node, target="SECTION")
        else:
            self._parse_children(node.children)

    def _parse_SECTION_tag(self, node: Node) -> None:
        title = node.options.strip() if node.options else ""
        if title:
            self.write(r"\section{%s}" % title)
        children = node.children
        # Nota: \begin{enumerate} must not be written just after the
        # beginning of the section, since there may be some explanations
        # between the section title and the first question.
        # So, we have to insert it just before the first NEW_QUESTION.
        try:
            i = self._child_index(children, "NEW_QUESTION")
        except ValueError:
            self._parse_children(children)
            return
        self._parse_children(children[:i])
        self.write(r"\begin{enumerate}[resume]")
        self._mcq_shuffle_and_parse_children(node, children[i:], target="NEW_QUESTION")
        self.write(r"\end{enumerate}")

    def _parse_QUESTION_NAME_tag(self, node: Node) -> None:
        name = node.arg(0)
        if self.context.get("MCQ_DISPLAY_QUESTION_TITLE"):
            self.write(r"\fbox{")
            self.write(f"{self.mcq_current_state.question_number}")
            if self.mcq_current_state.version_number > 1:
                self.write(f".v{self.mcq_current_state.version_number}")
            self.write("--")
            self.write(name, verbatim=True)
            self.write("}\\par")

    def _parse_NEW_QUESTION_tag(self, node: Node) -> None:
        self.mcq_current_state.question_number += 1
        self.mcq_current_state.version_number = 0
        # Each question must be independent, so reset all local variables.
        self.set_new_context(self.mcq_context)
        self._mcq_pick_and_parse_children(node, children=node.children, target="VERSION")

    def _parse_CONSECUTIVE_QUESTION_tag(self, node: Node) -> None:
        self.mcq_current_state.question_number += 1
        self.mcq_current_state.version_number = 0
        # For a consecutive question, the context (ie. local variables) must not be reset.
        self._mcq_pick_and_parse_children(node, children=node.children, target="VERSION")

    def _parse_VERSION_tag(self, node: Node) -> None:
        """A version of a question. Each question have one or more versions.

        Tag usage: #VERSION{num}
        """
        self.mcq_current_state.version_number += 1
        n = OriginalQuestionNumber(int(node.arg(0)))
        self.mcq_question_number = n
        # This list is used to test that the same answer is not proposed twice.
        self.mcq_answers: List[str] = []
        data = self.mcq_data.ordering[self.NUM]
        data["questions"].append(n)
        data["answers"][n] = []
        self.context["APPLY_TO_ANSWERS"] = None
        self.context["RAW_CODE"] = None
        self.context["ANSWER_WIDTH"] = None
        self.write(r"\pagebreak[3]\item\filbreak")
        self.write(r"\setcounter{answerNumber}{0}")

        # This is used to improve message error when an error occurred.
        # The question itself is stored to make debugging easier (error messages will
        # display current question).
        # Use `self.mcq_current_state.question_text` to get current question.
        def remember_last_question(code):
            self.mcq_current_state.question_text = code
            return code

        # So, we have to find where the question itself ends and the answers start.
        try:
            i = self._child_index(node.children, "ANSWERS_BLOCK")
        except ValueError:
            try:
                i = self._child_index(node.children, "ANSWERS_LIST")
            except ValueError:
                raise RuntimeError(
                    "No answers found after a MCQ question !\n"
                    "Question text:\n"
                    "----------------------------------\n"
                    f"{node.as_text(skipped_children=(0,)).strip()}\n"
                    "----------------------------------\n"
                )
        self._parse_children(node.children[1:i], function=remember_last_question)
        # This is the end of the question itself.

        # And then, the answers follow.
        self.write("\n\\nopagebreak[4]\n")
        self.write("\n\\begin{minipage}{\\textwidth}\n\\begin{flushleft}")
        self._parse_children(node.children[i:])
        self.write("\\end{flushleft}\n\\end{minipage}")

    def _parse_ANSWERS_BLOCK_tag(self, node: Node) -> None:
        self._mcq_shuffle_and_parse_children(node, target="NEW_ANSWER")

    def _parse_NEW_ANSWER_tag(self, node: Node) -> None:
        """A new answer.

        Tag usage: #NEW_ANSWER{num}{is_answer_correct}
        """

        k = OriginalAnswerNumber(int(node.arg(0)))
        is_correct: Optional[bool] = eval(node.arg(1), self.context)
        if not (is_correct is True or is_correct is False or is_correct is None):
            raise ValueError(
                "Second #NEW_ANSWER argument must be either True, False or None,"
                f" but {node.arg(1)!r} value is {is_correct!r}."
            )
        n = self.mcq_question_number

        self._open_answer(n, k, is_correct)
        # Functions to apply. Last one is applied first:
        # if functions = [f, g, h], then s -> f(g(h(s))).

        # First function must strip remaining new lines and spaces.
        # Remaining new lines may cause bugs if a formating is applied, like $%s$.
        # For example, "$x^2\n\n$" or "$\n\nx^2$" would fail.
        functions: list[Callable] = [lambda s: s.strip()]

        # TODO(?): functions should be compiled only once for each question block,
        #  not for every answer (though it is probably not a bottleneck in
        #  code execution).
        apply = self.context.get("APPLY_TO_ANSWERS")
        if apply:
            # Apply template or function to every answer.
            # Support:
            # - string templates. Ex: \texttt{%s}
            # - name of the function to apply. Ex: f.
            # In last case, the function must have been defined or imported
            # before.
            if "%s" in apply:
                functions.append(lambda s: (apply % s))
            else:
                # Search for the function name in context.
                functions.append(self.context[apply])

        if self.context.get("RAW_CODE"):
            # Try to emulate verbatim (which is not allowed inside
            # a macro argument in LaTeX).
            functions.append(latex_verbatim)
        else:
            functions.append(_handle_multiline_answers)

        # WARNING: this function must be the last one to be called !
        if not self.context.get("ALLOW_SAME_ANSWER_TWICE"):
            # This function is used to verify that each answer is unique.
            # This avoids proposing twice the same answer by mistake, which
            # may occur easily when using random values.
            functions.append(partial(self._test_singularity_and_append, answers_list=self.mcq_answers))

        # WARNING: do NOT apply any more function after `self._test_singularity_and_append` !

        self._parse_children(node.children[2:], function=functions)
        self._close_answer()

    def _open_answer(
        self, n: OriginalQuestionNumber, k: OriginalAnswerNumber, is_correct: Optional[bool]
    ) -> None:
        # `n` is question number *before* shuffling
        # `k` is answer number *before* shuffling
        # When the pdf with solutions will be generated, incorrect answers
        # will be preceded by a white square, while correct ones will
        # be preceded by a gray one.
        if width := self.context.get("ANSWER_WIDTH"):
            if re.fullmatch(r"\d+.?\d*|\.\d+", width):
                # Default unit is `\linewidth`.
                width += r"\linewidth"
            self.write(r"\begin{minipage}{%s}" % width)
        self.write(r"\ptyxMCQTab{")
        cb_id = f"Q{n}-{k}"
        if self.WITH_ANSWERS and is_correct:
            self.write(r"\checkBox{gray}{%s}" % cb_id)
        elif self.WITH_ANSWERS and is_correct is None:
            self.write(r"\checkBox{orange!20}{%s}" % cb_id)
        else:
            self.write(r"\checkBox{white}{%s}" % cb_id)
        self.write(r"}{")
        data = self.mcq_data.ordering[self.NUM]
        data["answers"][n].append((k, is_correct))

    def _close_answer(self) -> None:
        # Close '\ptyxMCQTab{' written by `_open_answer()`.
        self.write("}")
        if self.context.get("ANSWER_WIDTH"):
            self.write(r"\end{minipage}")
        self.write(r"\quad" "\n")

    def _parse_ANSWERS_LIST_tag(self, node: Node) -> None:
        """This tag generates answers from a python list.

        Tag usage: #ANSWERS_LIST{list_of_answers}{list_of_correct_answers}

        Example:
        #ANSWERS_LIST{l}{[l[0]]} or #ANSWERS_LIST{l}{l[0],}
        When using the last syntax, the coma is mandatory.

        Note that if the elements of the lists are not strings, they will be
        converted automatically to math mode latex code (1/2 -> '$\frac{1}{2}$').
        """

        def eval_and_format(arg: str) -> List[str]:
            raw_list = eval(arg.strip(), self.context)
            if not isinstance(raw_list, (list, tuple)):
                raise RuntimeError(f"In #ANSWERS_LIST, argument {arg!r} must be a list of answers.")
            formatted_list = [(val if isinstance(val, str) else f"${sympy2latex(val)}$") for val in raw_list]
            return formatted_list

        answers = eval_and_format(node.arg(0))
        correct_answers = eval_and_format(node.arg(1))
        neutralized_answers = eval_and_format(node.options) if node.options else []

        # Test that arguments seem correct
        # (they must be a list of unique answers, and answers must include the correct ones).
        for ans in correct_answers:
            if ans not in answers:
                raise RuntimeError(
                    f"#ANSWERS_LIST: correct answer {ans!r} is not in proposed answers list {answers!r}!"
                )
        for ans in neutralized_answers:
            if ans not in answers:
                raise RuntimeError(
                    f"#ANSWERS_LIST: neutralized answer {ans!r} is not in proposed answers list {answers!r}!"
                )

        for ans in answers:
            self._test_singularity_and_append(ans, self.mcq_answers)
        # answers = self.mcq_answers

        # Shuffle and generate LaTeX.
        # randfunc.shuffle(answers)
        self.write("\n\n" r"\begin{minipage}{\textwidth}" "\n")
        n = self.mcq_question_number
        for k, ans in enumerate(answers, 1):
            self._open_answer(
                n, OriginalAnswerNumber(k), None if ans in neutralized_answers else (ans in correct_answers)
            )
            self.write(ans)
            self._close_answer()
        self.write("\n\n\\end{minipage}")

    def _parse_L_ANSWERS_tag(self, node: Node) -> None:
        raise DeprecationWarning(
            "L_ANSWERS tag is not supported anymore.\n"
            "Use #ANSWERS_LIST{list_of_answers}{list_of_correct_answers} instead of "
            "#L_ANSWERS{list_of_answers}{correct_answer}.\n"
            "Example: #L_ANSWERS{l}{l[0]} -> #ANSWERS_LIST{l}{[l[0]]}"
        )

    def _parse_DEBUG_MCQ_tag(self, node: Node) -> None:
        data = self.mcq_data
        print("---------------------------------------------------------------")
        print("ptyxMCQ data:")
        print(data)
        print("---------------------------------------------------------------")
        # self.write(data)

    def _parse_QUESTION_CONFIG_tag(self, node: Node) -> None:
        if getattr(self, "mcq_question_number", None) is None:
            raise RuntimeError("#QUESTION_CONFIG can only be used inside a question.")
        for line in node.arg(0).split("\n"):
            line = line.strip()
            if line == "":
                continue
            # Support for `;` delimiter between `key = value` entries.
            for key_val in line.split(";"):
                key_val = key_val.strip()
                match key_val.split("=", maxsplit=1):
                    case key, val:
                        key = key.strip()
                        val = val.strip()
                        if key in SCORE_CONFIG_KEYS:
                            val_type = SCORE_CONFIG_KEYS[key]
                            getattr(self.mcq_data, key)[self.mcq_question_number] = val_type(val)
                        else:
                            raise NameError(f"Unknown key in #QUESTION_CONFIG: {key!r}.")
                    case _:
                        if key_val != "":
                            raise RuntimeError(f"Invalid line in #QUESTION_CONFIG: {key_val!r}.")

    @staticmethod
    def _parse_sty_list(sty_packages: str) -> str:
        """Parse LaTeX sty packages list in header."""
        packages: list[str] = []
        for package in sty_packages.split(","):
            if package:
                package = package.strip()
                # noinspection RegExpRedundantEscape
                m = re.match(r"\s*\[(?P<options>(?:\w|\s)+)\](?P<package>.+)", package)
                if m is None:
                    packages.append(f"{{{package}}}")
                else:
                    options = m.group("options").strip()
                    package = m.group("package").strip()
                    packages.append(f"[{options}]{{{package}}}")
        return "\n".join(r"\usepackage" + package for package in packages)

    @staticmethod
    def _extract_config_from_header(text: str) -> dict[str, str]:
        def format_key(key_: str) -> str:
            return key_.strip().replace(" ", "_").lower()

        # {alias: standard key name}
        alias = {
            "name": "names",
            "student": "names",
            "students": "names",
            "id": "students_ids",
            "ids": "students_ids",
            "student_ids": "students_ids",
            "student_id": "students_ids",
            "students_id": "students_ids",
            "package": "sty",
            "packages": "sty",
            "id_formats": "id_format",
            "ids_formats": "id_format",
            "ids_format": "id_format",
        }
        # Read config: a dictionary is generated from the `key = value` entries.
        config: Dict[str, str] = {}
        for line in text.split("\n"):
            line = line.strip()
            if "=" in line:
                key, val = line.split("=", maxsplit=1)
                # Normalize the key.
                key = format_key(key)
                key = alias.get(key, key)
                config[key] = val.strip()
            elif line != "":
                raise RuntimeError(f"Invalid format in configuration: {line!r}.")
        return config

    def _parse_QCM_FOOTER_tag(self, node: Node) -> None:
        if not self.context.get("MCQ_REMOVE_HEADER"):
            self.write("\n\\cleardoublepage")
        if self.context.get("MCQ_PREVIEW_MODE"):
            self.write("\\end{preview}")
        self.write("\n\\end{document}")

    def _parse_QCM_HEADER_tag(self, node: Node) -> None:
        """Parse HEADER.

        HEADER raw format is the following:
        ===========================
        sty=my_custom_sty_file
        correct=1
        incorrect=0
        skipped=0
        mode=all
        ids=~/my_students_ids_and_names.csv
        names=~/my_students_names.csv
        id_format=8 digits
        ---------------------------
        # Custom lines to include at the end of the LaTeX preamble.
        ===========================
        """

        sty = ""
        raw_latex = ""
        #    if self.WITH_ANSWERS:
        #        self.context['format_ask'] = (lambda s: '')

        check_id_or_name = self.mcq_cache["check_id_or_name"]
        if self.context.get("MCQ_REMOVE_HEADER"):
            check_id_or_name = ""
        elif check_id_or_name is None:
            code = ""

            config = self._extract_config_from_header(node.arg(0))
            # After the `key = value` entries, the user may append some raw LaTeX code.
            raw_latex = node.arg(1)

            for key, val_type in SCORE_CONFIG_KEYS.items():
                if key in config:
                    getattr(self.mcq_data, key)["default"] = val_type(config.pop(key))

            if "names" in config:
                # the value must be the path of a CSV file.
                csv = config.pop("names")
                if not self.WITH_ANSWERS:
                    students = extract_students_name_from_csv(Path(csv), self.compiler.file_path)
                    code = students_checkboxes(students)
                    self.mcq_data.students_list = students

            if "students_ids" in config or "id_format" in config:
                # config['ids'] must be the path of a CSV file.
                csv = config.pop("students_ids", "")
                id_format = config.pop("id_format", "")

                if not self.WITH_ANSWERS:
                    if csv:
                        ids = extract_students_id_and_name_from_csv(Path(csv), self.compiler.file_path)
                    else:
                        ids = {}

                    try:
                        data = _detect_id_format(ids, id_format)
                    except IdentifiantError as e:
                        msg = e.args[0]
                        raise IdentifiantError(f"Error in {csv!r} : {msg!r}")

                    self.mcq_data.id_format = data["id_format"]
                    self.mcq_data.students_ids = data["students_ids"]
                    code = student_id_table(*data["id_format"])

            if "sty" in config:
                sty = config.pop("sty")

            if "default_score" in config:
                self.mcq_data.default_score = config.pop("default_score")

            # Config should be empty by now !
            for key in config:
                if key == "scores":
                    right, wrong, skipped = config[key].split()
                    print_warning("Please update your ptyx file header:")
                    print(f"Replace `scores = {config[key]}` with:")
                    print(20 * "-")
                    print(f"correct = {right}")
                    print(f"incorrect = {wrong}")
                    print(f"skipped = {skipped}")
                    print(20 * "-")
                raise NameError(f"Unknown key {key!r} in the header of the pTyX file.")

            check_id_or_name = code if not self.WITH_ANSWERS else ""
            self.mcq_cache["check_id_or_name"] = check_id_or_name
            if check_id_or_name:
                check_id_or_name += r"""
            \vspace{1em}

            \tikz{\draw[dotted] ([xshift=2cm]current page.west) -- ([xshift=-1cm]current page.east);}
            """

        header = self.mcq_cache["header"]
        if header is None:
            header1, header2 = packages_and_macros(preview_mode=self.context.get("MCQ_PREVIEW_MODE", False))
            header = "\n".join([header1, self._parse_sty_list(sty), header2, raw_latex, r"\begin{document}"])
            self.mcq_cache["header"] = header

        # Generate barcode
        # Barcode must NOT be put in the cache, since each document has a
        # unique ID.
        n = self.NUM
        calibration = "MCQ__SCORE_FOR_THIS_STUDENT" not in self.context
        top: list[str] = []
        if self.context.get("MCQ_PREVIEW_MODE"):
            top.append("\\renewcommand{\\PreviewBorder}{1.5cm}")
            top.append("\\begin{preview}")
        if self.context.get("MCQ_REMOVE_HEADER"):
            top.append("\n\\newcommand{\\CustomHeader}{}\n")
        else:
            top.append(id_band(doc_id=n, calibration=calibration))

        self.write("\n".join([header, "\n".join(top), check_id_or_name]))
