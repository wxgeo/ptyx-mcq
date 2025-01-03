import sys
import traceback
from pathlib import Path
from typing import Type, Callable

from mypy.ipc import TracebackType
from ptyx.shell import print_error


class FatalError(BaseException):
    """Request main script to exit on current error.

    Not that ptyx-mcq main script won't display any traceback for this error.
    The rational is that any traceback should have been printed before, and
    then a meaningful error summary, which should be the last printed information.
    """


class ProcessInterrupted(BaseException):
    """Process was aborted by user."""


def is_ptyx_file(path: Path) -> bool:
    """Test whether the file looks like a pTyX file."""
    if not path.is_file():
        return False
    with open(path) as f:
        return "#LOAD{mcq}" in f.read(1000)


def get_file_or_sysexit(path: Path, *, extension: str, autodetect_ptyx_files=True) -> Path:
    """Get the path of the file corresponding to the given `path`, with given extension.

    If the file is not found, exit calling `sys.exit(1)`.
    """
    try:
        return get_file_with_extension(path, extension=extension, autodetect_ptyx_files=autodetect_ptyx_files)
    except OSError:
        traceback.print_exc()
        resolve = f" ({path.resolve()})" if str(path) != str(path.resolve()) else ""
        print(f"Searching for a '{extension}' file in '{path}'{resolve} failed !")
        print_error(f"No '{extension}' file found.")
        raise FatalError


def get_file_with_extension(path: Path, *, extension, autodetect_ptyx_files=True) -> Path:
    """Get the path of the ptyx file corresponding to the given `path`.

    If `path` is already the path of a ptyx file, just return `path` unchanged.
    Else, `path` must be a directory which contains a single ptyx file, and the path
    of this ptyx file is returned.



    Raise `FileNotFoundError` if `path` is neither a directory nor a ptyx file, or if `path`
    is a directory but contains no ptyx file or several ptyx files.
    """
    path = path.expanduser().resolve()
    if autodetect_ptyx_files and extension == ".ptyx" and is_ptyx_file(path):
        return path
    if path.name.endswith(extension):
        if not path.is_file():
            raise FileNotFoundError(f"File '{path}' not found.")
    else:
        found_files: list[Path] = list(path.glob("*" + extension))
        if len(found_files) == 0:
            raise FileNotFoundError(f"No '{extension}' file found in '{path}'.")
        elif len(found_files) > 1:
            raise FileNotFoundError(
                f"Several {extension} file found in '{path}', I don't know which one to chose."
            )
        path = found_files[0]
    return path


# config_path = config_path.expanduser().resolve()
#         if config_path.is_dir():
#             self.configfile = search_by_extension(config_path, ".ptyx.mcq.config.json")
#         elif config_path.is_file():
#             self.configfile = config_path.with_suffix(".ptyx.mcq.config.json")
#             if not self.configfile.is_file():
#                 raise FileNotFoundError(f"File '{self.configfile}' not found.")


# def search_by_extension(directory: Path, ext: str) -> Path:
#     """Search for a file with extension `ext` in given directory.
#
#     Search is NOT case sensible.
#     If no or more than one file is found, an error is raised.
#     """
#     ext = ext.lower()
#     paths = [pth for pth in directory.glob("*") if pth.name.lower().endswith(ext)]
#     if not paths:
#         raise FileNotFoundError(f"No {ext!r} file found in that directory: {directory} ! ")
#     elif len(paths) > 1:
#         raise RuntimeError(
#             f"Several {ext!r} file found in that directory: {directory} ! "
#             "Keep only one of them and delete all the others (or rename their extensions)."
#         )
#     return paths[0]
def print_framed_msg(msg: str) -> None:
    decoration = max(len(line) for line in msg.split("\n")) * "-"
    print(decoration)
    print(msg)
    print(decoration)


class Silent:
    """A context manager enabling to discard or redirect any stdout output for a while.

    with Silent():
        ...
    """

    def __init__(self, *, silent=True, log_file: Path | None = None, reset_log=False):
        self.silent = silent
        self.log_file = log_file
        if reset_log and log_file is not None and log_file.is_file():
            open(self.log_file, "w").close()

    def __enter__(self):
        if self.silent:
            self.stdout = sys.stdout
            sys.stdout = self
        self.file = None if self.log_file is None else open(self.log_file, "a", encoding="utf8")

    # noinspection PyShadowingNames
    def __exit__(
        self,
        exception_type: Type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType,
    ) -> None:
        if self.silent:
            sys.stdout = self.stdout
        if self.file is not None:
            self.file.close()

    def write(self, s: str) -> None:
        if self.file is not None:
            self.file.write(s)

    def flush(self) -> None:
        if self.file is not None:
            self.file.flush()


def _progression_coroutin(message: str, last_val: int):
    print()
    for i in range(1, last_val):
        print(f"{message}: {i}/{last_val}...", end="\r")
        yield
    print(f"{message}: DONE." + 2 * len(str(last_val)) * " ")
    while True:
        yield


def generate_progression_callback(message: str, last_val: int) -> Callable[[], None]:
    """
    Generate a function that can be used to display a progression in a terminal.

    Each time the function will be called, +1 will be added and the progression updated,
    until last value `last_val` is reached, then the progression will be displayed as completed.
    """
    generator = _progression_coroutin(message, last_val)

    def progression(*args, **kw) -> None:
        generator.__next__()

    return progression
