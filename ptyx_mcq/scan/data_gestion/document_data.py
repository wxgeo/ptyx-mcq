from collections import ChainMap
from dataclasses import dataclass
from enum import Enum, auto
from typing import NewType

from ptyx_mcq.tools.config_parser import (
    DocumentId,
    StudentId,
    StudentName,
    OriginalQuestionAnswersDict,
    ApparentQuestionNumber,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
)

Page = NewType("Page", int)


class DetectionStatus(Enum):
    """Status of a checkbox after scan."""

    CHECKED = auto()
    UNCHECKED = auto()
    PROBABLY_CHECKED = auto()
    PROBABLY_UNCHECKED = auto()

    def __repr__(self):
        return self.name

    @classmethod
    def seems_checked(cls, status: "DetectionStatus") -> bool:
        return status in (cls.CHECKED, cls.PROBABLY_CHECKED)


class RevisionStatus(Enum):
    MARKED_AS_CHECKED = auto()
    MARKED_AS_UNCHECKED = auto()

    def __repr__(self):
        return self.name


@dataclass(kw_only=True)
class PicData:
    # ID of the document:
    doc_id: DocumentId
    # page number:
    page: Page
    name: StudentName
    student_id: StudentId
    # answers checked by the student for each question:
    answered: OriginalQuestionAnswersDict
    # Position of each checkbox in the page:
    positions: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], tuple[int, int]]
    cell_size: int
    # Translation table ({question number before shuffling: after shuffling})
    questions_nums_conversion: dict[OriginalQuestionNumber, ApparentQuestionNumber]
    detection_status: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], DetectionStatus]
    revision_status: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], RevisionStatus]
    pic_path: str

    @property
    def needs_review(self):
        return (
            DetectionStatus.PROBABLY_CHECKED in self.detection_status.values()
            or DetectionStatus.PROBABLY_UNCHECKED in self.detection_status.values()
        )


@dataclass(kw_only=True)
class DocumentData:
    pages: dict[Page, PicData]
    name: StudentName
    student_id: StudentId
    score: float
    score_per_question: dict[OriginalQuestionNumber, float]  # {question: score}

    @property
    def answered(self) -> ChainMap[OriginalQuestionNumber, set[OriginalAnswerNumber]]:
        return ChainMap(*(pic_data.answered for pic_data in self.pages.values()))
