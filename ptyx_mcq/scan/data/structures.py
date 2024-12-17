from collections import ChainMap
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import NewType, Self, Mapping, Iterator, TYPE_CHECKING

from PIL import Image
from numpy import ndarray, array
from ptyx.shell import print_error

from ptyx_mcq.scan.picture_analyze.calibration import CalibrationData
from ptyx_mcq.scan.picture_analyze.identify_doc import IdentificationData
from ptyx_mcq.scan.picture_analyze.types_declaration import Pixel
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    StudentId,
    StudentName,
    OriginalQuestionAnswersDict,
    ApparentQuestionNumber,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    PageNum,
    CbxRef,
)

if TYPE_CHECKING:
    from ptyx_mcq.scan.data.main_manager import ScanData

PdfHash = NewType("PdfHash", str)
PicNum = NewType("PicNum", int)
PdfData = dict[PdfHash, dict[PicNum, tuple[CalibrationData, IdentificationData]]]


class InvalidFormat(RuntimeError):
    """Raised when a file has an invalid format and cannot be decoded."""


class CbxState(Enum):
    """Status of a checkbox after scan."""

    CHECKED = auto()
    UNCHECKED = auto()
    PROBABLY_CHECKED = auto()
    PROBABLY_UNCHECKED = auto()

    def __repr__(self):
        return self.name

    @property
    def seems_checked(self) -> bool:
        return self in (CbxState.CHECKED, CbxState.PROBABLY_CHECKED)


class RevisionStatus(Enum):
    MARKED_AS_CHECKED = auto()
    MARKED_AS_UNCHECKED = auto()

    def __repr__(self):
        return self.name


@dataclass
class Student:
    """Data class regrouping information concerning one student."""

    id: StudentId
    name: StudentName

    def _as_str(self) -> str:
        return f"{self.name}\n{self.id}\n"

    @classmethod
    def _from_str(cls: Self, file_content: str) -> Self:
        try:
            student_name, student_id = file_content.strip().split("\n")
            return cls(name=StudentName(student_name), id=StudentId(student_id))
        except (ValueError, AttributeError):
            raise InvalidFormat(f"Incorrect file content: {file_content!r}")

    @classmethod
    def load(cls: Self, path: Path) -> Self:
        """Read the content of a student information file.

        May raise:
            - an OSError variant if the file is missing or unreadable.
            - an InvalidFormat if the file format is incorrect.
        """
        return cls._from_str(path.read_text(encoding="utf8"))

    def save(self, path: Path) -> None:
        path.write_text(self._as_str(), encoding="utf8")


class Checkboxes(dict, Mapping[CbxRef, CbxState]):
    """Dict containing all the checkboxes states (CHECKED, UNCHECKED, ...)."""

    def _as_str(self) -> str:
        # `{state!r}` and not `{state}`, to get "CHECKED" and not "CbxState.CHECKED".
        return "\n".join(f"{q}, {a}: {state!r}" for (q, a), state in self.items()) + "\n"

    @classmethod
    def _from_str(cls: Self, content: str) -> Self:
        cbx_states: Self = Checkboxes()
        for line in content.split("\n"):
            if line := line.strip():
                try:
                    q_a, status = line.split(":")
                    q, a = q_a.split(",")
                    cbx_states[(OriginalQuestionNumber(int(q)), OriginalAnswerNumber(int(a)))] = getattr(
                        CbxState, status.strip()
                    )
                except (ValueError, AttributeError):
                    raise InvalidFormat(f"Incorrect line: {line!r}")
        return cbx_states

    @classmethod
    def load(cls: Self, path: Path) -> Self:
        """Read the content of a checkboxes states file.

        May raise:
            - an OSError variant if the file is missing or unreadable.
            - an InvalidFormat if the file format is incorrect.
        """
        return cls._from_str(path.read_text(encoding="utf8"))

    def save(self, path: Path) -> None:
        path.write_text(self._as_str(), encoding="utf8")


