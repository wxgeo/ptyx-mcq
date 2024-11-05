from pathlib import Path

from ptyx.shell import print_error, print_success

from ptyx_mcq import FatalError
from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq.tools.config_parser import Configuration
from ptyx_mcq.tools.io_tools import get_file_or_sysexit
from ptyx_mcq.make.include_directives_parsing import update_file
from ptyx.latex_generator import Compiler


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
    # the same holds for the answers (but their labelling as correct
    # or incorrect is allowed to change).
    if not same_questions_and_answers_numbers(data, config):
        cmd = f"mcq make {path}"
        sep = len(cmd) * "-"
        cmd = f"{sep}\n{cmd}\n{sep}\n"
        print_error("Questions or answers changed.\n" "You must run a full compilation:\n" + cmd)
        raise FatalError

    # Get back the positions of checkboxes from last full compilation.
    data.id_table_pos = config.id_table_pos
    data.boxes = config.boxes
    data.dump(config_file.parent / (config_file.name.split(".")[0] + CONFIG_FILE_EXTENSION))
    print_success("Configuration file was successfully updated.")


def same_questions_and_answers_numbers(config1: Configuration, config2: Configuration) -> bool:
    if list(config1.ordering) != list(config2.ordering):
        return False
    for doc_id in config1.ordering:
        ordering1 = config1.ordering[doc_id]
        ordering2 = config2.ordering[doc_id]
        if ordering1["questions"] != ordering2["questions"]:
            return False
        if list(ordering1["answers"]) != list(ordering2["answers"]):
            return False

        for q in ordering1["answers"]:
            if [a for a, _ in ordering1["answers"][q]] != [a for a, _ in ordering2["answers"][q]]:
                return False
    return True


def update_exercises(path: Path, force=False, clean=False) -> None:
    """Update the list of included exercises."""

    ptyxfile_path = get_file_or_sysexit(path, extension=".ptyx")
    update_file(ptyxfile_path, force=force, clean=clean)
    print_success("The list of included files was successfully updated.")
