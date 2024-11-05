#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
"""
ptyx MCQ Command Line Interface

@author: Nicolas Pourcelot
"""
import os
import shutil
import subprocess
import sys
import re
import traceback
from argparse import ArgumentParser, Action, Namespace
from os import unlink
from pathlib import Path
from typing import Optional, Literal, Iterable, TYPE_CHECKING

import argcomplete
from argcomplete import DirectoriesCompleter, FilesCompleter
from platformdirs import PlatformDirs

from ptyx.shell import (
    print_warning,
    print_success,
    print_error,
    print_info,
    ANSI_RESET,
    ANSI_REVERSE_PURPLE,
    ANSI_REVERSE_BLUE,
    ANSI_BLUE,
)

from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION, DEFAULT_TEMPLATE_NAME, DEFAULT_TEMPLATE_FULLPATH
from ptyx_mcq.tools.config_parser import Configuration
from ptyx_mcq.tools.io_tools import get_file_or_sysexit, FatalError, ProcessInterrupted

if TYPE_CHECKING:
    # Import `MCQPictureParser` ONLY when type checking!
    # Otherwise, this would severely impact CLI autocompletion performance.
    from ptyx_mcq.scan.scan_doc import MCQPictureParser


class TemplatesCompleter(argcomplete.completers.BaseCompleter):
    def __call__(  # type: ignore[override]
        self, *, prefix: str, action: Action, parser: ArgumentParser, parsed_args: Namespace
    ) -> Iterable[str]:
        return [DEFAULT_TEMPLATE_NAME] + [
            template.name for template in _get_user_templates_path().glob("*") if template.is_dir()
        ]


