import shutil
from os import unlink
from pathlib import Path

from ptyx.shell import print_success

from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq.tools.io_tools import get_file_or_sysexit


def clear(path: Path) -> None:
    """Implement `mcq clear` command."""
    ptyxfile_path = get_file_or_sysexit(path, extension=".ptyx")
    filename = ptyxfile_path.name
    root = ptyxfile_path.parent
    for directory in ("out/.cache", ".compile"):
        try:
            shutil.rmtree(root / directory)
        except FileNotFoundError as e:
            print(f"Warning: {e}")
            print(f"Info: '{directory}' not found...")
    for filepath in (
        ptyxfile_path.with_suffix(".pdf"),
        ptyxfile_path.with_suffix(CONFIG_FILE_EXTENSION),
        ptyxfile_path.with_name(f".{filename}.plain-ptyx"),
        ptyxfile_path.with_name(f"{ptyxfile_path.stem}-corr.pdf"),
    ):
        try:
            unlink(filepath)
        except FileNotFoundError as e:
            print(f"Warning: {e}")
            print(f"Info: '{filepath}' not found...")
    print_success("Directory cleared.")
