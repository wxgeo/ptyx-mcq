from dataclasses import dataclass
from pathlib import Path
from typing import Self

from ptyx.pretty_print import print_error, print_warning


@dataclass(frozen=True)
class Directive:
    """Object corresponding to an include directive."""

    # Nota: `path` must be the first argument, since directives must be ordered by path.
    path: Path
    is_disabled: bool = False
    comment: str = ""
    configuration: str = ""

    def __str__(self):
        comment = f"@{self.comment}: " if self.comment else ""
        disabled = "!" if self.is_disabled else ""
        type_ = " DIR:" if isinstance(self, ChangeDirectory) else ""
        directive = f"{comment}{disabled}--{type_} {self.path}"
        if self.configuration or ":" in str(self.path):
            directive += f" : {self.configuration}"
        return directive

    def copy(
        self,
        is_disabled: bool | None = None,
        comment: str | None = None,
    ) -> Self:
        """Make a copy, but allow to update some attributes."""
        # noinspection PyTypeChecker
        return self.__class__(
            self.path,
            comment=(self.comment if comment is None else comment),
            is_disabled=(self.is_disabled if is_disabled is None else is_disabled),
            configuration=self.configuration,
        )

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