# noinspection PyTypeHints
def main(args: Optional[list] = None, _set_pythonhashseed_to_zero=True) -> None:
    """Main entry point, called whenever the `mcq` command is executed.

    Advanced parameter `_set_pythonhashseed_to_zero`: It should be left to `True` in normal usage
    (it restarts the python process if needed to disable hash randomness, making the MCQ generation more deterministic).
    However, you must set it to `False` when using debugging in PyCharm (and possibly other IDE), otherwise a crash
    occurs, since PyCharm don't expect the python process to be restarted.
    """
    parser = ArgumentParser(description="Generate and manage pdf MCQs.")
    subparsers = parser.add_subparsers()
    add_parser = subparsers.add_parser

    # ------------------------------------------
    #     $ mcq new
    # ------------------------------------------
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
    new_parser.set_defaults(func=new)

    # ------------------------------------------
    #     $ mcq make
    # ------------------------------------------
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
    make_parser.set_defaults(func=make)

    # ------------------------------------------
    #     $ mcq scan
    # ------------------------------------------
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
    # TODO: reimplement --verify (with tests) or remove it.
    scan_parser.add_argument(
        "--verify",
        "--manual-verification",
        choices=("always", "never", "auto"),
        default="auto",
        help="[UNMAINTAINED] If set to `always`, then for each page scanned, display a picture of "
        "the interpretation by the detection algorithm, "
        "for manual verification.\n"
        "If set to `never`, always assume algorithm is right.\n"
        "Default is `auto`, i.e. only ask for manual verification "
        "in case of ambiguity.",
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
    scan_parser.set_defaults(func=scan)

    # ------------------------------------------
    #     $ mcq clear
    # ------------------------------------------
    # create the parser for the "clear" command
    clear_parser = add_parser("clear", help="Remove every MCQ data but the ptyx file.")
    clear_parser.add_argument("path", nargs="?", metavar="PATH", type=Path, default=".")
    clear_parser.set_defaults(func=clear)

    # ------------------------------------------
    #     $ mcq fix
    # ------------------------------------------
    # create the parser for the "fix" command
    fix_parser = add_parser("fix", help="Update mcq configuration file.")
    fix_parser.add_argument(  # type: ignore[attr-defined]
        "path",
        nargs="?",
        metavar="PATH",
        type=Path,
        default=".",
        help="The .ptyx file from which the configuration file must be updated.",
    ).completer = FilesCompleter("ptyx")
    fix_parser.set_defaults(func=fix)

    # ------------------------------------------
    #     $ mcq see
    # ------------------------------------------
    # create the parser for the "see" command
    see_parser = add_parser("see", help="Show the pdf corresponding to the given student.")
    see_parser.add_argument(
        "name",
        nargs="?",
        metavar="NAME",
        type=str,
        help='The name of the student, or part of it. Wildcard may be used, like "J*hn*" (use quotes then).',
    )
    see_parser.set_defaults(func=see)

    # ------------------------------------------
    #     $ mcq update
    # ------------------------------------------
    # create the parser for the "update" command
    update_parser = add_parser("update", help="Update the list of included files.")
    update_parser.add_argument(  # type: ignore[attr-defined]
        "path", nargs="?", metavar="PATH", type=Path, default=".", help="Path of the .ptyx file to update."
    ).completer = FilesCompleter("ptyx")
    update_parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force update, even if it doesn't seem safe (pTyX code and include directives are intricate).",
    )
    update_parser.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="Remove imports corresponding to missing files, and any import comments.",
    )
    update_parser.set_defaults(func=update)

    # ------------------------------------------
    #     $ mcq create-template
    # ------------------------------------------
    # create the parser for the "create-template" command
    create_template_parser = add_parser("create-template", help="Create a customisable user template.")
    create_template_parser.add_argument(
        "name",
        nargs="?",
        metavar="NAME",
        type=str,
        default="default",
        help="The template name must be a valid new directory name.",
    )
    create_template_parser.set_defaults(func=create_template)

    # ------------------------------------------
    #     $ mcq doc
    # ------------------------------------------
    # create the parser for the "doc" command
    doc_parser = add_parser(
        "doc", help="Display information about available options and evaluation strategies."
    )
    add_doc_parser = doc_parser.add_subparsers().add_parser
    strategies_parser = add_doc_parser("strategies", help="Document available evaluation strategies.")
    strategies_parser.set_defaults(func=doc_strategies)
    config_parser = add_doc_parser("config", help="Document ptyx files configuration options.")
    config_parser.set_defaults(func=doc_config)

    # ------------------------------------------
    #     $ mcq add-autocompletion
    # ------------------------------------------
    # create the parser for the "add-autocompletion" command
    install_shell_completion_parser = add_parser(
        "install-shell-completion",
        help="Enable completion for the `mcq` command in the shell (only bash is supported for now).",
    )
    install_shell_completion_parser.add_argument(
        "--shell", type=str, default="bash", choices=("bash", "zsh", "fish")
    )
    install_shell_completion_parser.set_defaults(func=install_shell_completion)

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

    if func not in (doc_strategies, doc_config, see):
        # Make compilation more reproducible, by disabling PYTHONHASHSEED.
        if not os.getenv("PYTHONHASHSEED") and _set_pythonhashseed_to_zero:
            os.environ["PYTHONHASHSEED"] = "0"
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            print("PYTHONHASHSEED:", os.getenv("PYTHONHASHSEED"))
        assert os.getenv("PYTHONHASHSEED") or not _set_pythonhashseed_to_zero

    try:
        func(**kwargs)
    except ProcessInterrupted:
        sys.exit(0)
    except FatalError:
        sys.exit(1)


def make(
    path: Path,
    num: int = 1,
    start: int = 1,
    quiet: bool = False,
    with_correction: bool = False,
    for_review: bool = False,
    force: bool = False,
) -> None:
    """Wrapper for _make(), so that `argparse` module don't intercept exceptions."""
    from .make.make import make_command

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


def scan(
    path: Path,
    reset: bool = False,
    cores: int = 0,
    verify: Literal["auto", "always", "never"] = "auto",
    test_picture: Path = None,
    debug: bool = False,
) -> "MCQPictureParser":
    """Implement `mcq scan` command.

    Returned `MCQPictureParser` instance may be used by tests to check results.
    """
    from ptyx_mcq.scan.scan_doc import MCQPictureParser

    try:
        if verify == "always":
            manual_verification: Optional[bool] = True
        elif verify == "never":
            manual_verification = False
        else:
            manual_verification = None
        mcq_parser = MCQPictureParser(path)
        if test_picture is None:
            mcq_parser.run(
                manual_verification=manual_verification, number_of_processes=cores, debug=debug, reset=reset
            )
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


