import subprocess
from pathlib import Path

from ptyx.shell import print_error, print_warning, print_info

from ptyx_mcq.tools.io_tools import FatalError


def see(name: str) -> None:
    """Display the pdf corresponding to the given student."""
    if "*" not in name:
        name = f"*{name}*"
    if not name.endswith(".pdf"):
        name += ".pdf"
    directory = Path.cwd() / ".scan/pdf"
    if not directory.is_dir():
        print_error("No scan results found, run `mcq scan .` first or change directory.")
        raise FatalError
    results = list(directory.glob(name))
    # TODO: use `case_sensitive=False` once python 11 support is dropped.
    if len(results) > 1:
        print_warning("Several matching files:")
        for path in results:
            print_warning(f"  - {path.stem}")
    elif len(results) == 0:
        print_warning("No matching file.")
    else:
        print_info(f"Displaying {results[0]}")
        subprocess.run(["xdg-open", str(results[0])])
