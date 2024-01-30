"""
Generate pdf file from raw mcq file.
"""
from functools import partial
from pathlib import Path
from typing import Any

from ptyx.compilation import make_files
from ptyx.compilation_options import CompilationOptions
from ptyx.latex_generator import Compiler

from ptyx_mcq.scan.document_data import Page
from ptyx_mcq.tools.io_tools import get_file_or_sysexit
from ptyx_mcq.tools.config_parser import Configuration


def generate_config_file(_compiler: Compiler) -> None:
    mcq_data: Configuration = _compiler.latex_generator.mcq_data
    file_path = _compiler.file_path
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
        checkboxes_positions: dict[Page, dict[str, tuple[float, float]]] = {}
        mcq_data.boxes[n] = checkboxes_positions
        with open(full_path) as f:
            for line in f:
                k, v = line.split(": ", 1)
                k = k.strip()
                if k == "ID-table":
                    if id_table_pos is None:
                        x, y = (float(s.strip("() \n")) for s in v.split(","))
                        id_table_pos = x, y
                        mcq_data.id_table_pos = id_table_pos
                    continue
                page_, x_, y_ = [s.strip("p() \n") for s in v.split(",")]
                checkboxes_positions.setdefault(Page(int(page_)), {})[k] = (float(x_), float(y_))

    mcq_data.dump(file_path.with_suffix(".ptyx.mcq.config.json"))


def make_command(
    path: Path,
    num: int = 1,
    start: int = 1,
    quiet: bool = False,
    with_correction: bool = False,
    for_review: bool = False,
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
    print(f"Reading {ptyx_filename}...")
    compiler = Compiler(path=ptyx_filename)

    make = partial(make_files, compiler=compiler)

    if for_review:
        context |= {"MCQ_KEEP_ALL_VERSIONS": True, "MCQ_DISPLAY_QUESTION_TITLE": True}
        # Generate a document including the different versions of all the questions
        # with the correct answers checked.
        make(
            (ptyx_filename.parent / ptyx_filename.stem).with_suffix(".all-corr.pdf"),
            options=CompilationOptions(context=context | {"PTYX_WITH_ANSWERS": True}, quiet=quiet),
        )
    else:
        # Compile and generate output files (tex or pdf)
        all_info = make(
            ptyx_filename,
            number_of_documents=num,
            options=CompilationOptions(
                same_number_of_pages_compact=True, compress=True, start=start, quiet=quiet
            )
            # cpu_cores=1,
        )
        generate_config_file(compiler)

        # Keep track of the seed used.
        seed_value = compiler.seed
        with open(all_info.directory / ".seed", "w") as seed_file:
            seed_file.write(str(seed_value))

        if with_correction:
            corr_info = make(
                ptyx_filename,
                correction=True,
                doc_ids_selection=all_info.doc_ids,
                options=CompilationOptions(compress=True, quiet=quiet),
            )
            assert corr_info.doc_ids == all_info.doc_ids, repr((all_info.doc_ids, corr_info.doc_ids))
