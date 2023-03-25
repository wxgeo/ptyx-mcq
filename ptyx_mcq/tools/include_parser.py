import re
from pathlib import Path
from typing import Match

from ptyx_mcq.tools.io_tools import print_info, print_warning


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
    includes: dict[str, dict[str, bool | None]]
    _root: Path

    def __init__(self, default_path: Path):
        self.default_path = default_path
        self._reset()

    def _reset(self):
        self._root = self.default_path
        self.includes = {}

    def _parse_include(self, match: Match) -> str:
        include_enabled = match.group(0)[0] != "!"
        pattern = match.group(1).strip()
        if pattern.startswith("ROOT:"):
            if include_enabled:
                path = Path(pattern[5:].strip()).expanduser()
                if not path.is_absolute():
                    path = (self.default_path / path).resolve()
                print_info(f"Directory for files inclusion changed to '{path}'.")
                if not path.is_dir():
                    raise FileNotFoundError(
                        f"Directory '{self._root}' not found.\n"
                        f'HINT: Change "-- {pattern}" line in your ptyx file.'
                    )
                self._root = path
            return "\n"
        else:
            includes = self.includes.setdefault(str(self._root), {})
            if include_enabled:
                file_found = False
                contents = []
                for path in sorted(self._root.glob(pattern)):
                    if path.is_file():
                        file_found = True
                        contents.append(self._include_file(path))
                if file_found:
                    # Include enabled
                    includes[str(pattern)] = True
                else:
                    # Invalid include
                    includes[str(pattern)] = None
                    print_warning(f"No file corresponding to {pattern!r} in '{self._root}'!")
                return "\n\n" + "\n\n".join(contents) + "\n\n"
            else:
                # Include disabled
                includes[str(pattern)] = False
                return "\n"

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
                    prettified_path = path.parent / f"\u001b[36m{path.name}\u001b[0m"
                    lines.append(f'#PRINT{{\u001b[36mIMPORTING\u001b[0m "{prettified_path}"}}')
        return "\n".join(lines)

    def parse(self, text: str) -> str:
        """"""
        self._reset()
        return re.sub(r"^!?-- (.+)$", self._parse_include, text, flags=re.MULTILINE)
