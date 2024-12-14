from collections import ChainMap
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import NewType

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
    Page,
    CbxRef,
)


PdfHash = NewType("PdfHash", str)
PicNum = NewType("PicNum", int)


class DetectionStatus(Enum):
    """Status of a checkbox after scan."""

    CHECKED = auto()
    UNCHECKED = auto()
    PROBABLY_CHECKED = auto()
    PROBABLY_UNCHECKED = auto()

    def __repr__(self):
        return self.name

    @property
    def seems_checked(self) -> bool:
        return self in (DetectionStatus.CHECKED, DetectionStatus.PROBABLY_CHECKED)


class RevisionStatus(Enum):
    MARKED_AS_CHECKED = auto()
    MARKED_AS_UNCHECKED = auto()

    def __repr__(self):
        return self.name


@dataclass(kw_only=True, frozen=True)
class PicData:
    calibration_data: CalibrationData
    identification_data: IdentificationData

    @property
    def doc_id(self) -> DocumentId:
        """The id of the original document."""
        return self.identification_data.doc_id

    @property
    def page(self) -> Page:
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


PdfData = dict[PdfHash, dict[PicNum, PicData]]


@dataclass
class Student:
    id: StudentId
    name: StudentName


@dataclass
class ReviewData:
    student: Student | None
    checkboxes: dict[CbxRef, DetectionStatus]


@dataclass(frozen=True)
class Picture:
    path: Path
    data: PicData

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


# TODO: review or remove:
# =============
#     OLD
# =============


@dataclass(kw_only=True)
class DocumentData:
    pages: dict[Page, PicData]
    score: float
    score_per_question: dict[OriginalQuestionNumber, float]  # {question: score}

    @property
    def answered(self) -> ChainMap[OriginalQuestionNumber, set[OriginalAnswerNumber]]:
        return ChainMap(*(pic_data.answered for pic_data in self.pages.values()))

    @property
    def name(self) -> StudentName:
        return self.pages[Page(1)].name

    @name.setter
    def name(self, value: StudentName) -> None:
        self.pages[Page(1)].name = value

    @property
    def student_id(self) -> StudentId:
        return self.pages[Page(1)].student_id

    @student_id.setter
    def student_id(self, value: StudentId) -> None:
        self.pages[Page(1)].student_id = value
