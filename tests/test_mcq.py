"""
QUESTIONS

This extension offers a new syntax to write tests and answers.
"""

import re
import shutil
from pathlib import Path

# import atexit

import pytest
from ptyx.latex_generator import Compiler, Node

from ptyx_mcq.cli import make
from ptyx_mcq.make.extend_latex_generator import SameAnswerError
from ptyx_mcq.tools.config_parser import Configuration, DocumentId, OriginalQuestionNumber

TEST_DIR = Path(__file__).parent.resolve()
# TMP_PDF: List[Path] = []


def copy_test(folder: str, tmp_path) -> Path:
    shutil.copytree(TEST_DIR / folder, copy_ := tmp_path / folder)
    return copy_


def load_ptyx_file(ptyx_file_path: Path):
    """Load ptyx file, create a `Compiler` instance and call extensions to
    generate a plain ptyx file.

    Return the `Compiler` instance."""
    c = Compiler()
    c.read_file(ptyx_file_path)
    c.preparse()
    return c


def test_minimal_MCQ(tmp_path):
    folder = copy_test("ptyx-files/minimal-working-example", tmp_path)
    latex = (folder / "minimal-working-example.tex").read_text()
    c = Compiler()
    assert c.parse(path=folder / "minimal-working-example.ptyx") == latex


def test_at_directives(tmp_path):
    folder = copy_test("ptyx-files/format-answers", tmp_path)
    latex = (folder / "at-directives.tex").read_text()
    c = Compiler()
    assert c.parse(path=folder / "at-directives.ptyx", PTYX_NUM=1) == latex


def test_MCQ_basics(tmp_path):
    folder = copy_test("ptyx-files/other", tmp_path)
    c = load_ptyx_file(folder / "partial-test.ptyx")
    assert "VERSION" in c.syntax_tree_generator.tags
    assert "VERSION" in c.latex_generator.parser.tags
    assert "END_QCM" in c.syntax_tree_generator.tags
    assert "END_QCM" in c.latex_generator.parser.tags
    c.generate_syntax_tree()
    header_found = False
    mcq_found = False
    seed_found = False
    for child in c.syntax_tree.children:
        if isinstance(child, Node):
            name = child.name
            if name == "QCM_HEADER":
                header_found = True
            elif child.name == "QCM":
                mcq_found = True
            elif name == "SEED":
                seed_found = True
    assert not seed_found  # `#SEED` is parsed and removed before generating the syntax tree.
    assert header_found
    assert mcq_found
    # TODO: add tests
    latex = c.get_latex()
    # TODO: add tests
    assert "Jean de la Fontaine" in latex


def test_MCQ_shuffling(tmp_path):
    folder = copy_test("ptyx-files/other", tmp_path)
    c = load_ptyx_file(folder / "shuffle.ptyx")
    c.generate_syntax_tree()
    root = c.syntax_tree
    print(root.display())
    assert isinstance(root, Node)
    assert root.name == "ROOT"
    assert repr(root) == f"<Node ROOT at {hex(id(root))}>"
    header = root.children[0]
    assert isinstance(header, Node)
    assert header.name == "QCM_HEADER"
    footer = root.children[-1]
    assert isinstance(footer, Node)
    assert footer.name == "QCM_FOOTER"
    assert isinstance(root.children[-2], str)
    mcq = root.children[-3]
    assert isinstance(mcq, Node)
    assert mcq.name == "QCM"
    section = mcq.children[-1]
    assert isinstance(section, Node)
    assert section.name == "SECTION"

    # Test question structure.
    qlist = []
    for question in section.children:
        assert isinstance(question, Node)
        assert question.name in ("NEW_QUESTION", "CONSECUTIVE_QUESTION")
        assert len(question.children) == 1
        version = question.children[0]
        assert isinstance(version, Node)
        assert version.name == "VERSION"
        question_text = version.children[1].strip()
        qlist.append(question_text.split()[0])
        if "must follow" in question_text:
            assert question.name == "CONSECUTIVE_QUESTION"
        else:
            assert question.name == "NEW_QUESTION"
    assert qlist == [f"question{c}" for c in "ABCDEFGHIJ"], qlist

    # Test questions order
    latex = c.get_latex()
    questions = []
    i = 0
    while i != -1:
        i = latex.find("question", i)
        if i != -1:
            i += len("question")
            questions.append(latex[i : i + 1])
    ordering = "".join(questions)
    assert "DEFGHI" in ordering
    assert ordering != "".join(sorted(questions))
    e0 = latex.find("ansE0")
    e1 = latex.find("ansE1")
    e2 = latex.find("ansE2")
    e3 = latex.find("ansE3")
    e4 = latex.find("ansE4")
    f1 = latex.find("ansF1")
    f2 = latex.find("ansF2")
    f3 = latex.find("ansF3")
    assert all(i != -1 for i in (e0, e1, e2, e3, e4, f1, f2, f3))
    assert max(f1, f2) < f3
    assert f1 < f3
    assert e0 < min(e1, e2, e3) < max(e1, e2, e3) < e4
    assert "\n\n" not in latex[f1:f2]
    assert "\n\n" in latex[f2:f3]
    assert "\n\n" not in latex[e0:e1]
    assert "\n\n" not in latex[e1:e2]
    assert "\n\n" not in latex[e2:e3]
    assert "\n\n" not in latex[e3:e4]


