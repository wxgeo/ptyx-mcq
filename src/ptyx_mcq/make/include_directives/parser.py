import re
from pathlib import Path
from typing import Any

from ptyx.pretty_print import print_warning

from ptyx_mcq.make.exercises_parsing import _get_ex_file_content
from ptyx_mcq.make.extend_latex_generator import HeaderConfigKeys
from ptyx_mcq.make.include_directives.directives import AddPath, ChangeDirectory, Directive
from ptyx_mcq.make.parser_tools import split_around_mcq
from ptyx_mcq.tools.evaluation_strategies import ScoringStrategy
from ptyx_mcq.tools.parse_config.subtypes import QuestionWeight


def parse_directive(line: str) -> Directive | str:
    """
    Analyze the line, and return either the corresponding directive, or the line itself.

    If the line is an include directive, then a `Directive` object will be returned instead.
    Else, the line will be returned unchanged.

    This function can also be used to test if a line of text is a valid directive or not,
    by checking if a `Directive` instance is returned or not.
    """
    # language=regexp
    prefix = "(?:@(?P<comment>\\w+):)?\\s*(?P<disable>!)?--\\s+(?P<special>DIR:|ROOT:)?"
    if (m := re.match(prefix, line)) is None:
        return line
    pos = m.end()
    d = m.groupdict(default="")

    # language=regexp
    short_pattern = "(?P<path>.+)"
    # The regexp for the score's weight and the strategy should accept any character for now, since the validation
    # will occur after.
    # language=regexp
    mid_pattern = short_pattern + ":(?P<weight>.*)"
    # language=regexp
    long_pattern = mid_pattern + ":(?P<strategy>.*)"
    # The longest pattern must be tested at first, since it is the more specific.
    # (Note that if the path contains colons, which is very unlikely, it must follow the long pattern.)
    for pattern in (long_pattern, mid_pattern, short_pattern):
        if m := re.fullmatch(pattern, line[pos:]):
            break
    else:
        return line
    d |= m.groupdict(default="")
    if d["special"] == "ROOT:":
        raise DeprecationWarning(
            f"Error in `{line}`:\n`-- ROOT:` is not supported anymore, use `-- DIR:` instead."
        )

    try:
        if d.get("weight"):
            # Accept both `.` and `,` as decimal separator.
            weight = QuestionWeight(float(d["weight"].replace(",", ".")))
        else:
            weight = None
    except ValueError:
        print_warning(f"Invalid score weight: {d['weight']!r}.")
        return line
    try:
        if d.get("strategy"):
            strategy = getattr(ScoringStrategy, d["strategy"].strip().upper())
        else:
            strategy = None
    except AttributeError:
        print_warning(f"Unknown scoring strategy: {d['strategy']!r}.")
        return line
    # noinspection PyArgumentList
    return (ChangeDirectory if d["special"] == "DIR:" else AddPath)(
        Path(d["path"].strip()).expanduser(),
        is_disabled=(d["disable"] == "!"),
        comment=d["comment"],
        question_weight=weight,
        scoring_strategy=strategy,
    )


def parse_code(code: str) -> list[Directive | str]:
    """Parse pTyx code, searching for include directives.

    Return a list of lines of code or directive objects."""
    return [parse_directive(line) for line in code.splitlines()]


def _resolve_include(
    is_exercise: bool, line_num: int, directive: AddPath, directory: Path, strict: bool
) -> str:
    config: dict[HeaderConfigKeys, Any] = {}
    if directive.scoring_strategy is not None:
        config[HeaderConfigKeys.mode] = directive.scoring_strategy
    if directive.question_weight is not None:
        config[HeaderConfigKeys.weight] = directive.question_weight
    return "\n".join(
        _get_ex_file_content(
            path,
            is_exercise=is_exercise,
            position=str(line_num),
            config=config,
        )
        for path in directive.get_all_files(directory, error_if_none=strict)
    )


def resolve_includes(code: str, default_dir: Path, strict=True) -> str:
    """Search for include directives, and insert the corresponding files content into the pTyX code."""
    directory: Path = default_dir
    # pTyX code after includes resolution.
    ptyx_code: list[str] = []

    line: str | Directive
    line_num = 0
    for section, lines in enumerate(split_around_mcq(code=code)):
        for line in lines:
            # noinspection PyTypeChecker
            line = parse_directive(line)
            if isinstance(line, Directive):
                if not line.is_disabled:
                    if isinstance(line, ChangeDirectory):
                        directory = line.get_directory(default_dir)
                    else:
                        assert isinstance(line, AddPath)
                        # New files to include.
                        ptyx_code.append(
                            _resolve_include(
                                is_exercise=(section == 1),
                                line_num=line_num,
                                directive=line,
                                directory=directory,
                                strict=strict,
                            )
                        )
            else:
                assert isinstance(line, str)
                ptyx_code.append(line)
            line_num += 1
    return "\n".join(ptyx_code) + "\n"


def resolve_includes_from_file(ptyx_file: Path) -> str:
    """Search for include directives, and insert the corresponding files content into the pTyX code."""
    return resolve_includes(ptyx_file.read_text(), ptyx_file.parent)


# def add_directories(ptyx_file: Path, directories: Iterable[Path]) -> None:
#     """Append new `ChangeDirectory` directives to the given pTyX file."""
#     before, mcq, after = parse_and_split_around_mcq(ptyx_file=ptyx_file)
#     mcq.extend(ChangeDirectory(path) for path in directories)
#     lines = [str(line) for line in before + mcq + after]
#     ptyx_file.write_text("\n".join(lines))
