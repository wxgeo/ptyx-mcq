import typing
from typing import Literal, NewType, TypedDict, TypeVar

T = TypeVar("T")
K = TypeVar("K", bound=typing.Hashable)
V = TypeVar("V")
DocumentId = NewType("DocumentId", int)
StudentId = NewType("StudentId", str)
StudentName = NewType("StudentName", str)
OriginalQuestionNumber = NewType("OriginalQuestionNumber", int)
ApparentQuestionNumber = NewType("ApparentQuestionNumber", int)
QuestionNumber = OriginalQuestionNumber | ApparentQuestionNumber
OriginalAnswerNumber = NewType("OriginalAnswerNumber", int)
ApparentAnswerNumber = NewType("ApparentAnswerNumber", int)
AnswerNumber = OriginalAnswerNumber | ApparentAnswerNumber
CbxRef = tuple[OriginalQuestionNumber, OriginalAnswerNumber]


class OrderingConfiguration(TypedDict):
    questions: list[OriginalQuestionNumber]
    answers: dict[OriginalQuestionNumber, list[tuple[OriginalAnswerNumber, bool | None]]]


QuestionNumberOrDefault = Literal["default"] | OriginalQuestionNumber
StudentIdFormat = tuple[int, int, list[tuple[str, ...]]]
OriginalQuestionAnswersDict = dict[OriginalQuestionNumber, set[OriginalAnswerNumber]]
ApparentQuestionAnswersDict = dict[ApparentQuestionNumber, set[ApparentAnswerNumber]]
QuestionToAnswerDict = OriginalQuestionAnswersDict | ApparentQuestionAnswersDict
QuestionWeight = NewType("QuestionWeight", float)
PageNum = NewType("PageNum", int)
