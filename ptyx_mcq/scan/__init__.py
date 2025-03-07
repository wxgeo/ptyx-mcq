from pathlib import Path

from ptyx.pretty_print import print_success, print_warning, print_info

from ptyx_mcq.scan.scan_doc import MCQPictureParser
from ptyx_mcq.tools.io_tools import ProcessInterrupted


def scan(
    path: Path,
    reset: bool = False,
    cores: int = 0,
    test_picture: Path = None,
    debug: bool = False,
) -> "MCQPictureParser":
    """Implement `mcq scan` command.

    Return a `MCQPictureParser` instance, which may be used by tests to check the scan's result.
    """

    try:
        mcq_parser = MCQPictureParser(path)
        if test_picture is None:
            mcq_parser.run(number_of_processes=cores, debug=debug, reset=reset)
            print_success("Students' marks successfully generated. :)")
        else:
            mcq_parser.scan_single_picture(test_picture)
            print_success(f"Picture {test_picture!r} scanned.")
        return mcq_parser
    except KeyboardInterrupt:
        print()
        print_warning("Script interrupted.")
        print_info("Relaunch it to resume scan process.")
        raise ProcessInterrupted
