"""
Generate pdf file from raw mcq file.
"""
import sys
import traceback
from pathlib import Path

from ptyx.compilation import make_files, make_file
from ptyx.latex_generator import compiler, Compiler
from ptyx_mcq.io_tools import print_error, print_success, get_file_or_sysexit

from ..tools.config_parser import dump, Configuration


def generate_config_file(_compiler: Compiler) -> None:
    mcq_data: Configuration = _compiler.latex_generator.mcq_data
    file_path = _compiler.file_path
    assert file_path is not None
    folder = file_path.parent
    name = file_path.stem
    id_table_pos = None
    for n in mcq_data["ordering"]:
        # XXX: what if files are not auto-numbered, but a list
        # of names is provided to Ptyx instead ?
        # (cf. command line options).
        if len(mcq_data["ordering"]) == 1:
            filename = f"{name}.pos"
        else:
            filename = f"{name}-{n}.pos"
        full_path = folder / ".compile" / name / filename
        # For each page of the document, give the position of every answer's checkbox.
        checkboxes_positions: dict[int, dict[str, tuple[float, float]]] = {}
        mcq_data["boxes"][n] = checkboxes_positions
        with open(full_path) as f:
            for line in f:
                k, v = line.split(": ", 1)
                k = k.strip()
                if k == "ID-table":
                    if id_table_pos is None:
                        id_table_pos = tuple(float(s.strip("() \n")) for s in v.split(","))
                        assert len(id_table_pos) == 2
                        mcq_data["id_table_pos"] = id_table_pos  # type: ignore
                    continue
                page, x, y = [s.strip("p() \n") for s in v.split(",")]
                checkboxes_positions.setdefault(int(page), {})[k] = (float(x), float(y))

    config_file = file_path.with_suffix(".ptyx.mcq.config.json")
    dump(config_file, mcq_data)


def make(
    path: Path, num: int = 1, start: int = 1, quiet: bool = False, correction_only: bool = False
) -> None:
    """Wrapper for _make(), so that `argparse` module don't intercept exceptions."""
    try:
        _make(path, num, start, quiet, correction_only)
        print_success(f"Document was successfully generated in {num} version(s).")
    except Exception as e:  # noqa
        if hasattr(e, "msg"):
            traceback.print_tb(e.__traceback__)
            print(e.msg)  # type: ignore
            print(f"\u001b[31m{e.__class__.__name__}:\u001b[0m {e}")
        else:
            traceback.print_exc()
        print()
        print_error("`mcq make` failed to build document (see above for details).")
        sys.exit(1)


def _make(
    path: Path, num: int = 1, start: int = 1, quiet: bool = False, correction_only: bool = False
) -> None:
    """Implement `mcq make` command.

    If `only_correction` is `True`, only generate correction (useful for fast testing).
    """
    assert isinstance(num, int)
    ptyx_filename = get_file_or_sysexit(path, extension=".ptyx")
    # Read pTyX file.
    print(f"Reading {ptyx_filename}...")
    compiler.read_file(ptyx_filename)
    # Parse #INCLUDE tags, load extensions if needed, read seed.
    compiler.preparse()

    # Generate syntax tree.
    # The syntax tree is generated only once, and will then be used
    # for all the following compilations.
    compiler.generate_syntax_tree()

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
    generate_config_file(compiler)

    # Keep track of the seed used.
    seed_value = compiler.seed
    seed_file_name = output_name.parent / ".seed"
    with open(seed_file_name, "w") as seed_file:
        seed_file.write(str(seed_value))

    if not correction_only:
        _, nums2 = make_files(ptyx_filename, correction=True, _nums=nums, compress=True, quiet=quiet)
        assert nums2 == nums, repr((nums, nums2))

        # Generate a document including the different versions of all the questions.
        make_file(
            (output_name.parent / output_name.stem).with_suffix(".all.pdf"),
            context={"MCQ_KEEP_ALL_VERSIONS": True},
            quiet=quiet,
        )
        # Generate a document including the different versions of all the questions
        # with the correct answers checked.
        make_file(
            (output_name.parent / output_name.stem).with_suffix(".all-corr.pdf"),
            context={"MCQ_KEEP_ALL_VERSIONS": True, "PTYX_WITH_ANSWERS": True},
            quiet=quiet,
        )