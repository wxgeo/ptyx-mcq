#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
"""
ptyx MCQ Command Line Interface

@author: Nicolas Pourcelot
"""
import os
import shutil
import sys
import traceback
from argparse import ArgumentParser
from os import unlink
from pathlib import Path
from typing import Optional, Literal

import argcomplete
from platformdirs import PlatformDirs

from ptyx_mcq.tools.config_parser import Configuration
from ptyx_mcq.tools.io_tools import (
    print_success,
    print_error,
    get_file_or_sysexit,
    ANSI_RESET,
    ANSI_REVERSE_PURPLE,
    ANSI_REVERSE_BLUE,
    ANSI_BLUE,
    print_warning,
    print_info,
)


def main(args: Optional[list] = None) -> None:
    """Main entry point, called whenever `mcq` command is executed."""
    parser = ArgumentParser(description="Generate and manage pdf MCQs.")
    subparsers = parser.add_subparsers()
    add_parser = subparsers.add_parser

    # create the parser for the "new" command
    new_parser = add_parser("new", help="Create an empty ptyx file.")
    new_parser.add_argument("path", nargs="?", metavar="PATH", type=Path, default="new-mcq")
    new_parser.add_argument(
        "--include",
        "-i",
        metavar="INCLUDE_PATH",
        type=Path,
        help="Include all files from this path in the generated .ptyx file.",
    )
    new_parser.add_argument(
        "--template",
        "-t",
        metavar="TEMPLATE_NAME",
        type=str,
        default="",
        help=(
            "Specify the name of the template to use.\nIf not specified, search for a template named "
            "'default' in the user config directory, or use the default template.\n"
            "One may force the use of the default template by writing 'original'."
        ),
    )
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
        "--correction-only", "-c", action="store_true", help="Generate only correction for fast testing."
    )
    make_parser.add_argument(
        "--for-review",
        "-r",
        action="store_true",
        help="For each question, display its title and its different versions (if any). "
        "Useful for reviewing a mcq.",
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
        help="Delete all cached data. The scanning process will restart from the beginning.",
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
    scan_parser.add_argument(
        "--test-picture",
        type=Path,
        default=None,
        help="Used for debugging: scan only this picture, without storing scan's results.",
    )
    scan_parser.set_defaults(func=scan)
    # create the parser for the "clear" command
    clear_parser = add_parser("clear", help="Remove every MCQ data but the ptyx file.")
    clear_parser.add_argument("path", nargs="?", metavar="PATH", type=Path, default=".")
    clear_parser.set_defaults(func=clear)

    # create the parser for the "update-config" command
    update_config_parser = add_parser("update-config", help="Update mcq configuration file.")
    update_config_parser.add_argument("path", nargs="?", metavar="PATH", type=Path, default=".")
    update_config_parser.set_defaults(func=update_config)

    # create the parser for the "update-include" command
    update_include_parser = add_parser("update-include", help="Update included files.")
    update_include_parser.add_argument("path", nargs="?", metavar="PATH", type=Path, default=".")
    update_include_parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force update, even if it doesn't seem safe (pTyX code and include directives are intricate).",
    )
    update_include_parser.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="Remove imports corresponding to missing files, and any import comments.",
    )
    update_include_parser.set_defaults(func=update_include)

    # create the parser for the "create_template" command
    create_template_parser = add_parser("create-template", help="Create a customisable user template.")
    create_template_parser.add_argument(
        "name",
        nargs="?",
        metavar="NAME",
        type=str,
        default="default",
        help="The template name must be a valid directory name.",
    )
    create_template_parser.set_defaults(func=create_template)

    # create the parser for the "strategies" command
    strategies_parser = add_parser("strategies", help="List available evaluation strategies.")
    strategies_parser.set_defaults(func=strategies)

    # create the parser for the "add-autocompletion" command
    install_shell_completion_parser = add_parser(
        "install-shell-completion",
        help="Enable completion for the `mcq` command in the shell (only bash is supported for now).",
    )
    install_shell_completion_parser.add_argument(
        "--shell", type=str, default="bash", choices=("bash", "zsh", "fish")
    )
    install_shell_completion_parser.set_defaults(func=install_shell_completion)

    argcomplete.autocomplete(parser)

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


def make(
    path: Path,
    num: int = 1,
    start: int = 1,
    quiet: bool = False,
    correction_only: bool = False,
    for_review: bool = False,
) -> None:
    """Wrapper for _make(), so that `argparse` module don't intercept exceptions."""
    from .make.make import make_command

    try:
        make_command(path, num, start, quiet, correction_only, for_review)
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
        sys.exit(1)


def scan(
    path: Path,
    reset: bool = False,
    ask_for_name: bool = False,
    verify: Literal["auto", "always", "never"] = "auto",
    test_picture: Path = None,
) -> None:
    """Implement `mcq scan` command."""
    from .scan.scan import MCQPictureParser

    try:
        if verify == "always":
            manual_verification: Optional[bool] = True
        elif verify == "never":
            manual_verification = False
        else:
            manual_verification = None
        if test_picture is None:
            MCQPictureParser(path).scan_all(
                reset=reset,
                ask_for_name=ask_for_name,
                manual_verification=manual_verification,
            )
            print_success("Students' marks successfully generated. :)")
        else:
            MCQPictureParser(path).scan_picture(test_picture)
            print_success(f"Picture {test_picture!r} scanned.")
    except KeyboardInterrupt:
        print()
        print_warning("Script interrupted.")
        print_info("Relaunch it to resume scan process.")
        sys.exit(0)


