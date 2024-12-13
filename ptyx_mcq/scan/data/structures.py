from collections import ChainMap
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

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
)


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


@dataclass(kw_only=True)
class PicData:
    # # Position of each checkbox in the page:
    # positions: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], Pixel]
    # id_table_position: Pixel
    pic_path: Path
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


# @dataclass(kw_only=True)
# class PicData:
#     # ID of the document:
#     doc_id: DocumentId
#     # page number:
#     page: Page
#     name: StudentName
#     student_id: StudentId
#     # answers checked by the student for each question:
#     answered: OriginalQuestionAnswersDict
#     # Position of each checkbox in the page:
#     positions: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], tuple[int, int]]
#     cell_size: int
#     # Translation table ({question number before shuffling: after shuffling})
#     questions_nums_conversion: dict[OriginalQuestionNumber, ApparentQuestionNumber]
#     detection_status: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], DetectionStatus]
#     revision_status: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], RevisionStatus]
#     pic_path: str
#
#     @property
#     def needs_review(self):
#         return (
#             DetectionStatus.PROBABLY_CHECKED in self.detection_status.values()
#             or DetectionStatus.PROBABLY_UNCHECKED in self.detection_status.values()
#         )


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


@dataclass
class ReviewData:
    student_id: StudentId
    student_name: StudentName
    checkboxes: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], DetectionStatus]


@dataclass
class Student:
    id: StudentId
    name: StudentName
