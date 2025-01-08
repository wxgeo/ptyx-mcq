#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
"""
ptyx MCQ Command Line Interface

@author: Nicolas Pourcelot
"""
# ________
# WARNING!
# ‾‾‾‾‾‾‾‾
# ___________________________________________________________________________________
# We use `argcomplete` library to implement shell autocompletion.
# Arguments completion must be as fast as possible.
# So we must not import any heavy module for now:
# all heavy import must only occur **AFTER** calling `argcomplete.autocomplete()`!
#
# Extract from `https://pypi.org/project/argcomplete/`:
#  | Argcomplete gets completions by running your program.
#  | It intercepts the execution flow at the moment argcomplete.autocomplete() is called.
#  | After sending completions, it exits using exit_method (os._exit by default).
#  | This means if your program has any side effects that happen before argcomplete is called,
#  | those side effects will happen every time the user presses <TAB>
#  | (although anything your program prints to stdout or stderr will be suppressed).
#  | For this reason it’s best to construct the argument parser
#  | and call argcomplete.autocomplete() as early as possible in your execution flow.

# Calling `mcq` with incorrect arguments must also fail instantaneously,
# without importing all the heavy ptyx-mcq machinery.
#
# This is the reason why all handlers are given as strings, and not as functions,
# so that they will be imported only later (if needed).
# ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾

import os
import sys
from argparse import ArgumentParser, Action, Namespace
from enum import StrEnum
from pathlib import Path
from typing import Optional, Iterable, TYPE_CHECKING, Callable
from importlib import import_module

import argcomplete
from argcomplete import DirectoriesCompleter, FilesCompleter

from ptyx_mcq import __version__
from ptyx_mcq.other_commands.template import get_user_templates_path
from ptyx_mcq.parameters import DEFAULT_TEMPLATE_NAME
from ptyx_mcq.tools.io_tools import FatalError, ProcessInterrupted

if TYPE_CHECKING:
    # Import `MCQPictureParser` ONLY when type checking!
    # Otherwise, this would severely impact CLI autocompletion performance.
    pass


class TemplatesCompleter(argcomplete.completers.BaseCompleter):
    def __call__(  # type: ignore[override]
        self, *, prefix: str, action: Action, parser: ArgumentParser, parsed_args: Namespace
    ) -> Iterable[str]:
        return [DEFAULT_TEMPLATE_NAME] + [
            template.name for template in get_user_templates_path().glob("*") if template.is_dir()
        ]


# TODO: add in tests/ a new test that verify that all handlers referenced in ArgumentParser are effectively implemented!


def get_handler(handler_location: str) -> Callable:
    # Import handler.
    module_name, function_name = handler_location.rsplit(".", maxsplit=1)
    # Launch handler.
    return getattr(import_module(module_name), function_name)


class Handlers(StrEnum):
    new = "ptyx_mcq.other_commands.new.new"
    make = "ptyx_mcq.make.make"
    scan = "ptyx_mcq.scan.scan"
    clear = "ptyx_mcq.other_commands.clear.clear"
    see = "ptyx_mcq.other_commands.see.see"
    fix_doc = "ptyx_mcq.other_commands.fix.fix_doc"
    fix_name = "ptyx_mcq.other_commands.fix.fix_name"
    update_config_file = "ptyx_mcq.other_commands.update.update_config_file"
    update_exercises = "ptyx_mcq.other_commands.update.update_exercises"
    create_templates = "ptyx_mcq.other_commands.template.create_template"
    list_templates = "ptyx_mcq.other_commands.template.list_templates"
    doc_config = "ptyx_mcq.other_commands.doc.doc_config"
    doc_strategies = "ptyx_mcq.other_commands.doc.doc_strategies"
    install_shell_completion = "ptyx_mcq.other_commands.install.install_shell_completion"


