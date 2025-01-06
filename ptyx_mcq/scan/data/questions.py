from dataclasses import dataclass
from enum import Enum, auto

from ptyx_mcq.scan.picture_analyze.types_declaration import Line, Col, Pixel
from ptyx_mcq.tools.config_parser import CbxRef, OriginalAnswerNumber, OriginalQuestionNumber

CbxPositions = dict[CbxRef, tuple[Line, Col]]


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

    @property
    def needs_review(self) -> bool:
        return self in (CbxState.PROBABLY_CHECKED, CbxState.PROBABLY_UNCHECKED)

    # @property
    # def manually_revied(self):


# class RevisionStatus(Enum):
#     MARKED_AS_CHECKED = auto()
#     MARKED_AS_UNCHECKED = auto()
#
#     def __repr__(self):
#         return self.name


# class AnswerStateDict(TypedDict):
#     correct: bool | None
#     initial_state: CbxState | None
#     amended_state: CbxState | None


@dataclass
class Answer:
    answer_num: OriginalAnswerNumber
    # Should the checkbox have been checked, i.e. is the answer correct?
    is_correct: bool | None
    # Position of the top-left pixel of the checkbox
    position: Pixel
    # State of the checkbox as detected by the program
    _initial_state: CbxState | None = None
    # State of the checkbox after user review, if any, else `None`.
    _amended_state: CbxState | None = None

    @property
    def initial_state(self) -> CbxState | None:
        """State of the checkbox as detected before any eventual manual review."""
        return self._initial_state

    @property
    def amended_state(self) -> CbxState | None:
        """Correction of the state of the checkbox during manual review, if any."""
        return self._amended_state

    @property
    def state(self) -> CbxState | None:
        """The state of the checkbox (checked or not)."""
        return self._initial_state if self._amended_state is None else self._amended_state

    @state.setter
    def state(self, value: CbxState) -> None:
        if self._initial_state is None:
            self._initial_state = value
        else:
            self._amended_state = value

    def as_str(self, is_fix=False) -> str:
        state = self._amended_state if is_fix else self._initial_state
        # `{state!r}` and not `{state}`, to get "CHECKED" and not "CbxState.CHECKED".
        return "" if state is None else f"{self.answer_num}: {state!r}"

    def as_hashable_tuple(self):
        return self.as_str(), self.as_str(is_fix=True)

    @property
    def neutralized(self) -> bool:
        return self.is_correct is None

    @property
    def checked(self) -> bool | None:
        return None if self.state is None else self.state.seems_checked

    @property
    def unchecked(self) -> bool | None:
        return None if self.state is None else not self.state.seems_checked

    @property
    def analyzed(self) -> bool:
        """Has the state been already automatically detected?"""
        return self._initial_state is not None

    @property
    def needs_review(self) -> bool | None:
        return None if self._initial_state is None else self._initial_state.needs_review

    @property
    def reviewed(self) -> bool:
        """Has the state been manually reviewed?"""
        return self._amended_state is not None


@dataclass
class Question:
    question_num: OriginalQuestionNumber
    answers: dict[OriginalAnswerNumber, Answer]
    score: float | None = None

    def __iter__(self):
        return iter(answer for answer in self.answers.values())

    def as_str(self, is_fix: bool = False) -> str:
        return (
            f"[{self.question_num}]\n"
            + "\n".join(a for answer in self if (a := answer.as_str(is_fix)))
            + "\n"
        )

    def update_from_str(self, s: str, is_fix: bool = False):
        for line in s.split("\n"):
            if line := line.strip():
                a, st = line.split(":")
                answer = self.answers[OriginalAnswerNumber(int(a))]
                state = getattr(CbxState, st.strip())
                if is_fix:
                    answer._amended_state = state
                else:
                    answer._initial_state = state

    def as_hashable_tuple(self):
        return tuple(answer.as_hashable_tuple() for answer in self)

    @property
    def checked_answers(self) -> list[Answer]:
        return [answer for answer in self if answer.checked]

    @property
    def correct_answers(self) -> list[Answer]:
        return [answer for answer in self if answer.is_correct]

    @property
    def needs_review(self) -> bool:
        return any(answer.needs_review for answer in self)

    @property
    def analyzed(self) -> bool:
        return all(answer.analyzed for answer in self)

    @property
    def reviewed(self) -> bool:
        """Return True if all answer needing review were reviewed, and at least one answer was reviewed."""
        answers_reviewed = [answer.reviewed for answer in self if answer.needs_review]
        return all(answers_reviewed) and len(answers_reviewed) >= 1
