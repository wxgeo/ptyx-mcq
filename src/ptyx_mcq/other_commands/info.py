"""
Command line's tools that display information.
"""

import re

from ptyx.pretty_print import term_color, TermColors

from ptyx_mcq.scan.score_management.evaluation_strategies import ScoringImplementations
from ptyx_mcq.make.extend_latex_generator import HeaderConfigKeys


def _print_options_info(title: str, options_info: dict[str, str]) -> None:
    """Helper function to display all the available options for a given category in the terminal.

    After listing all the options, each option will be described.
    """

    def blue(s: str, reverse: bool = False) -> str:
        return term_color(s, TermColors.BLUE, reverse=reverse)

    def reverse_purple(s: str) -> str:
        return term_color(s, TermColors.PURPLE, reverse=True)

    # Display options list.
    print(reverse_purple(f"\n[ {title} ]"))
    print(", ".join(options_info))
    print()
    # Describe each option.
    print(reverse_purple("\n[ Details ]"))
    for option_name, option_doc in options_info.items():
        print(blue("\n ╭───╴") + blue(f" {option_name}  ", reverse=True))
        print(blue(" │ "))
        for line in option_doc.split("\n"):
            print(blue(" │ ") + line.strip())
        print(blue(" │ "))
        print(blue(" ╰───╴"))


def info_strategies() -> None:
    """Display all evaluation modes with a description."""

    strategies = ScoringImplementations.get_all_strategies()
    _print_options_info(
        title="Available strategies",
        options_info={name: getattr(ScoringImplementations, name).__doc__.strip() for name in strategies},
    )


def info_config() -> None:
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

    _print_options_info(
        title="Ptyx files configuration options", options_info={key: "\n".join(info[key]) for key in info}
    )