def launcher(
    parser_creator: Callable[[], ArgumentParser], args: Optional[list] = None, _restart_process_if_needed=True
) -> None:
    """Main entry point, called whenever the `mcq` command is executed.

    Advanced parameter `_restart_process_if_needed`: It should be left to `True` in normal usage
    (it restarts the python process if needed to disable hash randomness, making the MCQ generation more deterministic).
    However, you must set it to `False` when using debugging in PyCharm (and possibly other IDE), otherwise a crash
    occurs, since PyCharm don't expect the python process to be restarted.
    """
    parser = parser_creator()
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    argcomplete.autocomplete(parser, always_complete_options=False)
    parsed_args = parser.parse_args(args)

    subparser = parser
    try:
        # Launch the function corresponding to the given subcommand.
        kwargs = vars(parsed_args)
        subparser = kwargs.pop("subparser", parser)
        # print(kwargs)
        handler: str = kwargs.pop("handler")
    except KeyError:
        # No subcommand passed.
        subparser.print_help()
        return

    if kwargs.pop("enforce_determinism", False) and _restart_process_if_needed:
        # Make compilation more reproducible, by disabling PYTHONHASHSEED.
        if not os.getenv("PYTHONHASHSEED"):
            os.environ["PYTHONHASHSEED"] = "0"
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            print("PYTHONHASHSEED:", os.getenv("PYTHONHASHSEED"))
        assert os.getenv("PYTHONHASHSEED")

    try:
        # Launch corresponding handler.
        get_handler(handler)(**kwargs)
    except ProcessInterrupted:
        sys.exit(0)
    except FatalError:
        sys.exit(1)


