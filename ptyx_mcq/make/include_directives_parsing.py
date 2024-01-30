"""Parser used to include files in a ptyx file.

Ptyx-mcq accept the following syntax to include a file:

    -- path/to/file

There must be at least one space after the two dashed.

To disable an include, add a `!` just before the dashes:

    !-- path/to/file

    --

(You may also simply comment the line using the `#` character with a space after,
which is the usual syntax to comment pTyX code, but this is less convenient).

By default, when relative, paths to files refer to the directory where the ptyx file
is located.

The following syntax allows to change the directory where the files are searched.
-- DIR: /path/to/main/directory
This will change the search directory for every subsequent path, at least
until another `-- DIR:` directive occurs (search directory may be changed
several times).

The files list may be semi-automatically updated using `.update()` method,
which search for new files and missing files in the default directory,
and in any directory declared through the `-- DIR:` directive.

Directives may be prefixed with comments: @<comment>:<directive>,
where <comment> is a single word (\\w+).

New files will be added with the `@new:` prefix:

    @new: -- path/relative/to/declared/directory/file.ex

Files not found will appear with the `@missing:` prefix,
and the directive will be disabled with `!`:

    @missing: !-- declared/path/file.ex

"""

import re
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

from typing import Self, Final, Iterable

from ptyx_mcq.make.exercises_parsing import _get_ex_file_content
from ptyx_mcq.tools.io_tools import print_warning, print_error


class UnsafeUpdate(RuntimeError):
    """Error raised when detecting a mix of pTyX code and include directives in the MCQ."""


class NoMCQSectionFound(RuntimeError):
    """
    Error raised when the file to update does not contain any MCQ section.

    The MCQ section must be surrounded by `<<<` and `>>>` lines.
    """


@dataclass(frozen=True)
class Directive:
    """Object corresponding to an include directive."""

    # Nota: `path` must be the first argument, since directives must be ordered by path.
    path: Path
    is_disabled: bool = False
    comment: str = ""

    def __str__(self):
        comment = f"@{self.comment}: " if self.comment else ""
        disabled = "!" if self.is_disabled else ""
        type_ = " DIR:" if isinstance(self, ChangeDirectory) else ""
        return f"{comment}{disabled}--{type_} {self.path}"

    def copy(self, is_disabled=None, comment=None) -> Self:
        if comment is None:
            comment = self.comment
        if is_disabled is None:
            is_disabled = self.is_disabled
        # noinspection PyArgumentList
        return self.__class__(self.path, comment=comment, is_disabled=is_disabled)

    def __lt__(self, other: "Directive"):
        if not isinstance(other, Directive):
            raise NotImplementedError(f"I can't compare {other} and {self}.")
        return self.path < other.path


class AddPath(Directive):
    """A directive corresponding to a path to add (one or several files)."""

    def get_all_files(self, directory: Path, error_if_none=False) -> list[Path]:
        """Return the list of all the matching files."""
        path = self.path.expanduser()
        if path.is_absolute():
            if path.is_file():
                paths = [path]
            else:
                paths = []
                print_warning(msg := f"File '{path}' not found !")
                if error_if_none:
                    raise FileNotFoundError(msg)
        else:
            # Support for glob (*, **)
            paths = sorted(path for path in directory.glob(str(path)) if path.is_file())
            if not paths:
                if "*" in str(path):
                    msg = f"No file name matches '{path}' in folder `{directory}`!"
                else:
                    msg = f"File '{path}' not found in folder `{directory}`!"
                print_warning(msg)
                if error_if_none:
                    raise FileNotFoundError(msg)
        return paths


class ChangeDirectory(Directive):
    """A directive to change current directory.

    Following `AddPath` directives will use this directory by default."""

    def get_directory(self, root: Path) -> Path:
        """
        Resolve directory path, expanding user and returning an absolute path.

        Raise `FileNotFoundError` if directory is not found.
        """
        path = self.path.expanduser()
        if not path.is_absolute():
            path = root / path
        if not path.is_dir():
            print_error(msg := f"Directory '{path}' not found !")
            raise FileNotFoundError(msg)
        return path


