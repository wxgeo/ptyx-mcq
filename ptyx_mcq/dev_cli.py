#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
"""
ptyx MCQ Specific command line interface for development

@author: Nicolas Pourcelot
"""
import datetime
import tarfile
from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory

import argcomplete
from argcomplete import FilesCompleter

from ptyx_mcq.tools.io_tools import (
    print_success,
)


# noinspection PyTypeHints
def main(args: list[str] | None = None) -> None:
    """Main entry point, called whenever `mcq` command is executed."""
    parser = ArgumentParser(description="Development tools for pTyX-MCQ.")
    subparsers = parser.add_subparsers()
    add_parser = subparsers.add_parser

    # ------------------------------------------
    #     $ mcq-dev  export-checkboxes
    # ------------------------------------------
    # create the parser for the "export-checkboxes" command
    export_checkboxes_parser = add_parser(
        "export-checkboxes", help="Export all checkboxes. This is used to create tests."
    )
    export_checkboxes_parser.add_argument(  # type: ignore[attr-defined]
        "path", nargs="?", metavar="PATH", type=Path, default="."
    ).completer = FilesCompleter("ptyx")

    export_checkboxes_parser.set_defaults(func=export_checkboxes)

    # ------------------------------------------
    #     $ mcq-dev scan-picture
    # ------------------------------------------
    # create the parser for the "make" command
    scan_picture_parser = add_parser("scan-picture", help="Scan one picture for debugging.")
    scan_picture_parser.add_argument(  # type: ignore[attr-defined]
        "picture", metavar="PIC", type=Path
    ).completer = FilesCompleter("ptyx")
    scan_picture_parser.add_argument(  # type: ignore[attr-defined]
        "path", nargs="?", metavar="PATH", type=Path, default="."
    ).completer = FilesCompleter("ptyx")
    scan_picture_parser.set_defaults(func=scan_picture)

    # ------------------------------------------
    argcomplete.autocomplete(parser, always_complete_options=False)
    parsed_args = parser.parse_args(args)
    try:
        # Launch the function corresponding to the given subcommand.
        kwargs = vars(parsed_args)
        func = kwargs.pop("func")
    except KeyError:
        # No subcommand passed.
        parser.print_help()
        return
    func(**kwargs)


def scan_picture(
    picture: Path,
    path: Path | str = ".",
) -> None:
    """Implement `mcq scan` command."""
    from .scan.scan import MCQPictureParser

    MCQPictureParser(path).scan_picture(picture)
    print_success(f"Picture '{picture}' scanned.")


def export_checkboxes(path: Path | str = "."):
    from .scan.data_handler import DataHandler

    path = Path(path)
    now = datetime.datetime.now()
    tar_name = f"checkboxes-{now.year}-{now.month}-{now.day}-{now.hour}-{now.minute}-{now.second}.tar"
    with TemporaryDirectory() as tmp_dir:
        DataHandler(path).export_checkboxes(export_all=True, path=Path(tmp_dir))
        with tarfile.open(path / tar_name, "w") as tar:
            tar.add(tmp_dir)
    print_success(f"File {tar_name} created.")


if __name__ == "__main__":
    main()
