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

from ptyx.latex_generator import compiler

from ptyx_mcq.tools.config_parser import Configuration
from ptyx_mcq.tools.io_tools import print_success, print_error, get_file_or_sysexit

from .make.make import make, parse_ptyx_file
from .scan.scan import scan


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

    # create the parser for the "update" command
    new_parser = add_parser("update", help="Update mcq configuration file.")
    new_parser.add_argument("path", nargs="?", metavar="PATH", type=Path, default=".")
    new_parser.set_defaults(func=update)

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


def new(path: Path) -> None:
    """Implement `mcq new` command."""
    template = Path(__file__).resolve().parent / "template"
    if path.exists():
        print_error(f"Path {path} already exists.")
        sys.exit(1)
    else:
        shutil.copytree(template, path)
        print_success(f"A new MCQ was created at {path}.")


def clear(path: Path) -> None:
    """Implement `mcq clear` command."""
    try:
        ptyxfile_path = get_file_or_sysexit(path, extension=".ptyx")
    except FileNotFoundError:
        print(f"Searching for a ptyx file in '{path}' ({path.resolve()}) failed !")
        print_error("No ptyx file found.")
        sys.exit(1)
    filename = ptyxfile_path.name
    root = ptyxfile_path.parent
    for directory in (".scan", ".compile"):
        try:
            shutil.rmtree(root / directory)
        except FileNotFoundError as e:
            print(f"Warning: {e}")
            print(f"Info: '{directory}' not found...")
    for filepath in (
        ptyxfile_path.with_suffix(".pdf"),
        ptyxfile_path.with_suffix(".ptyx.mcq.config.json"),
        ptyxfile_path.with_name(f".{filename}.plain-ptyx"),
        ptyxfile_path.with_name(f"{ptyxfile_path.stem}-corr.pdf"),
    ):
        try:
            unlink(filepath)
        except FileNotFoundError as e:
            print(f"Warning: {e}")
            print(f"Info: '{filepath}' not found...")
    print_success("Directory cleared.")


def update(path: Path) -> None:
    config_file = get_file_or_sysexit(path, extension=".ptyx.mcq.config.json")
    config = Configuration.load(config_file)
    parse_ptyx_file(path)
    # Compile ptyx file to LaTeX, to update information, but without compiling
    # LaTeX, which is slow (don't generate pdf files again).
    for doc_id in config.ordering:
        compiler.get_latex(PTYX_NUM=doc_id)
    # Update configuration
    data: Configuration = compiler.latex_generator.mcq_data
    # Test compatibility of `data` with `config`:
    # The number of questions and their ordering should not have change,
    # the same holds for the answers (but their labelling as correct
    # or incorrect is allowed to change).
    if not same_questions_and_answers_numbers(data, config):
        cmd = f"mcq make {path}"
        sep = len(cmd) * "-"
        cmd = f"{sep}\n{cmd}\n{sep}\n"
        print_error("Questions or answers changed.\n" "You must run a full compilation:\n" + cmd)

    # Get back the positions of checkboxes from last full compilation.
    data.id_table_pos = config.id_table_pos
    data.boxes = config.boxes
    data.dump(config_file.parent / (config_file.name.split(".")[0] + ".ptyx.mcq.config.json"))
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


if __name__ == "__main__":
    main()
