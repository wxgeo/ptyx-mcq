import traceback
from pathlib import Path

from ptyx.shell import print_success, print_error

from ptyx_mcq import FatalError
from ptyx_mcq.make.make_command import make_command


def make(
    path: Path,
    num: int = 1,
    start: int = 1,
    quiet: bool = False,
    with_correction: bool = False,
    for_review: bool = False,
    force: bool = False,
) -> None:
    """Wrapper for make_command(), so that `argparse` module don't intercept exceptions."""

    try:
        make_command(path, num, start, quiet, with_correction, for_review, force)
        print_success(f"Document was successfully generated in {num} version(s).")
    except Exception as e:  # noqa
        if hasattr(e, "msg"):
            traceback.print_tb(e.__traceback__)
            print(e.msg)
            print(f"\u001b[31m{e.__class__.__name__}:\u001b[0m {e}")
        else:
            traceback.print_exc()
        print()
        print_error("`mcq make` failed to build document (see above for details).")
        raise FatalError
