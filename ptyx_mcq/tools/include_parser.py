import re
from enum import auto, Enum
from functools import partial
from pathlib import Path
from typing import Match

from ptyx_mcq.tools.io_tools import print_info, print_warning, print_error


class IncludeStatus(Enum):
    OK = auto()
    DISABLED = auto()
    NOT_FOUND = auto()
    AUTOMATICALLY_ADDED = auto()

    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


class IncludeParser:
    """Parser used to include files in a ptyx file.

    Ptyx-mcq accept the following syntax to include a file:

        -- path/to/file

    There must be at least one space after the two dashed.

    To disable an include, add a `!` just before the dashes:

        !-- path/to/file

    (You may also simply comment the line using the `#` character with a space after,
    which is the usual syntax to comment pTyX code, but this is less convenient).

    By default, when relative, paths to files refer to the directory where the ptyx file
    is located.

    The following syntax allows to change the directory where the files are searched.
    -- ROOT: /path/to/main/directory
    This will change the search directory for every subsequent path, at least
    until another `-- ROOT:` directive occurs (search directory may be changed
    several times).
    """

    # Store all include paths.
    # Format: {ROOT folder: {relative path: include enabled (True)|disabled (False)|invalid (None)}}
    includes: dict[str, dict[str, IncludeStatus]]
    _root: Path

    def __init__(self, default_path: Path):
        """Path `default_path` should be the parent directory of the ptyx file."""
        self.default_path = default_path
        self._reset()

    def _reset(self):
        self._root = self.default_path
        self._last_status = IncludeStatus.OK
        self.includes = {}

    def _parse_include(self, match: Match, strict: bool) -> str:
        include_enabled = match.group(0)[0] != "!"
        if match.group(0)[0] == "#":
            # Special `#--` comments are used to indicate include status.
            # (Currently, this only used to mark that an include was automatically added.)
            try:
                self._last_status = IncludeStatus[match.group(1).strip().rstrip(":")]
            except KeyError:
                print_warning(f"Invalid line: {match.group(0)}")
            return ""
        status = self._last_status
        self._last_status = IncludeStatus.OK
        pattern = match.group(1).strip()
        if pattern.startswith("ROOT:"):
            if include_enabled:
                path = Path(pattern[5:].strip()).expanduser()
                if not path.is_absolute():
                    path = (self.default_path / path).resolve()
                print_info(f"Directory for files inclusion set to '{path}'.")
                if not path.is_dir():
                    raise FileNotFoundError(
                        f"Directory '{path}' not found.\n"
                        f'HINT: Change "-- {pattern}" line in your ptyx file.'
                    )
                self._root = path
            return ""
        else:
            includes = self.includes.setdefault(str(self._root), {})
            if include_enabled:
                file_found = False
                contents = []
                for path in sorted(self._root.glob(pattern)):
                    if path.is_file():
                        file_found = True
                        contents.append(self._include_file(path).strip())
                if file_found:
                    # Include enabled
                    includes[str(pattern)] = status
                else:
                    # Invalid include
                    includes[str(pattern)] = IncludeStatus.NOT_FOUND
                    if strict:
                        print_error(message := f"No file corresponding to {pattern!r} in '{self._root}'!")
                        raise FileNotFoundError(message)
                    else:
                        print_warning(f"No file corresponding to {pattern!r} in '{self._root}'!")
                return "\n\n" + "\n\n".join(contents) + "\n\n"
            else:
                # Include disabled
                includes[str(pattern)] = IncludeStatus.DISABLED
                return ""

    def _include_file(self, path: Path) -> str:
        lines: list[str] = []
        with open(path) as file:
            file_content = file.read().strip()
            # Remove comments
            file_content = re.sub("( # .+)|(^# .+\n)", "", file_content, flags=re.MULTILINE)
            # Each exercise must start with a star. Since each included file is supposed to be an exercise,
            # add the initial star if missing.
            if file_content[:2].strip() != "*":
                file_content = "*\n" + file_content
            for line in file_content.split("\n"):
                lines.append(line)
                if (
                    line.startswith("* ")
                    or line.startswith("> ")
                    or line.startswith("OR ")
                    or line.rstrip() in ("*", ">", "OR")
                ):
                    prettified_path = path.parent / f"\u001b[36m{path.name.replace('#', '##')}\u001b[0m"
                    lines.append(f'#PRINT{{\u001b[36mIMPORTING\u001b[0m "{prettified_path}"}}')
        return "\n".join(lines)

    def parse(self, code: str, strict: bool = False) -> str:
        """Parse all include directives and include the corresponding files into the code.

        By default, if a path or a pattern don't match any file, a warning is raised,
        but the parsing will go on.
        However, if `strict` is set to `True`, a `FileNotFoundError` is raised in that case.
        """
        self._reset()
        _parse = partial(self._parse_include, strict=strict)
        return re.sub(r"^[#!]?-- (.+)$", _parse, code, flags=re.MULTILINE)

    def update(self, ptyxfile_path: Path):
        """Track all the `.ex` files and update pTyX file to include all the `.ex` files found.

        The `.ex` files are searched:
            - in the same directory as the `.pTyX` file
            - in any directory manually added via a `-- ROOT: /my/path` directive.
        """
        self.parse(ptyxfile_path.read_text(encoding="utf8"))
        new_includes: dict[str, dict[str, IncludeStatus]] = {}
        # Several patterns may refer to the same file: keep track of the files already indexed,
        # using their absolute path.
        already_indexed: set[Path] = set()
        for directory, indexed_files in self.includes.items():
            directory_path = Path(directory)
            new_directory_index = new_includes[directory] = {}
            # `index_files` is a dict. Its format is: {
            #   "a relative path or pattern to one or several indexed file": the status of the indexed files
            #   }
            indexed_ex_files: dict[Path, IncludeStatus] = {
                path: status
                for pattern, status in indexed_files.items()
                for path in directory_path.glob(pattern)
                if path not in already_indexed
            }
            already_indexed.update(indexed_ex_files)

            for ex_file_path, status in indexed_ex_files.items():
                ex_file = str(ex_file_path.relative_to(directory_path))
                new_directory_index[ex_file] = status

        for directory, indexed_files in self.includes.items():
            directory_path = Path(directory)
            # Search for new `.ex` files to index:
            for ex_file_path in directory_path.glob("**/*.ex"):
                if ex_file_path not in already_indexed:
                    already_indexed.add(ex_file_path)
                    ex_file = str(ex_file_path.relative_to(directory_path))
                    new_includes[directory][ex_file] = IncludeStatus.AUTOMATICALLY_ADDED
        self.includes = new_includes
        self._rewrite_file(ptyxfile_path, new_includes)

    def _rewrite_file(self, ptyxfile_path: Path, includes: dict[str, dict[str, IncludeStatus]]):
        new_file_added = False
        lines = []
        with open(ptyxfile_path, encoding="utf8") as f:
            for line in f:
                if line.startswith(">>>"):  # `>>>` marks the end of the MCQ
                    # Insert all include directives just before the end of the MCQ.
                    for folder, paths in includes.items():
                        folder_path = Path(folder)
                        if folder_path.is_relative_to(self.default_path):
                            folder = str(folder_path.relative_to(self.default_path))
                        lines.append(f"-- ROOT: {folder}")
                        for path, status in sorted(paths.items()):
                            match status:
                                case IncludeStatus.OK:
                                    lines.append(f"-- {path}")
                                case IncludeStatus.DISABLED:
                                    lines.append(f"!-- {path}")
                                case IncludeStatus.NOT_FOUND:
                                    lines.append(f"#-- NOT_FOUND:\n!-- {path}")
                                    print_warning(f"Invalid file path removed: '{path}'.")
                                case IncludeStatus.AUTOMATICALLY_ADDED:
                                    lines.append(f"#-- AUTOMATICALLY_ADDED:\n-- {path}")
                                    print_info(f"New file added: '{path}'.")
                                    new_file_added = True
                if not re.match(r"[#!]?-- ", line):
                    lines.append(line.rstrip())
        if not new_file_added:
            print_info("No new file found.")
        with open(ptyxfile_path, "w", encoding="utf8") as f:
            f.write("\n".join(lines) + "\n")