def new(path: Path, include: Path = None, template="") -> None:
    """Implement `mcq new` command.

    Path `path` is the path of the new file to create.
    Path `include` must be a directory whose all .ex files will be recursively included.
    """
    # Select the template to use.
    template_path = get_template_path(template)
    # Create the new MCQ.
    if path.exists():
        print_error(f"Path {path} already exists.")
        raise FatalError
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


def get_template_path(template_name: str = "") -> Path:
    """Return the path of the directory containing the corresponding template.

    The template is first searched in user config directory.
    If not found, a default template is applied.
    """
    # Default template:
    template_path = DEFAULT_TEMPLATE_FULLPATH
    # Directory of the eventual user templates:
    user_templates_path = _get_user_templates_path()
    if template_name == "":
        # Search for a default user-defined template.
        user_default_template_path = user_templates_path / "default"
        if user_default_template_path.is_dir():
            template_path = user_default_template_path
    elif template_name != DEFAULT_TEMPLATE_NAME:
        template_path = user_templates_path / template_name
    if not template_path.is_dir():
        print_error(f"I can't use template {template_name!r}: '{template_path}' directory not found.")
        raise FatalError
    return template_path


def _get_user_templates_path():
    """Return the path of the directory where the user's templates are stored."""
    return PlatformDirs().user_config_path / "ptyx-mcq/templates"


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
        ptyxfile_path.with_suffix(CONFIG_FILE_EXTENSION),
        ptyxfile_path.with_name(f".{filename}.plain-ptyx"),
        ptyxfile_path.with_name(f"{ptyxfile_path.stem}-corr.pdf"),
    ):
        try:
            unlink(filepath)
        except FileNotFoundError as e:
            print(f"Warning: {e}")
            print(f"Info: '{filepath}' not found...")
    print_success("Directory cleared.")


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


def fix(path: Path) -> None:
    """Update the .ptyx.mcq.config.json configuration file, following any .ptyx file change.

    Path `path` must be either a pTyx file, or a directory containing a single pTyX file.
    """
    from ptyx.latex_generator import Compiler

    config_file = get_file_or_sysexit(path, extension=CONFIG_FILE_EXTENSION)
    print(f"Reading {config_file}...")
    config = Configuration.load(config_file)
    ptyx_filename = get_file_or_sysexit(path, extension=".ptyx")
    print(f"Reading {ptyx_filename}...")
    compiler = Compiler(path=ptyx_filename)
    # Compile ptyx file to LaTeX, to update information, but without compiling
    # LaTeX, which is slow (don't generate pdf files again).
    for doc_id in config.ordering:
        compiler.get_latex(PTYX_NUM=doc_id)
    # Update configuration
    data: Configuration = compiler.latex_generator.mcq_data  # type: ignore
    # Test compatibility of `data` with `config`:
    # The number of questions and their ordering should not have changed,
    # the same holds for the answers (but their labelling as correct
    # or incorrect is allowed to change).
    if not same_questions_and_answers_numbers(data, config):
        cmd = f"mcq make {path}"
        sep = len(cmd) * "-"
        cmd = f"{sep}\n{cmd}\n{sep}\n"
        print_error("Questions or answers changed.\n" "You must run a full compilation:\n" + cmd)
        raise FatalError

    # Get back the positions of checkboxes from last full compilation.
    data.id_table_pos = config.id_table_pos
    data.boxes = config.boxes
    data.dump(config_file.parent / (config_file.name.split(".")[0] + CONFIG_FILE_EXTENSION))
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


def update(path: Path, force=False, clean=False) -> None:
    """Update the list of included files."""
    from ptyx_mcq.make.include_directives_parsing import update_file

    ptyxfile_path = get_file_or_sysexit(path, extension=".ptyx")
    update_file(ptyxfile_path, force=force, clean=clean)
    print_success("The list of included files was successfully updated.")


