import re
from pathlib import Path
from typing import Match

from ptyx.latex_generator import Compiler

from ptyx_mcq.tools.io_tools import print_info, print_warning


class IncludeParser:
    """Parser used to include files in a ptyx file.

    Ptyx-mcq accept the following syntax to include a file:
    -- path/to/file

    By default, when relative, paths to files refer to the directory where the ptyx file
    is located.

    The following syntax allows to change the directory where the files are searched.
    -- ROOT: /path/to/main/directory
    This will change the search directory for every subsequent path, at least
    until another `-- ROOT:` directive occurs (search directory may be changed
    several times).
    """

    def __init__(self, compiler: Compiler):
        self.compiler = compiler
        self.root: Path = compiler.dir_path
        self.includes: list[Path] = []

    def _parse_include(self, match: Match) -> str:
        pattern = match.group(1).strip()
        if pattern.startswith("ROOT:"):
            path = Path(pattern[5:].strip()).expanduser()
            if not path.is_absolute():
                path = (self.compiler.dir_path / path).resolve()
            print_info(f"Directory for files inclusion changed to '{path}'.")
            if not path.is_dir():
                raise FileNotFoundError(
                    f"Directory '{self.root}' not found.\n"
                    f'HINT: Change "-- {pattern}" in {self.compiler.file_path}.'
                )
            self.root = path
            return "\n"
        else:
            file_found = False
            contents = []
            for path in sorted(self.root.glob(pattern)):
                if path.is_file():
                    file_found = True
                    contents.append(self._include_file(path))
            if not file_found:
                print_warning(f"No file corresponding to {pattern!r} in '{self.root}'!")
            return "\n\n" + "\n\n".join(contents) + "\n\n"

    def _include_file(self, path: Path) -> str:
        self.includes.append(path)
        lines: list[str] = []
        with open(path) as file:
            file_content = self.compiler.syntax_tree_generator.remove_comments(file.read().strip())
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
        return re.sub(r"^-- (.+)$", self._parse_include, text, flags=re.MULTILINE)