# IncludeDictionary = dict[ChangeDirectory | None, list[AddPath]]


# class IncludeEntry(TypedDict):
#     path: Path
#     comment: str | None
#     disabled: bool


def _parse_directive(line: str) -> Directive | str:
    """
    Analyze the line, and return either the corresponding directive, or the line itself.

    If the line is an include directive, then a `Directive` object will be returned instead.
    Else, the line will be returned unchanged.
    """
    m = re.match(
        "^(?:@(?P<comment>\\w+):)?\\s*" "(?P<disable>!)?" "--\\s+(?P<special>DIR:|ROOT:)?" "(?P<path>.+)$",
        line,
    )
    if m is None:
        return line
    d = m.groupdict()
    if d["special"] == "ROOT:":
        raise DeprecationWarning(
            f"Error in `{line}`:\n`-- ROOT:` is not supported anymore, use `-- DIR:` instead."
        )

    # noinspection PyArgumentList
    return (ChangeDirectory if d["special"] == "DIR:" else AddPath)(
        Path(d["path"].strip()).expanduser(),
        is_disabled=(d["disable"] == "!"),
        comment=d["comment"] or "",
    )


def parse_code(code: str) -> list[Directive | str]:
    """Parse pTyx code, searching for include directives.

    Return a list of lines of code or directive objects."""
    return [_parse_directive(line) for line in code.splitlines()]


def resolve_includes(code: str, default_dir: Path, strict=True) -> str:
    """Search for include directives, and insert the corresponding files content into the pTyX code."""
    directory: Path = default_dir
    # pTyX code after includes resolution.
    ptyx_code: list[str] = []

    for section, lines in enumerate(_split_around_mcq(code=code)):
        for line in lines:
            if isinstance(line, Directive):
                if not line.is_disabled:
                    if isinstance(line, ChangeDirectory):
                        directory = line.get_directory(default_dir)
                    else:
                        assert isinstance(line, AddPath)
                        # New files to include.
                        ptyx_code.append(
                            "\n".join(
                                _get_ex_file_content(path, exercise=(section == 1))
                                for path in line.get_all_files(directory, error_if_none=strict)
                            )
                        )
            else:
                assert isinstance(line, str)
                ptyx_code.append(line)

    return "\n".join(ptyx_code) + "\n"


def resolve_includes_from_file(ptyx_file: Path) -> str:
    """Search for include directives, and insert the corresponding files content into the pTyX code."""
    return resolve_includes(ptyx_file.read_text(), ptyx_file.parent)


def add_directories(ptyx_file: Path, directories: Iterable[Path]) -> None:
    """Append new `ChangeDirectory` directives to the given pTyX file."""
    before, mcq, after = _split_around_mcq(ptyx_file=ptyx_file)
    mcq.extend(ChangeDirectory(path) for path in directories)
    lines = [str(line) for line in before + mcq + after]
    ptyx_file.write_text("\n".join(lines))


def update_file(ptyxfile_path: Path, force=False, clean=False) -> None:
    """
    Track all the `.ex` files and update pTyX file to include all the `.ex` files found.

    The `.ex` files are searched:
        - in the same directory as the `.pTyX` file
        - in any directory manually added via a `-- DIR: /my/path` directive.

    If `force` is True, update the file even if it seems unsafe to do so
    (include directives and pTyX code lines are intricate).

    If `clean` is True, remove missing imports and any comments on imports.
    """
    updater = IncludesUpdater(ptyxfile_path)
    updated_content = updater.update_file_content(clean=clean)
    if not updater.is_updating_safe:
        if force:
            print_warning(f"Forcing unsafe update of {ptyxfile_path}, as requested.")
        else:
            print_error(msg := f"Update of {ptyxfile_path} does not seem safe.")
            raise UnsafeUpdate(msg)
    ptyxfile_path.write_text(updated_content, encoding="utf8")


