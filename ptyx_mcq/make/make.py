"""
Generate pdf file from raw mcq file.
"""
from pathlib import Path
from typing import Any

from ptyx.compilation import make_files, make_file
from ptyx.latex_generator import compiler, Compiler

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
    correction_only: bool = False,
    for_review: bool = False,
) -> None:
    """Implement `mcq make` command.

    If `only_correction` is `True`, only generate correction (useful for fast testing).
    If `for_review` is `True`, insert before each question its title; if a question has several versions,
    display them all too.
    """
    assert isinstance(num, int)
    ptyx_filename = parse_ptyx_file(path)

    if for_review:
        context: dict[str, Any] = {"MCQ_KEEP_ALL_VERSIONS": True, "MCQ_DISPLAY_QUESTION_TITLE": True}
        if not correction_only:
            # Generate a document including the different versions of all the questions.
            make_file(
                (ptyx_filename.parent / ptyx_filename.stem).with_suffix(".all.pdf"),
                context=context,
                quiet=quiet,
            )
        # Generate a document including the different versions of all the questions
        # with the correct answers checked.
        make_file(
            (ptyx_filename.parent / ptyx_filename.stem).with_suffix(".all-corr.pdf"),
            context=context | {"PTYX_WITH_ANSWERS": True},
            quiet=quiet,
        )
    else:
        # Compile and generate output files (tex or pdf)
        output_name, nums = make_files(
            ptyx_filename,
            correction=correction_only,
            compress=True,
            number_of_documents=num,
            fixed_number_of_pages=True,
            quiet=quiet,
            start=start,
            # cpu_cores=1,
        )
        if not correction_only:
            generate_config_file(compiler)

        # Keep track of the seed used.
        seed_value = compiler.seed
        seed_file_name = output_name.parent / ".seed"
        with open(seed_file_name, "w") as seed_file:
            seed_file.write(str(seed_value))

        if not correction_only:
            _, nums2 = make_files(ptyx_filename, correction=True, _nums=nums, compress=True, quiet=quiet)
            assert nums2 == nums, repr((nums, nums2))


def parse_ptyx_file(path):
    ptyx_filename = get_file_or_sysexit(path, extension=".ptyx")
    # Read pTyX file.
    print(f"Reading {ptyx_filename}...")
    compiler.reset()
    compiler.read_file(ptyx_filename)
    # Parse #INCLUDE tags, load extensions if needed, read seed.
    compiler.preparse()
    # Generate syntax tree.
    # The syntax tree is generated only once, and will then be used
    # for all the following compilations.
    compiler.generate_syntax_tree()
    return ptyx_filename
