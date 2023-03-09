from dataclasses import dataclass
from typing import TypedDict, Dict, Tuple, Optional, NewType

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
    positions: Dict[Tuple[OriginalQuestionNumber, OriginalAnswerNumber], Tuple[int, int]]
    cell_size: int
    # Translation table ({question number before shuffling: after shuffling})
    questions_nums: Dict[OriginalQuestionNumber, ApparentQuestionNumber]
    # Manual verification by the user ?
    verified: Optional[bool]
    pic_path: str


class DocumentData(TypedDict):
    pages: dict[Page, PicData]
    name: StudentName
    student_ID: StudentId
    answered: OriginalQuestionAnswersDict  # {question: set of answers}
    score: float
    score_per_question: dict[OriginalQuestionNumber, float]  # {question: score}