# noinspection PyTypeHints
def create_mcq_arg_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Generate and manage pdf MCQs.")
    subparsers = parser.add_subparsers()
    add_parser = subparsers.add_parser

    # Add all parsers and corresponding handlers.

    # ------------------------------------------
    #     $ mcq new
    # ==========================================
    # create the parser for the "new" command
    new_parser = add_parser("new", help="Create an empty ptyx file.")
    new_parser.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        type=Path,
        default="new-mcq",
        help="The name or the path of the new file to create.",
    ).completer = DirectoriesCompleter()  # type: ignore[attr-defined]
    new_parser.add_argument(
        "--include",
        "-i",
        metavar="INCLUDE_PATH",
        type=Path,
        help="Include all .ex files from this path in the generated .ptyx file.",
    ).completer = DirectoriesCompleter()  # type: ignore[attr-defined]
    new_parser.add_argument(
        "--template",
        "-t",
        metavar="TEMPLATE_NAME",
        type=str,
        default="",
        help=(
            "Specify the name of the template to use.\nIf not specified, search for a template named "
            "'default' in the user config directory, or use the default template.\n"
            f"One may force the use of the default template by writing '{DEFAULT_TEMPLATE_NAME}'."
        ),
    ).completer = TemplatesCompleter()  # type: ignore[attr-defined]
    new_parser.set_defaults(handler=Handlers.new)

    # ------------------------------------------
    #     $ mcq make
    # ==========================================
    # create the parser for the "make" command
    make_parser = add_parser("make", help="Generate pdf file.")
    make_parser.add_argument(  # type: ignore[attr-defined]
        "path", nargs="?", metavar="PATH", type=Path, default="."
    ).completer = FilesCompleter("ptyx")
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
    make_parser.add_argument("--with-correction", "-c", action="store_true", help="Generate correction too.")
    make_parser.add_argument(
        "--for-review",
        "-r",
        action="store_true",
        help="For each question, display its title and its different versions (if any). "
        "Useful for reviewing a mcq.",
    )
    make_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force the build of a new document even if a previous one exist, without asking what to do.",
    )
    make_parser.set_defaults(enforce_determinism=True, handler=Handlers.make)

    # ------------------------------------------
    #     $ mcq scan
    # ==========================================
    # create the parser for the "scan" command
    scan_parser = add_parser("scan", help="Generate scores from scanned documents.")
    scan_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help=(
            "Path to a directory which must contain "
            "a `.mcq.config` file and a `scan/` subdirectory "
            "(alternatively, this path may point to any file in this folder)."
        ),
    ).completer = DirectoriesCompleter()  # type: ignore[attr-defined]
    scan_parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all cached data. The scanning process will restart from the beginning.",
    )
    scan_parser.add_argument(
        "--cores",
        metavar="N",
        type=int,
        default=0,
        help="Set the number of cores to use (when set to 0 (default),"
        " the number of cores will be set automatically)."
        " Setting cores to 1 will disable multiprocessing and make scanning more verbose.",
    )
    scan_parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Debugging mode: display the picture with coloured squares at each step to review scanning process.",
    )
    scan_parser.add_argument(  # type: ignore[attr-defined]
        "--test-picture",
        type=Path,
        default=None,
        help="Used for debugging: scan only this picture, without storing scan's results.",
    ).completer = FilesCompleter("jpg")
    scan_parser.set_defaults(enforce_determinism=True, handler=Handlers.scan)

    # ------------------------------------------
    #     $ mcq clear
    # ==========================================
    # create the parser for the "clear" command
    clear_parser = add_parser("clear", help="Remove every MCQ data but the ptyx file.")
    clear_parser.add_argument("path", nargs="?", metavar="PATH", type=Path, default=".")
    clear_parser.set_defaults(handler=Handlers.clear)

    # ------------------------------------------
    #     $ mcq see
    # ==========================================
    # create the parser for the "see" command
    see_parser = add_parser("see", help="Show the pdf corresponding to the given student.")
    see_parser.add_argument(
        "name",
        nargs="?",
        metavar="NAME",
        type=str,
        help='The name of the student, or part of it. Wildcard may be used, like "J*hn*" (use quotes then).',
    )
    see_parser.set_defaults(handler=Handlers.see)

    # ------------------------------------------
    #     $ mcq fix
    # ==========================================
    # create the parser for the "fix" command
    fix_parser = add_parser("fix", help="Resolve the conflicts for the specified documents.")
    fix_parser.set_defaults(subparser=fix_parser)
    add_fix_parser = fix_parser.add_subparsers().add_parser

    # $ mcq fix doc
    # ------------------------
    # create the parser for the "fix doc" command
    fix_doc_parser = add_fix_parser("doc", help="Resolve conflicts concerning the students answers.")
    fix_doc_parser.add_argument(
        "-d",
        "--doc",
        metavar="DOC",
        type=int,
        help="The identifier of the document.",
    )  # TODO: add a completer ?
    fix_doc_parser.add_argument(
        "-p",
        "--page",
        metavar="PAGE",
        type=int,
        help="The page of the document.",
    )  # TODO: add a completer ?
    fix_doc_parser.add_argument(
        "-n",
        "--name",
        metavar="NAME",
        type=str,
        help="The name of the student.",
    )  # TODO: add a completer ?
    fix_doc_parser.add_argument(
        "-i",
        "--id",
        metavar="ID",
        type=str,
        help="The identifier of the student.",
    )  # TODO: add a completer ?
    fix_doc_parser.set_defaults(handler=Handlers.fix_doc)

    # $ mcq fix name
    # ------------------------
    # create the parser for the "fix name" command
    fix_name_parser = add_fix_parser("name", help="Resolve conflicts concerning the students name.")
    fix_name_parser.add_argument(
        "--doc",
        metavar="DOC",
        type=int,
        help="The identifier of the document.",
    )  # TODO: add a completer ?
    fix_doc_parser.set_defaults(handler=Handlers.fix_name)

    # ------------------------------------------
    #     $ mcq update
    # ==========================================
    # create the parser for the "update" command
    update_parser = add_parser("update", help="Update/synchronize some files of the MCQ directory.")
    update_parser.set_defaults(subparser=update_parser)
    add_update_parser = update_parser.add_subparsers().add_parser

    # $ mcq update config-file
    # ------------------------
    # create the parser for the "update config-file" command
    update_config_file_parser = add_update_parser(
        "config-file", help="Synchronize the mcq configuration file with the .ptyx file."
    )
    update_config_file_parser.add_argument(  # type: ignore[attr-defined]
        "path",
        nargs="?",
        metavar="PATH",
        type=Path,
        default=".",
        help="The .ptyx file from which the configuration file must be updated.",
    ).completer = FilesCompleter("ptyx")
    update_config_file_parser.set_defaults(handler=Handlers.update_config_file)

    # $ mcq update exercises
    # ------------------------
    # create the parser for the "update exercises" command
    update_exercices_parser = add_update_parser(
        "exercises", help="Update the list of the imported exercises."
    )
    update_exercices_parser.add_argument(  # type: ignore[attr-defined]
        "path", nargs="?", metavar="PATH", type=Path, default=".", help="Path of the .ptyx file to update."
    ).completer = FilesCompleter("ptyx")
    update_exercices_parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force update, even if it doesn't seem safe (pTyX code and include directives are intricate).",
    )
    update_exercices_parser.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="Remove imports corresponding to missing files, and any import comments.",
    )
    update_exercices_parser.set_defaults(handler=Handlers.update_exercises)

    # ------------------------------------------
    #     $ mcq template
    # ==========================================
    # create the parser for the "template" command
    template_parser = add_parser("template", help="Manage templates.")
    template_parser.set_defaults(subparser=template_parser)
    add_template_parser = template_parser.add_subparsers().add_parser

    # $ mcq template create
    # ------------------------
    # create the parser for the "template create" command
    create_template_parser = add_template_parser("create", help="Create a customisable user template.")
    create_template_parser.add_argument(
        "name",
        nargs="?",
        metavar="NAME",
        type=str,
        default="default",
        help="The template name must be a valid new directory name.",
    )
    create_template_parser.set_defaults(handler=Handlers.create_templates)

    # $ mcq template list
    # -------------------
    # create the parser for the "template list" command
    create_template_parser = add_template_parser("list", help="List all available templates.")
    create_template_parser.set_defaults(handler=Handlers.list_templates)

    # ------------------------------------------
    #     $ mcq doc
    # ==========================================
    # create the parser for the "doc" command
    doc_parser = add_parser(
        "doc", help="Display information about available options and evaluation strategies."
    )
    doc_parser.set_defaults(subparser=doc_parser)
    add_doc_parser = doc_parser.add_subparsers().add_parser

    # $ mcq doc strategies
    # --------------------
    strategies_parser = add_doc_parser("strategies", help="Document available evaluation strategies.")
    strategies_parser.set_defaults(handler=Handlers.doc_strategies)

    # $ mcq doc config
    # ----------------
    config_parser = add_doc_parser("config", help="Document ptyx files configuration options.")
    config_parser.set_defaults(handler=Handlers.doc_config)

    # ------------------------------------------
    #     $ mcq install
    # ==========================================
    # create the parser for the "install" command
    # create the parser for the "doc" command
    install_parser = add_parser("install", help="Manage pTyX-MCQ installation.")
    install_parser.set_defaults(subparser=install_parser)
    add_install_parser = install_parser.add_subparsers().add_parser

    # $ mcq install shell-completion
    # ------------------------------
    install_shell_completion_parser = add_install_parser(
        "shell-completion",
        help="Enable completion for the `mcq` command in the shell (only bash is supported for now).",
    )
    install_shell_completion_parser.add_argument(
        "--shell", type=str, default="bash", choices=("bash", "zsh", "fish")
    )
    install_shell_completion_parser.set_defaults(handler=Handlers.install_shell_completion)

    # TODO: enable to update pTyX-MCQ version.

    return parser


def main(args: Optional[list] = None, _restart_process_if_needed=True) -> None:
    launcher(create_mcq_arg_parser, args, _restart_process_if_needed=_restart_process_if_needed)


if __name__ == "__main__":
    main()
