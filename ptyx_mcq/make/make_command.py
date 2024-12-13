"""
Generate pdf file from raw mcq file.
"""

import tempfile
from functools import partial
from pathlib import Path
from typing import Any

from ptyx.compilation import make_files, compile_latex_to_pdf
from ptyx.compilation_options import CompilationOptions
from ptyx.latex_generator import Compiler
from ptyx.shell import print_error, print_info
from ptyx.utilities import force_hardlink_to

from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq.tools.io_tools import get_file_or_sysexit, FatalError
from ptyx_mcq.tools.config_parser import (
    Configuration,
    Page,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    CbxRef,
)
from ptyx_mcq.make.exercises_parsing import wrap_exercise

DEFAULT_PTYX_MCQ_COMPILATION_OPTIONS = CompilationOptions(same_number_of_pages_compact=True, compress=True)


def _get_question_answer_num(tag: str) -> tuple[OriginalQuestionNumber, OriginalAnswerNumber]:
    """Get the question and answer numbers from the checkbox LaTeX tag."""
    q, a = map(int, tag[1:].split("-"))
    return OriginalQuestionNumber(q), OriginalAnswerNumber(a)


def generate_config_file(compiler: Compiler) -> None:
    mcq_data: Configuration = compiler.latex_generator.mcq_data  # type: ignore
    file_path = compiler.file_path
    assert file_path is not None
    folder = file_path.parent
    name = file_path.stem
    id_table_pos: tuple[float, float] | None = None
    for n in mcq_data.ordering:
        # XXX: what if files are not auto-numbered, but a list
        # of names is provided to Ptyx instead ?
        # (cf. command line options).
        if len(mcq_data.ordering) == 1:
            filename = f"{name}.pos"
        else:
            filename = f"{name}-{n}.pos"
        full_path = folder / ".compile" / name / filename
        # For each page of the document, give the position of every answer's checkbox.
        checkboxes_positions: dict[Page, dict[CbxRef, tuple[float, float]]] = {}
        mcq_data.boxes[n] = checkboxes_positions
        with open(full_path) as f:
            for line in f:
                tag, pos = line.split(": ", 1)
                tag = tag.strip()
                if tag == "ID-table":
                    if id_table_pos is None:
                        x, y = (float(s.strip("() \n")) for s in pos.split(","))
                        id_table_pos = x, y
                        mcq_data.id_table_pos = id_table_pos
                else:
                    page_, x_, y_ = [s.strip("p() \n") for s in pos.split(",")]
                    q, a = _get_question_answer_num(tag)
                    checkboxes_positions.setdefault(Page(int(page_)), {})[(q, a)] = (float(x_), float(y_))

    mcq_data.dump(file_path.with_suffix(CONFIG_FILE_EXTENSION))


def compile_exercise_to_latex(path: Path, **context: Any) -> tuple[str, Path]:
    """Compile an exercise to LaTeX code."""
    exercise_path = get_file_or_sysexit(path, extension=".ex")
    print(f"\n == Compiling exercise '{exercise_path}'. == \n")
    code = wrap_exercise(exercise_path.read_text(encoding="utf8"), exercise_path)
    context["MCQ_REMOVE_HEADER"] = True
    context["MCQ_PREVIEW_MODE"] = True
    print("Temporary pTyX file code:")
    print("\n" + 5 * "---✂---")
    print(code)
    print(5 * "---✂---" + "\n")
    compiler = Compiler()
    return compiler.parse(code=code, **context), exercise_path


def compile_exercise(path: Path) -> None:
    """Compile an exercise."""
    latex, ex_path = compile_exercise_to_latex(path)
    with tempfile.TemporaryDirectory() as tmpdir:
        texfile = Path(tmpdir) / ex_path.with_suffix(".tex").name
        texfile.write_text(latex, encoding="utf8")
        info = compile_latex_to_pdf(texfile)
        force_hardlink_to(ex_path.with_suffix(".pdf"), info.dest)


def make_command(
    path: Path,
    num: int = 1,
    start: int = 1,
    quiet: bool = False,
    with_correction: bool = False,
    for_review: bool = False,
    force: bool = False,
    context: dict[str, Any] | None = None,
) -> None:
    """Implement `mcq make` command.

    If `with_correction` is `True`, then a corrected version of the documents will also be generated.
    If `for_review` is `True`, insert before each question its title; if a question has several versions,
    display them all too.

    Dictionary `context` can be used to pass additional information to compiler.
    """
    assert isinstance(num, int)

    if context is None:
        context = {}

    ptyx_filename = get_file_or_sysexit(path, extension=".ptyx")
    if ptyx_filename.with_suffix(CONFIG_FILE_EXTENSION).is_file() and not force:
        if input("A previous compiled version exist, overwrite it (y∕N) ?") not in ("y", "Y"):
            print_info("You may use `mcq scan --force` or `mcq scan -f` to force recompilation.")
            print_error("Conflict with a previous file, no file was generated.")
            raise FatalError
    print(f"Reading {ptyx_filename}...")
    compiler = Compiler(path=ptyx_filename)

    make = partial(make_files, compiler=compiler)

    if for_review:
        context |= {"MCQ_KEEP_ALL_VERSIONS": True, "MCQ_DISPLAY_QUESTION_TITLE": True}
        # Generate a document including the different versions of all the questions
        # with the correct answers checked.
        make(
            ptyx_filename,
            output_basename=f"{ptyx_filename.stem}.review",
            correction=True,
            options=CompilationOptions(context=context | {"PTYX_WITH_ANSWERS": True}, quiet=quiet),
        )

    else:
        # Compile and generate output files (tex or pdf)
        all_info, _ = make(
            ptyx_filename,
            number_of_documents=num,
            options=DEFAULT_PTYX_MCQ_COMPILATION_OPTIONS.updated(start=start, quiet=quiet),
            # cpu_cores=1,
        )
        generate_config_file(compiler)

        # Keep track of the seed used.
        seed_value = compiler.seed
        with open(all_info.directory / ".seed", "w") as seed_file:
            seed_file.write(str(seed_value))

        if with_correction:
            corr_info, _ = make(
                ptyx_filename,
                correction=True,
                doc_ids_selection=all_info.doc_ids,
                options=CompilationOptions(compress=True, quiet=quiet),
            )
            assert corr_info.doc_ids == all_info.doc_ids, repr((all_info.doc_ids, corr_info.doc_ids))
