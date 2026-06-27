from pathlib import Path

from ptyx.latex_generator import Compiler
from ptyx.pretty_print import print_error, print_success, print_warning, print_info
from ptyx_mcq.make.include_directives.update import update_file
from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq.scan.data import ScanData
from ptyx_mcq.tools.io_tools import FatalError, get_file_or_sysexit
from ptyx_mcq.tools.parse_config.config import Configuration


def update_cached_names(config_path: Path):
    """
    Update the students' names in cache.
    """
    ScanData(config_path).synchronize_students_names()


def update_config_file(path: Path) -> None:
    """Update the .ptyx.mcq.config.json configuration file, following any .ptyx file change.

    Path `path` must be either a pTyx file, or a directory containing a single pTyX file.
    """

    config_file = get_file_or_sysexit(path, extension=CONFIG_FILE_EXTENSION)
    print(f"Reading {config_file}...")
    config = Configuration.load(config_file)
    ptyx_filename = get_file_or_sysexit(path, extension=".ptyx")
    print(f"Reading {ptyx_filename}...")
    compiler = Compiler(path=ptyx_filename)
    # Compile ptyx file to LaTeX, to update information, but without compiling
    # LaTeX, which is slow (don't generate pdf files again).
    for doc_id in config.ordering:
        compiler.get_latex(PTYX_NUM=doc_id)
    # Update configuration
    data: Configuration = compiler.latex_generator.mcq_data  # type: ignore
    # Test compatibility of `data` with `config`:
    # The number of questions and their ordering should not have changed,
    # the same holds for the answers (but their labeling as correct
    # or incorrect is allowed to change).
    output_path = config_file.parent / (config_file.name.split(".")[0] + CONFIG_FILE_EXTENSION)
    ok, msg = same_questions_and_answers_numbers(data, config)
    if not ok:
        cmd = f"mcq make {path}"
        sep = len(cmd) * "-"
        cmd = f"{sep}\n{cmd}\n{sep}\n"
        if msg:
            print_warning(msg)
        print_error(
            "The number or ordering of the questions or answers changed.\n"
            "You must run a full compilation (you should make a backup of the folder first):\n" + cmd
        )
        data.dump(failed_output_path := output_path.with_suffix(".fail"))
        print_info(
            f"The failed attempt was stored in {failed_output_path.name!r}.\n"
            "You can inspect it with the following command:\n"
            f"diff '{output_path}' '{failed_output_path}' | less -R"
        )
        raise FatalError

    # Get back the positions of checkboxes from last full compilation.
    data.id_table_pos = config.id_table_pos
    data.boxes = config.boxes
    data.dump(output_path)
    # Students names' cached values must be updated, because the names may have been updated in the config file.
    update_cached_names(config_file)
    print_success("Configuration file was successfully updated.")


def same_questions_and_answers_numbers(config1: Configuration, config2: Configuration) -> tuple[bool, str]:
    """Check that the number of questions and answers per question is the same in both config files."""
    delta_doc = set(config1.ordering).symmetric_difference(set(config2.ordering))
    if delta_doc:
        return False, f"Those documents are found only in one configuration and not the other: {delta_doc}."
    for doc_id in config1.ordering:
        ordering1 = config1.ordering[doc_id]
        ordering2 = config2.ordering[doc_id]
        if ordering1["questions"] != ordering2["questions"]:
            return False, f"The number of questions or their order changed for document {doc_id} (at least)."
        if list(ordering1["answers"]) != list(ordering2["answers"]):
            # Should not occur, either a bug or a corrupted configuration file (maybe because of a manual edition).
            return False, f"Incoherent questions data for document {doc_id} (at least)."

        for q in ordering1["answers"]:
            if [a for a, _ in ordering1["answers"][q]] != [a for a, _ in ordering2["answers"][q]]:
                return (
                    False,
                    f"The number of answers or their order changed for the question {q}"
                    " of the document {doc_id} (at least).",
                )
    return True, ""


def update_exercises(path: Path, force=False, clean=False) -> None:
    """Update the list of included exercises."""

    ptyxfile_path = get_file_or_sysexit(path, extension=".ptyx")
    update_file(ptyxfile_path, force=force, clean=clean)
    print_success("The list of included files was successfully updated.")