def new(path: Path, include: Path = None, template="") -> None:
    """Implement `mcq new` command."""
    # Select the template to use.
    # Default template:
    template_path = Path(__file__).resolve().parent / "templates/original"
    # Directory of the eventual user templates:
    user_templates_path = PlatformDirs().user_config_path / "ptyx-mcq/templates"
    if template == "":
        # Search for a default user-defined template.
        user_default_template_path = user_templates_path / "default"
        if user_default_template_path.is_dir():
            template_path = user_default_template_path
    elif template != "original":
        template_path = user_templates_path / template
    if not template_path.is_dir():
        print_error(f"I can't use template {template!r}: '{template_path}' directory not found.")
        sys.exit(1)

    # Create the new MCQ.
    if path.exists():
        print_error(f"Path {path} already exists.")
        sys.exit(1)
    else:
        print(f"Using template from '{template_path}'.")
        shutil.copytree(template_path, path)
        if include is not None:
            # No need to have a questions directory template,
            # since questions' files will be explicitly listed.
            shutil.rmtree(path / "questions", ignore_errors=True)
            # Edit the .ptyx file, to replace default code with the list of the questions' files.
            ptyx_path = get_file_or_sysexit(path, extension=".ptyx")
            new_lines = [f"-- DIR: {include.resolve()}"]
            for include_path in include.glob("**/*.ex"):
                new_lines.append(f"-- {include_path.relative_to(include)}")
            lines = []
            with open(ptyx_path, encoding="utf8") as f:
                include_section = False
                for line in f:
                    line = line.rstrip("\n")
                    if line.startswith("<<<<"):
                        include_section = True
                        lines.append(line)
                        lines.extend(new_lines)
                    elif line.startswith(">>>>"):
                        include_section = False
                        lines.append(line)
                    elif not include_section:
                        lines.append(line)

            with open(ptyx_path, "w", encoding="utf8") as f:
                f.write("\n".join(lines) + "\n")
        print_success(f"A new MCQ was created at {path}.")


def clear(path: Path) -> None:
    """Implement `mcq clear` command."""
    ptyxfile_path = get_file_or_sysexit(path, extension=".ptyx")
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


def update_config(path: Path) -> None:
    """Update the .ptyx.mcq.config.json configuration file, following any .ptyx file change."""
    from ptyx.latex_generator import compiler
    from .make.make import parse_ptyx_file

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
    # The number of questions and their ordering should not have changed,
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


def update_include(path: Path, force=False, clean=False) -> None:
    """Update the list of included files."""
    from .tools.include_parser import update_file

    ptyxfile_path = get_file_or_sysexit(path, extension=".ptyx")
    update_file(ptyxfile_path, force=force, clean=clean)
    print_success("The list of included files was successfully updated.")


def strategies() -> None:
    """Display all evaluation modes with a description."""
    from .scan.evaluation_strategies import EvaluationStrategies

    strategies_list = EvaluationStrategies.get_all_strategies()
    print(f"\n{ANSI_REVERSE_PURPLE}[ Available strategies ]{ANSI_RESET}")
    print(", ".join(strategies_list))
    print()
    print(f"\n{ANSI_REVERSE_PURPLE}[ Details ]{ANSI_RESET}")
    for name in strategies_list:
        print(f"\n {ANSI_BLUE}╭───╴{ANSI_RESET}{ANSI_REVERSE_BLUE} {name} {ANSI_RESET} ")
        print(f" {ANSI_BLUE}│{ANSI_RESET} ")
        for line in getattr(EvaluationStrategies, name).__doc__.strip().split("\n"):
            print(f" {ANSI_BLUE}│{ANSI_RESET} " + line.strip())
        print(f" {ANSI_BLUE}│{ANSI_RESET} ")
        print(f" {ANSI_BLUE}╰───╴{ANSI_RESET}")


def create_template(name: str = "default") -> None:
    """Create default user template."""
    if name == "original":
        print_error(f"Name {name!r} is reserved, please choose another template name.")
        sys.exit(1)
    user_template = PlatformDirs().user_config_path / f"ptyx-mcq/templates/{name}"
    if user_template.is_dir():
        print_error(f"Folder {user_template} already exist, choose a different template name.")
        sys.exit(1)
    default_template = Path(__file__).resolve().parent / "templates/original"
    shutil.copytree(default_template, user_template)
    print_success(f"Template created at {user_template}. Edit the inner files to customize it.")


def install_shell_completion(shell: str = "bash") -> None:
    """Enable completion for the `mcq` command in the shell (bash by default)."""
    if shell != "bash":
        print_error(f"Sorry, {shell} completion not yet supported. :-(")
        sys.exit(1)
    if not os.access(__file__, os.X_OK):
        print_error(
            f"Unable to install completion since {__file__} is not executable. Fix it with:\n"
            f"chmod u+x {__file__}"
        )
        sys.exit(1)
    completion_file = PlatformDirs().user_config_path / f"ptyx-mcq/config/{shell}-completion"
    completion_file.parent.mkdir(parents=True, exist_ok=True)
    with open(completion_file, "w") as f:
        f.write(argcomplete.shellcode(["mcq"], shell=shell, argcomplete_script=__file__))
    bash_rc = Path("~/.bashrc").expanduser()
    newlines = f"\n# Enable mcq command completion\nsource {completion_file}\n"
    if not (bash_rc.is_file() and newlines in bash_rc.read_text()):
        with open(bash_rc, "a") as f:
            f.write(newlines)
        print_success(f"Completion enabled in {shell}. Enjoy!")
    else:
        print_info(f"Completion in {shell} was already activated. Nothing done.")


if __name__ == "__main__":
    main()