def test_include(monkeypatch, tmp_path):
    folder = copy_test("ptyx-files/with-exercises", tmp_path)
    monkeypatch.chdir(folder)
    c = load_ptyx_file(folder / "include.ptyx")
    # Test for support of:
    # - no star at all at the beginning of the question (must be automatically added)
    with open(folder / "exercises/ex1.ex") as f:
        assert not f.read().startswith("*")
    # - a line break after the star. This should be Ok too.
    with open(folder / "exercises/ex2.ex") as f:
        assert f.read().startswith("*\n")
    c.generate_syntax_tree()
    latex = c.get_latex()
    assert r"$2\times(-1)^2$" in latex
    assert "an other answer" in latex


def test_include_glob(monkeypatch, tmp_path):
    folder = copy_test("ptyx-files/with-exercises", tmp_path)
    monkeypatch.chdir(folder)
    c1 = load_ptyx_file(folder / "include.ptyx")
    c1.generate_syntax_tree()
    latex1 = c1.get_latex()
    c2 = load_ptyx_file(folder / "include_glob.ptyx")
    c2.generate_syntax_tree()
    latex2 = c2.get_latex()
    assert r"$2\times(-1)^2$" in latex2
    assert "an other answer" in latex2
    assert latex1.split() == latex2.split()


def test_question_context(tmp_path):
    folder = copy_test("ptyx-files/other", tmp_path)
    c = load_ptyx_file(folder / "questions_context.ptyx")
    c.generate_syntax_tree()
    latex = c.get_latex()

    for match in re.finditer(r"TEST\((\w+)=(\w+)\)", latex):
        assert match.group(1) == match.group(2)


def test_unicity_of_answers(tmp_path):
    folder = copy_test("ptyx-files/with-exercises", tmp_path)
    c = load_ptyx_file(folder / "unicity_of_answers.ptyx")
    c.generate_syntax_tree()
    try:
        c.get_latex()
        # The same answer appeared twice, it should have raised an error !
        assert False
    except SameAnswerError:
        # Alright, identical answers were detected.
        pass


def test_loading_of_sty_files(tmp_path):
    folder = copy_test("ptyx-files/with-exercises", tmp_path)
    c = load_ptyx_file(folder / "loading-sty-files.ptyx")
    c.generate_syntax_tree()
    latex = c.get_latex()
    latex_lines = latex.split("\n")
    for line in (r"\usepackage[table]{xcolor}", r"\usepackage{wasysym}"):
        if line not in latex_lines:
            print(repr(latex))
            assert False, f"Line {line} not found ! (See above)"


def test_neutralized_questions(tmp_path) -> None:
    folder = copy_test("ptyx-files/other", tmp_path)
    c = load_ptyx_file(folder / "neutralized_questions.ptyx")
    c.generate_syntax_tree()
    c.get_latex()
    data: Configuration = c.latex_generator.mcq_data
    answers = data.ordering[DocumentId(0)]["answers"]
    assert sorted(answers[OriginalQuestionNumber(1)]) == [(1, True), (2, None), (3, False)]
    assert sorted(answers[OriginalQuestionNumber(2)]) == [(1, False), (2, True), (3, None)]


def test_smallgraphlib_import_detection(tmp_path):
    from smallgraphlib.tikz_export import tikz_printer

    folder = copy_test("ptyx-files/with-exercises", tmp_path)
    c = load_ptyx_file(folder / "smallgraphlib.ptyx")
    c.generate_syntax_tree()
    latex = c.get_latex()
    # ptyx_code = c.plain_ptyx_code
    begin_document = latex.find(r"\begin{document}")
    for line in tikz_printer.latex_preamble_additions():
        # \usepackage{tikz} is already generated by the HEADER tag.
        if line != r"\usepackage{tikz}":
            position = latex.find(line)
            assert 0 <= position < begin_document, line


