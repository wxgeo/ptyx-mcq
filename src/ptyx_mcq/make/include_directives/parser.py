import re
from pathlib import Path

from ptyx_mcq.make.exercises_parsing import _get_ex_file_content
from ptyx_mcq.make.include_directives.directives import AddPath, ChangeDirectory, Directive
from ptyx_mcq.make.parser_tools import split_around_mcq

# language=regexp
RE_DIRECTIVE_PREFIX = "(?:@(?P<comment>\\w+):)?\\s*(?P<disable>!)?--\\s+(?P<special>DIR:|ROOT:)?"
# Use `:` as a separator between the path and the configuration options.
# language=regexp
RE_DIRECTIVE_CORE = "(?P<path>.+?)(:(?P<config>[^:]*))?"


def parse_directive(line: str) -> tuple[re.Match[str], re.Match[str]] | None:
    if (m1 := re.match(RE_DIRECTIVE_PREFIX, line)) is None:
        return None
    pos = m1.end()
    if (m2 := re.fullmatch(RE_DIRECTIVE_CORE, line[pos:])) is None:
        return None
    return m1, m2


def extract_directive(line: str) -> Directive | str:
    """
    Analyze the line, and return either the corresponding directive, or the line itself.

    If the line is an include directive, then a `Directive` object will be returned instead.
    Else, the line will be returned unchanged.

    This function can also be used to test if a line of text is a valid directive or not,
    by checking if a `Directive` instance is returned or not.
    """
    match parse_directive(line):
        case m1, m2:
            d = m1.groupdict(default="") | m2.groupdict(default="")

            if d["special"] == "ROOT:":
                raise DeprecationWarning(
                    f"Error in `{line}`:\n`-- ROOT:` is not supported anymore, use `-- DIR:` instead."
                )

            # noinspection PyArgumentList
            return (ChangeDirectory if d["special"] == "DIR:" else AddPath)(
                Path(d["path"].strip()).expanduser(),
                is_disabled=(d["disable"] == "!"),
                comment=d["comment"],
                configuration=d["config"].strip(),
            )
        case _:
            return line


def parse_code(code: str) -> list[Directive | str]:
    """Parse pTyx code, searching for include directives.

    Return a list of lines of code or directive objects."""
    return [extract_directive(line) for line in code.splitlines()]


def _resolve_include(
    is_exercise: bool, line_num: int, directive: AddPath, directory: Path, strict: bool
) -> str:
    return "\n".join(
        _get_ex_file_content(
            path,
            is_exercise=is_exercise,
            position=str(line_num),
            config=directive.configuration,
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
            line = extract_directive(line)
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
