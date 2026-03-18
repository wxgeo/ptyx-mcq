#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
"""
ptyx MCQ Specific command line interface for development

@author: Nicolas Pourcelot
"""
from argparse import ArgumentParser
from enum import StrEnum
from pathlib import Path
from typing import Optional

from argcomplete import FilesCompleter

from ptyx_mcq.cli import launcher


class DevHandlers(StrEnum):
    export_checkboxes = "ptyx_mcq.other_commands.dev.export_checkboxes"
    calibration = "ptyx_mcq.other_commands.dev.calibration"
    review = "ptyx_mcq.other_commands.dev.review"


# noinspection PyTypeHints
def create_mcq_dev_arg_parser() -> ArgumentParser:
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

    export_checkboxes_parser.set_defaults(handler=DevHandlers.export_checkboxes)

    # ------------------------------------------
    #     $ mcq-dev review
    # ------------------------------------------
    # create the parser for the "make" command
    review_picture_parser = add_parser("review", help="Review one picture for debugging.")
    review_picture_parser.add_argument(
        "picture", metavar="PIC", type=Path
    )  # .completer = FilesCompleter("ptyx")
    review_picture_parser.add_argument(  # type: ignore[attr-defined]
        "path", nargs="?", metavar="PATH", type=Path, default="."
    ).completer = FilesCompleter("ptyx")
    review_picture_parser.set_defaults(handler=DevHandlers.review)

    # ------------------------------------------
    #     $ mcq-dev calibration
    # ------------------------------------------
    # create the parser for the "make" command
    calibration_picture_parser = add_parser(
        "calibration", help="Display the picture calibration information."
    )
    calibration_picture_parser.add_argument(
        "picture", metavar="PIC", type=Path
    )  # .completer = FilesCompleter("ptyx")
    calibration_picture_parser.add_argument(  # type: ignore[attr-defined]
        "path", nargs="?", metavar="PATH", type=Path, default="."
    ).completer = FilesCompleter("ptyx")
    calibration_picture_parser.set_defaults(handler=DevHandlers.calibration)

    return parser


def main(args: Optional[list] = None, _restart_process_if_needed=True) -> None:
    launcher(create_mcq_dev_arg_parser, args, _restart_process_if_needed=_restart_process_if_needed)


if __name__ == "__main__":
    main()
