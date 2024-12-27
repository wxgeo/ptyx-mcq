from dataclasses import dataclass
from pathlib import Path
from typing import Self

from ptyx_mcq.scan.data.questions import InvalidFormat
from ptyx_mcq.tools.config_parser import StudentId, StudentName


@dataclass(frozen=True)
class Student:
    """Data class regrouping information concerning one student."""

    id: StudentId
    name: StudentName

    def _as_str(self) -> str:
        return f"{self.name}\n{self.id}\n"

    @classmethod
    def _from_str(cls: "Student", file_content: str) -> "Student":
        try:
            student_name, student_id = file_content.strip().split("\n")
            return cls(name=StudentName(student_name), id=StudentId(student_id))
        except (ValueError, AttributeError):
            raise InvalidFormat(f"Incorrect file content: {file_content!r}")

    @classmethod
    def load(cls: Self, path: Path) -> Self | None:
        """Read the content of a student information file, and return a Student instance.

        Return `None` if the file is missing or incorrect.
        """
        try:
            return cls._from_str(path.read_text(encoding="utf8"))
        except (OSError, InvalidFormat):
            return None

    def save(self, path: Path) -> None:
        path.write_text(self._as_str(), encoding="utf8")
