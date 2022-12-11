#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ptyx MCQ Command Line Interface

@author: Nicolas Pourcelot
"""
import shutil
import sys
from argparse import ArgumentParser
from os import unlink

from pathlib import Path
from typing import Optional

from .compile.make import make, get_ptyxfile_path
from .scan.scanner import scan


def main(args: Optional[list] = None) -> None:
    """Main entry point, called whenever `mcq` command is executed."""
    parser = ArgumentParser(description="Generate and manage pdf MCQs.")
    subparsers = parser.add_subparsers()
    add_parser = subparsers.add_parser

    # create the parser for the "new" command
    new_parser = add_parser("new", help="Create an empty ptyx file.")
    new_parser.add_argument("path", nargs="?", metavar="PATH", type=Path, default="new-mcq")
    new_parser.set_defaults(func=new)

    # create the parser for the "make" command
    make_parser = add_parser("make", help="Generate pdf file.")
    make_parser.add_argument("path", nargs="?", metavar="PATH", type=Path, default=".")
    make_parser.add_argument(
        "--num",
        "-n",
        metavar="N",
        type=int,
        default=1,
        help="Specify how many versions of the document must be generated.",
    )
    make_parser.add_argument(
        "--start",
        "-s",
        metavar="START",
        type=int,
        default=1,
        help="First document number (default=1).",
    )
    make_parser.add_argument("--quiet", "-q", action="store_true", help="Hide pdflatex output.")
    make_parser.add_argument(
        "--correction-only", "-co", action="store_true", help="Generate only correction for fast testing."
    )
    make_parser.set_defaults(func=make)

    # create the parser for the "scan" command
    scan_parser = add_parser("scan", help="Generate scores from scanned documents.")
    scan_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help=(
            "Path to a directory which must contain "
            "a .mcq.config file and a .scan.pdf file "
            "(alternatively, this path may point to any file in this folder)."
        ),
    )

    scan_parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all cached data." "The scanning process will restart from the beginning.",
    )

    scan_parser.add_argument(
        "--verify",
        "--manual-verification",
        choices=("always", "never", "auto"),
        default="auto",
        help="If set to `always`, then for each page scanned, display a picture of "
        "the interpretation by the detection algorithm, "
        "for manual verification.\n"
        "If set to `never`, always assume algorithm is right.\n"
        "Default is `auto`, i.e. only ask for manual verification "
        "in case of ambiguity.",
    )

    scan_parser.add_argument(
        "--ask-for-name",
        action="store_true",
        default=False,
        help="For each first page, display a picture of " "the top of the page and ask for the student name.",
    )

    scan_parser.set_defaults(func=scan)

    # create the parser for the "clear" command
    new_parser = add_parser("clear", help="Remove every MCQ data but the ptyx file.")
    new_parser.add_argument("path", nargs="?", metavar="PATH", type=Path, default=".")
    new_parser.set_defaults(func=clear)

    parsed_args = parser.parse_args(args)
    try:
        # Launch the function corresponding to the given subcommand.
        kwargs = vars(parsed_args)
        kwargs.pop("func")(**kwargs)
    except KeyError:
        # No subcommand passed.
        parser.print_help()


def new(path: Path) -> None:
    """Implement `mcq new` command."""
    template = Path(__file__).resolve().parent / "template"
    if path.exists():
        print(f"ERROR: path {path} already exists.", file=sys.stderr)
        sys.exit(1)
    else:
        shutil.copytree(template, path)
        print(f"Success: a new MCQ was created at {path}.")


def clear(path: Path) -> None:
    """Implement `mcq clear` command."""
    try:
        ptyxfile_path = get_ptyxfile_path(path)
    except FileNotFoundError:
        print("\33[31m[Error]\33[0m No ptyx file found.")
        return
    filename = ptyxfile_path.name
    for directory in (".scan", ".compile"):
        try:
            shutil.rmtree(directory)
        except FileNotFoundError:
            print(f"Info: '{directory}' not found...")
    for filepath in (
        ptyxfile_path.with_suffix(".pdf"),
        ptyxfile_path.with_suffix(".ptyx.autoqcm.config.json"),
        ptyxfile_path.with_name(f".{filename}.plain-ptyx"),
        ptyxfile_path.with_name(f"{ptyxfile_path.stem}-corr.pdf"),
    ):
        try:
            unlink(filepath)
        except FileNotFoundError:
            print(f"Info: '{filepath}' not found...")
    print("\33[32m[OK]\33[0m Directory cleared.")


if __name__ == "__main__":
    main()