class IncludesUpdater:
    """
    Class used to update the list of the .ex files included in a pTyX file.
    """

    def __init__(self, ptyxfile_path: Path):
        self.ptyxfile_path: Final[Path] = ptyxfile_path
        self.default_dir: Final[Path] = self.ptyxfile_path.parent

    def _reset(self) -> None:
        self.all_paths: set[Path] = set()
        self.local_includes: list[AddPath] = []
        self.includes: dict[ChangeDirectory, list[AddPath]] = {}
        # Is the update operation safe for this file?
        self.is_updating_safe = True

    def update_file_content(self, clean=False) -> str:
        """
        Track all the `.ex` files and return updated pTyX file content, to include all the `.ex` files found.

        The `.ex` files are searched:
            - in the same directory as the `.pTyX` file
            - in any directory manually added via a `-- DIR: /my/path` directive.
        """
        self._reset()
        before_mcq, mcq_section, after_mcq = _split_around_mcq(ptyx_file=self.ptyxfile_path)

        self._extract_directives(mcq_section)
        for line in reversed(before_mcq):
            if isinstance(line, ChangeDirectory) and self.local_includes:
                # Directory was changed before starting the MCQ,
                # so, the first directives of the MCQ section must refer to this directory,
                # and not to local path.
                self.includes.setdefault(line, []).extend(self.local_includes)
                # noinspection PyAttributeOutsideInit
                self.local_includes = []

        # Generate the set of all the files to include, and also detect and disable invalid paths.
        self._disable_missing_paths()
        # Detect new files.
        self._add_newly_discovered_paths()

        return (
            "\n".join(
                str(val)
                for val in before_mcq
                + [line for line in mcq_section if isinstance(line, str)]
                + self._directives_list(clean)
                + after_mcq
            )
            + "\n"
        )

    def _directives_list(self, clean=False) -> list[str]:
        lines = []

        def _append_directive(directive: Directive) -> None:
            if clean:
                if not directive.comment == "missing":
                    lines.append(str(directive.copy(comment="")))
            else:
                lines.append(str(directive))

        # Incorporate all the directives at the end of the mcq.
        for add_path_directive in sorted(self.local_includes):
            _append_directive(add_path_directive)
        for directory_directive, add_path_directives in sorted(self.includes.items()):
            if directory_directive is not None:
                _append_directive(directory_directive)
                for add_path_directive in sorted(add_path_directives):
                    _append_directive(add_path_directive)
        return lines

    def _extract_directives(self, lines: list[str | Directive]) -> None:
        """
        Find all the include directives in the mcq section (i.e. between `<<<` and `>>>`),
        and generate the `self.include` dict from them: {directory: [paths]}.

        Return a tuple of 2 items:
            - the lines of pTyX code (without the directives) until the end of mcq (`>>>` tag),
            - the remaining lines of pTyX code (from the `>>>` tag).
        """
        # Default includes, corresponding to the ptyx file directory.
        current_dir_includes = self.local_includes
        directive_found = False

        for line_no, line in enumerate(lines):
            if isinstance(line, Directive):
                directive_found = True
                if isinstance(line, ChangeDirectory):
                    current_dir_includes = self.includes.setdefault(line, [])
                else:
                    assert isinstance(line, AddPath)
                    current_dir_includes.append(line)
            else:
                assert isinstance(line, str)
                if directive_found and line.strip() != "":
                    # If directives were already found in the MCQ before this line of pTyX code,
                    # it means that directives and pTyX code are intricate inside the MCQ.
                    # Since any update will put all the directives at the end of the MCQ,
                    # updating may break the MCQ, depending on actual pTyX code content.
                    self.is_updating_safe = False

    def _disable_missing_paths(self) -> None:
        """
        Disable missing paths, and fill the paths set with all the paths found.
        """
        invalid_directories: list[ChangeDirectory] = []
        for directory_directive, add_path_directives in chain(
            self.includes.items(), [(ChangeDirectory(self.default_dir), self.local_includes)]
        ):
            directory: Path | None = None
            if directory_directive is None:
                directory = self.default_dir
            elif not directory_directive.is_disabled:
                try:
                    directory = directory_directive.get_directory(self.default_dir)
                except FileNotFoundError:
                    # Disable change directory directive, since the directory does not exist.
                    invalid_directories.append(directory_directive)

            # If `directory` is still `None`, it means that the given directory path was incorrect,
            # and has been already disabled. So only treat the case where `directory` is not `None`.
            if directory is not None:
                for i, add_path_directive in enumerate(add_path_directives):
                    paths = add_path_directive.get_all_files(directory)
                    if not paths:
                        # Disable add-path directive, since it doesn't match any existing file.
                        add_path_directives[i] = add_path_directive.copy(is_disabled=True, comment="missing")
                    else:
                        self.all_paths.update(paths)

        # Disable all directives corresponding to invalid directories:
        for directory_directive in invalid_directories:
            add_path_directives = self.includes.pop(directory_directive)
            # Disable any following add-path directive.
            self.includes[directory_directive.copy(is_disabled=True, comment="missing")] = [
                directive.copy(is_disabled=True, comment="missing") for directive in add_path_directives
            ]

    def _add_newly_discovered_paths(self) -> None:
        """
        Search for unreferenced .ex files, and update paths directives to include them.
        """

        # The `None` key (corresponding to `default_dir`) must be the last one to be seen.
        # The reason is that else, all newly discovered path would be preferentially discovered
        # from `default_dir`, instead of potential sub-folders given through `-- DIR:` directives.
        # It would be better to use a custom search algorithm, starting from the more specific sub-folders,
        # but it would not be so easy to implement, so it's probably not worth the additional code complexity.
        for directory_directive, add_path_directives in chain(
            self.includes.items(), [(ChangeDirectory(self.default_dir), self.local_includes)]
        ):
            # 1. Get the directory path.
            if directory_directive is None:
                directory = self.default_dir
            elif not directory_directive.is_disabled:
                directory = directory_directive.get_directory(self.default_dir)
            else:
                continue
            # 2. Add the relative paths of all its newly discovered `.ex` files.
            for ex_file_path in directory.glob("**/*.ex"):
                if ex_file_path not in self.all_paths:
                    add_path_directives.append(AddPath(ex_file_path.relative_to(directory), comment="new"))
                    self.all_paths.add(ex_file_path)


def _split_around_mcq(
    *,
    ptyx_file: Path = None,
    code: str = None,
) -> tuple[list[str | Directive], list[str | Directive], list[str | Directive]]:
    """
    Split the lines in 3 sub-lists:
    - the lines before the MCQ, including <<<
    - the lines inside the MCQ (the part between <<< and >>>).
    - the lines after the MCQ, including >>>

    Lines inside the MCQ are parsed and converted to directives if they match directive format.

    Raise NoMCQSectionFound if <<< or >>> is not found.
    """
    if code is None:
        if ptyx_file is None:
            raise ValueError("Either `ptyx_file` or `code` argument must be given.")
        else:
            code = ptyx_file.read_text()
    lines = parse_code(code)
    for start, line in enumerate(lines):
        if isinstance(line, str) and line.startswith("<<<"):
            break
    else:
        raise NoMCQSectionFound(f"`<<<` not found in '{ptyx_file}'.")
    start += 1

    for end, line in enumerate(lines[start:]):
        if isinstance(line, str) and line.startswith(">>>"):
            break
    else:
        raise NoMCQSectionFound(f"`>>>` not found in '{ptyx_file}'.")
    end += start
    return lines[:start], lines[start:end], lines[end:]