def test_verbatim_code(tmp_path):
    folder = copy_test("ptyx-files/format-answers", tmp_path)
    c = load_ptyx_file(folder / "verbatim_code.ptyx")
    c.generate_syntax_tree()
    latex = c.get_latex()
    extract = (
        r"\begin{minipage}{.45\linewidth}\ptyxMCQTab{\checkBox{white}{Q1-1}}{"
        r"\texttt{public~double~getNorm()~\{\linebreak\phantom{}~~~~int~i,~sum~=~0;"
        r"\linebreak\phantom{}~~~~for~(i=0;~i<counts.length;~i++)"
        r"~\{\linebreak\phantom{}~~~~~~~~sum~+=~counts[i]*counts[i];~\}\linebreak\phantom{}"
        r"~~~~return~Math.sqrt(sum);~\}}}\end{minipage}\quad"
    )
    assert extract in latex


def test_multiline_answers(tmp_path):
    folder = copy_test("ptyx-files/other", tmp_path)
    c = load_ptyx_file(folder / "multiline_answers.ptyx")
    c.generate_syntax_tree()
    latex = c.get_latex()
    print(latex)
    extract = (
        r"\ptyxMCQTab{\checkBox{white}{Q1-3}}{a penguin}\quad"
        "\n"
        r"\ptyxMCQTab{\checkBox{white}{Q1-6}}{\begin{tabular}[t]{l}"
        r"Well, this is an interesting question.\\Though, an elaborate multiline answer is needed.\\"
        r"Multiline answers like this one are supported, though this is not so commonly used..."
        r"\end{tabular}}"
    )
    assert extract in latex


def test_question_config(tmp_path):
    folder = copy_test("ptyx-files/other", tmp_path)
    c = load_ptyx_file(folder / "question_config.ptyx")
    c.generate_syntax_tree()
    c.get_latex()
    assert c.latex_generator.mcq_data.mode[1] == "all"
    assert c.latex_generator.mcq_data.mode[2] == "some"
    assert c.latex_generator.mcq_data.correct[1] == 2.0
    assert c.latex_generator.mcq_data.correct[2] == 3.0
    assert c.latex_generator.mcq_data.incorrect[1] == -1.0
    assert c.latex_generator.mcq_data.incorrect[2] == 4.0


def test_math_formatting(tmp_path):
    folder = copy_test("ptyx-files/format-answers", tmp_path)
    c = load_ptyx_file(folder / "math_formatting.ptyx")
    c.generate_syntax_tree()
    latex = c.get_latex()
    extract = (
        r"\ptyxMCQTab{\checkBox{white}{Q1-1}}{$2x$}\quad"
        "\n"
        r"\ptyxMCQTab{\checkBox{white}{Q1-2}}{$x^2$}\quad"
        "\n"
        r"\ptyxMCQTab{\checkBox{white}{Q1-4}}{$2x^2$}\quad"
        "\n"
        r"\ptyxMCQTab{\checkBox{white}{Q1-3}}{$x$}\quad"
        "\n"
    )
    assert extract in latex


def test_bug_verbatim(tmp_path):
    folder = copy_test("ptyx-files/bug-verbatim", tmp_path)
    c = load_ptyx_file(folder / "bug-verbatim.ptyx")
    c.generate_syntax_tree()
    latex = c.get_latex()
    assert r"\texttt{*~\{\linebreak\phantom{}~~margin:~0;\linebreak\phantom{}\}}" in latex


def test_bug_verbatim_ex(tmp_path):
    folder = copy_test("ptyx-files/bug-verbatim", tmp_path)
    c = load_ptyx_file(folder / "bug-verbatim-ex.ptyx")
    c.generate_syntax_tree()
    latex = c.get_latex()
    assert r"\texttt{*~\{\linebreak\phantom{}~~margin:~0;\linebreak\phantom{}\}}" in latex


@pytest.mark.xfail
def test_1(tmp_path):
    copy = copy_test("test-1", tmp_path)
    make(copy / "test.ptyx")


# @atexit.register
# def cleanup():
#     files_found = False
#     # Remove .ptyx.plain-ptyx files generated during tests.
#     for tmp_filename in (TEST_DIR / "ptyx-files").glob("*.ptyx.plain-ptyx"):
#         tmp_filename.unlink()
#         files_found = True
#     assert files_found
#     # for tmp_filename in TMP_PDF:
#     #     (TEST_DIR / Path(tmp_filename)).unlink()


if __name__ == "__main__":
    pass