@dataclass(kw_only=True)
class Picture:
    parent: "Page"
    path: Path
    calibration_data: CalibrationData
    identification_data: IdentificationData
    checkboxes: dict[CbxRef, CbxState] | None = None
    student: Student | None = None

    def __eq__(self, other):
        if not isinstance(other, Picture):
            return False
        if (
            self.checkboxes is None
            or self.student is None
            or other.checkboxes is None
            or other.student is None
        ):
            raise ValueError("Unparsed pictures should not be compared. Analyze them before.")
        return self.as_hashable_tuple() == other.as_hashable_tuple()

    @property
    def doc_id(self) -> DocumentId:
        """The id of the original document."""
        return self.identification_data.doc_id

    @property
    def page_num(self) -> PageNum:
        """The page number in the original document."""
        return self.identification_data.page

    def xy2ij(self, x: float, y: float) -> Pixel:
        """Convert (x, y) position (mm) to pixel coordinates (i, j).

        (x, y) is the position from the bottom left of the page in mm,
        as given by LaTeX.
        (i, j) is the position in pixel coordinates, where i is the line and j the
        column, starting from the top left of the image.
        """
        # Top left square is printed at 1 cm from the left and the top of the sheet.
        # 29.7 cm - 1 cm = 28.7 cm (A4 sheet format = 21 cm x 29.7 cm)
        top, left = self.calibration_data.top_left_corner_position
        v_resolution = self.calibration_data.v_pixels_per_mm
        h_resolution = self.calibration_data.h_pixels_per_mm
        return Pixel((round((287 - y) * v_resolution + top), round((x - 10) * h_resolution + left)))

    @property
    def dir(self):
        return self.path.parent

    @property
    def encoded_path(self) -> str:
        return str(self.path.with_suffix("").relative_to(self.path.parent.parent))

    @property
    def pdf_hash(self) -> PdfHash:
        return PdfHash(self.path.parent.name)

    @property
    def num(self) -> PicNum:
        return PicNum(int(self.path.stem))

    def as_image(self) -> Image.Image:
        if not self.path.is_file():
            print_error(f"File not found: `{self.path}`")
            raise FileNotFoundError(f'"{self.path}"')
        try:
            return Image.open(str(self.path))
        except Exception:
            print_error(f"Error when opening {self.path}.")
            raise

    def as_matrix(self) -> ndarray:
        return array(self.as_image().convert("L")) / 255

    def as_hashable_tuple(self) -> tuple:
        return (
            self.student,
            self.identification_data.doc_id,
            self.identification_data.page,
            tuple(self.checkboxes.values()),
        )

    @property
    def answered(self) -> dict[OriginalQuestionNumber, set[OriginalAnswerNumber]]:
        """Answers checked by the student for each question."""
        if self.checkboxes is None:
            raise ValueError("Picture must be analyzed first.")
        d = {}
        for (q, a), state in self.checkboxes.items():
            if state.seems_checked:
                d.setdefault(q, set()).add(a)
        return d

    @property
    def questions(self) -> list[OriginalQuestionNumber]:
        """All the (original) question numbers found in the picture."""
        return sorted({q for (q, a) in self.checkboxes})


@dataclass
class Page:
    parent: "Document"
    page_num: PageNum
    pictures: list[Picture]

    @property
    def has_conflicts(self):
        # No conflict is the data are the same (checkboxes + names).
        return len(self._conflicting_versions) >= 2

    @property
    def _conflicting_versions(self) -> list[Picture]:
        return list({pic.as_hashable_tuple(): pic for pic in self.pictures}.values())

    @property
    def pic(self):
        assert self.pictures
        if self.has_conflicts:
            raise ValueError(
                f"Only one picture expected, but {len(self.pictures)} conflicting versions found."
            )
        return self.pictures[0]

    def remove_duplicates(self):
        """Remove pictures which contain the same information, keeping only conflicting versions."""
        self.pictures = self._conflicting_versions

    def __iter__(self) -> Iterator[Picture]:
        return iter(self.pictures)


@dataclass
class Document:
    parent: "ScanData"
    doc_id: DocumentId
    pages: dict[PageNum, Page]
    score: float | None = None
    score_per_question: dict[OriginalQuestionNumber, float] | None = None

    @property
    def pictures(self) -> list[Picture]:
        """Return all the pictures associated with this document."""
        return [pic for page in self.pages.values() for pic in page.pictures]

    @property
    def answered(self) -> ChainMap[OriginalQuestionNumber, set[OriginalAnswerNumber]]:
        """Answers checked by the student for each question."""
        return ChainMap(*(page.pic.answered for page in self.pages.values()))

    def __iter__(self) -> Iterator[Page]:
        return iter(self.pages.values())
