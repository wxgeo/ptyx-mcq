from itertools import chain
from pathlib import Path
from typing import Final

from ptyx.pretty_print import print_error, print_warning

from ptyx_mcq.make.include_directives.directives import AddPath, ChangeDirectory, Directive
from ptyx_mcq.make.include_directives.parser import extract_directive
from ptyx_mcq.make.parser_tools import split_around_mcq


class UnsafeUpdate(RuntimeError):
    """Error raised when detecting a mix of pTyX code and include directives in the MCQ."""


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
        sections: tuple[list[str | Directive], ...] = split_around_mcq(ptyx_file=self.ptyxfile_path)  # type: ignore
        for section in sections:
            for i, line in enumerate(section):
                section[i] = extract_directive(line)  # type: ignore

        before_mcq, mcq_section, after_mcq = sections
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
