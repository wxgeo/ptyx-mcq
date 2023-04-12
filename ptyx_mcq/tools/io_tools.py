import sys
import traceback
from pathlib import Path

ANSI_RESET = "\u001B[0m"
ANSI_BLACK = "\u001B[30m"
ANSI_RED = "\u001B[31m"
ANSI_GREEN = "\u001B[32m"
ANSI_YELLOW = "\u001B[33m"
ANSI_BLUE = "\u001B[34m"
ANSI_PURPLE = "\u001B[35m"
ANSI_CYAN = "\u001B[1;36m"
ANSI_WHITE = "\u001B[37m"
ANSI_GRAY = "\u001B[90m"
ANSI_BOLD = "\u001B[1m"
ANSI_REVERSE_PURPLE = "\u001B[45m"
ANSI_REVERSE_BLUE = "\u001B[44m"


shell_colors = {
    "red": 1,
    "green": 2,
    "yellow": 3,
    "blue": 4,
}


def custom_print(msg: str, color: str, label: str, bold=False, **kw) -> None:
    n = shell_colors[color]
    print(f"\33[3{n}m[\33[9{n}{';1' if bold else ''}m{label}\33[0m\33[3{n}m]\33[0m " + msg, **kw)


def print_error(msg: str) -> None:
    custom_print(msg, "red", "Error", bold=True, file=sys.stderr)


def print_warning(msg: str) -> None:
    custom_print(msg, "yellow", "Warning", bold=False)


def print_success(msg: str) -> None:
    custom_print(msg, "green", "OK", bold=True)


def print_info(msg: str) -> None:
    custom_print(msg, "blue", "Info", bold=False)


def get_file_or_sysexit(path: Path, *, extension: str) -> Path:
    """Get the path of the ptyx file corresponding to the given `path`.

    If the file is not found, exit calling `sys.exit(1)`.
    """
    try:
        return get_file_with_extension(path, extension=extension)
    except OSError:
        traceback.print_exc()
        resolve = f" ({path.resolve()})" if str(path) != path.resolve() else ""
        print(f"Searching for a '{extension}' file in '{path}'{resolve} failed !")
        print_error(f"No '{extension}' file found.")
        sys.exit(1)


def get_file_with_extension(path: Path, *, extension) -> Path:
    """Get the path of the ptyx file corresponding to the given `path`.

    If `path` is already the path of a ptyx file, just return `path` unchanged.
    Else, `path` must be a directory which contains a single ptyx file, and the path
    of this ptyx file is returned.

    Raise `FileNotFoundError` if `path` is neither a directory nor a ptyx file, or if `path`
    is a directory but contains no ptyx file or several ptyx files.
    """
    path = path.expanduser().resolve()
    if path.suffix == extension:
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
