import re

from ptyx.shell import ANSI_REVERSE_PURPLE, ANSI_RESET, ANSI_BLUE, ANSI_REVERSE_BLUE

from ptyx_mcq.scan.score_management.evaluation_strategies import EvaluationStrategies
from ptyx_mcq.make.extend_latex_generator import HeaderConfigKeys


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

    strategies = EvaluationStrategies.get_all_strategies()
    _document_options(
        title="Available strategies",
        options_info={name: getattr(EvaluationStrategies, name).__doc__.strip() for name in strategies},
    )


def doc_config() -> None:
    """Display all ptyx files configuration keys with a description."""

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