def _document_options(title: str, options_info: dict[str, str]) -> None:
    """Helper function to display all the available options for a given category in the terminal.

    After listing all the options, each option will be described.
    """
    # Display options list.
    print(f"\n{ANSI_REVERSE_PURPLE}[ {title} ]{ANSI_RESET}")
    print(", ".join(options_info))
    print()
    # Describe each option.
    print(f"\n{ANSI_REVERSE_PURPLE}[ Details ]{ANSI_RESET}")
    for option_name, option_doc in options_info.items():
        print(f"\n {ANSI_BLUE}╭───╴{ANSI_RESET}{ANSI_REVERSE_BLUE} {option_name} {ANSI_RESET} ")
        print(f" {ANSI_BLUE}│{ANSI_RESET} ")
        for line in option_doc.split("\n"):
            print(f" {ANSI_BLUE}│{ANSI_RESET} " + line.strip())
        print(f" {ANSI_BLUE}│{ANSI_RESET} ")
        print(f" {ANSI_BLUE}╰───╴{ANSI_RESET}")


def doc_strategies() -> None:
    """Display all evaluation modes with a description."""
    from ptyx_mcq.scan.score_management.evaluation_strategies import EvaluationStrategies

    strategies = EvaluationStrategies.get_all_strategies()
    _document_options(
        title="Available strategies",
        options_info={name: getattr(EvaluationStrategies, name).__doc__.strip() for name in strategies},
    )


def doc_config() -> None:
    """Display all ptyx files configuration keys with a description."""
    from ptyx_mcq.make.extend_latex_generator import HeaderConfigKeys

    keys = HeaderConfigKeys.__members__
    current_key: str | None = None
    info: dict[str, list[str]] = {}
    for line in HeaderConfigKeys.__doc__.split("\n"):  # type: ignore
        if match := re.match(" {4}- (\\w+):", line):
            current_key = match.group(1)
            if current_key not in keys:
                raise RuntimeError(f"Unknown option: {current_key!r}")
            info[current_key] = []
        elif current_key is not None:
            info[current_key].append(line.strip())

    _document_options(
        title="Ptyx files configuration options", options_info={key: "\n".join(info[key]) for key in info}
    )


def create_template(name: str = "default") -> None:
    """Create default user template."""
    if name == DEFAULT_TEMPLATE_NAME:
        print_error(f"Name {name!r} is reserved, please choose another template name.")
        raise FatalError
    user_template = PlatformDirs().user_config_path / f"ptyx-mcq/templates/{name}"
    if user_template.is_dir():
        print_error(f"Folder {user_template} already exist, choose a different template name.")
        raise FatalError
    default_template = DEFAULT_TEMPLATE_FULLPATH
    shutil.copytree(default_template, user_template)
    print_success(f"Template created at {user_template}. Edit the inner files to customize it.")


def install_shell_completion(shell: str = "bash") -> None:
    """Enable completion for the `mcq` command in the shell (bash by default)."""
    if shell != "bash":
        print_error(f"Sorry, {shell} completion not yet supported. :-(")
        raise FatalError
    if not os.access(__file__, os.X_OK):
        print_error(
            f"Unable to install completion since {__file__} is not executable. Fix it with:\n"
            f"chmod u+x {__file__}"
        )
        raise FatalError

    dev_cli = __file__.replace("cli.py", "dev_cli.py")
    done = []
    if _install_completion(f"mcq-{shell}-completion", "mcq", __file__, shell):
        done.append("`mcq`")
    if _install_completion(f"mcq-dev-{shell}-completion", "mcq-dev", dev_cli, shell):
        done.append("`mcq-dev`")

    if done:
        print_success(f"Completion enabled in {shell} for {' and '.join(done)}. Enjoy!")
    else:
        print_info(f"Completion in {shell} was already activated. Nothing done.")


def _install_completion(completion_file_name, command, python_script, shell) -> bool:
    completion_file = PlatformDirs().user_config_path / "ptyx-mcq/config" / completion_file_name
    completion_file.parent.mkdir(parents=True, exist_ok=True)
    with open(completion_file, "w") as f:
        f.write(argcomplete.shellcode([command], shell=shell, argcomplete_script=python_script))
    bash_rc = Path("~/.bashrc").expanduser()
    newlines = f"\n# Enable {command} command completion\nsource {completion_file}\n"
    if not (bash_rc.is_file() and newlines in bash_rc.read_text()):
        with open(bash_rc, "a") as f:
            f.write(newlines)
        return True
    else:
        return False


if __name__ == "__main__":
    main()
