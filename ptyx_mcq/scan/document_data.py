from dataclasses import dataclass
from enum import Enum, auto
from typing import TypedDict, NewType

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
    CHECKED = auto()
    UNCHECKED = auto()
    PROBABLY_CHECKED = auto()
    PROBABLY_UNCHECKED = auto()

    def __repr__(self):
        return self.name


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
    student_ID: StudentId
    # answers checked by the student for each question:
    answered: OriginalQuestionAnswersDict
    # Position of each checkbox in the page:
    positions: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], tuple[int, int]]
    cell_size: int
    # Translation table ({question number before shuffling: after shuffling})
    questions_nums_conversion: dict[OriginalQuestionNumber, ApparentQuestionNumber]
    needs_review: bool
    detection_status: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], DetectionStatus]
    revision_status: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], RevisionStatus]
    pic_path: str


class DocumentData(TypedDict):
    pages: dict[Page, PicData]
    name: StudentName
    student_ID: StudentId
    answered: OriginalQuestionAnswersDict  # {question: set of answers}
    score: float
    score_per_question: dict[OriginalQuestionNumber, float]  # {question: score}
