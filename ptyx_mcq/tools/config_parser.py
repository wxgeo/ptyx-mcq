import typing
from dataclasses import dataclass, asdict, field
import json
from pathlib import Path
from typing import Any, TypeVar, TypedDict, Literal, NewType

T = TypeVar("T")

DocumentId = NewType("DocumentId", int)
StudentId = NewType("StudentId", str)
StudentName = NewType("StudentName", str)

OriginalQuestionNumber = NewType("OriginalQuestionNumber", int)
ApparentQuestionNumber = NewType("ApparentQuestionNumber", int)
QuestionNumber = OriginalQuestionNumber | ApparentQuestionNumber

OriginalAnswerNumber = NewType("OriginalAnswerNumber", int)
ApparentAnswerNumber = NewType("ApparentAnswerNumber", int)
AnswerNumber = OriginalAnswerNumber | ApparentAnswerNumber


class OrderingConfiguration(TypedDict):
    questions: list[OriginalQuestionNumber]
    answers: dict[OriginalQuestionNumber, list[tuple[OriginalAnswerNumber, bool | None]]]


QuestionNumberOrDefault = Literal["default"] | OriginalQuestionNumber

StudentIdFormat = tuple[int, int, list[tuple[str, ...]]]


class InvalidConfigurationKey(KeyError):
    """Error raised when an unknown key appears in a configuration file."""


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        # Save sets as tuples.
        if isinstance(obj, set):
            return tuple(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


# # Default configuration:
# "mode": {"default": "some"},
# "correct": {"default": 1},
# "incorrect": {"default": 0},
# "skipped": {"default": 0},
# "floor": {"default": None},
# "ceil": {"default": None},
# # 'correct_answers': correct_answers, # {1: [4], 2:[1,5], ...}
# "students": [],
# "id_table_pos": None,
# "students_ids": {},
# "ordering": {},
# # {NUM: {'questions': [2,1,3...],
# #        'answers': {1: [(2, True), (1, False), (3, True)...], ...}}, ...}
# "boxes": {},  # {NUM: {'tag': 'p4, (23.456, 34.667)', ...}, ...}
# "id_format": None,


# TODO: improve typing precision
@dataclass(kw_only=True, slots=True)
class Configuration:
    mode: dict[QuestionNumberOrDefault, str] = field(default_factory=lambda: {"default": "all"})
    correct: dict[QuestionNumberOrDefault, float] = field(default_factory=lambda: {"default": 1})
    incorrect: dict[QuestionNumberOrDefault, float] = field(default_factory=lambda: {"default": 0})
    skipped: dict[QuestionNumberOrDefault, float] = field(default_factory=lambda: {"default": 0})
    weight: dict[QuestionNumberOrDefault, float] = field(default_factory=lambda: {"default": 1})
    # -inf and inf would be sensible defaults for floor and ceil,
    # but unfortunately they aren't supported by ast.literal_eval().
    floor: dict[QuestionNumberOrDefault, float | None] = field(default_factory=lambda: {"default": None})
    ceil: dict[QuestionNumberOrDefault, float | None] = field(default_factory=lambda: {"default": None})
    id_format: StudentIdFormat | None = None
    default_score: str = ""
    students_ids: dict[StudentId, StudentName] = field(default_factory=dict)
    students_list: list[StudentName] = field(default_factory=list)
    ordering: dict[DocumentId, OrderingConfiguration] = field(default_factory=dict)
    # ordering: {NUM: {'questions': [2,1,3...],
    #                  'answers': {1: [(2, True), (1, False), (3, True)...], ...}}, ...}
    boxes: dict[DocumentId, dict[int, dict[str, tuple[float, float]]]] = field(default_factory=dict)
    # boxes: {NUM: {'tag': 'p4, (23.456, 34.667)', ...}, ...}
    id_table_pos: tuple[float, float] | None = None
    max_score: float | None = None

    def dump(self, path: Path | str) -> None:
        """Dump `cfg` dict to `path` as json."""
        with open(path, "w") as f:
            f.write(encode2js(self.as_dict(), formatter=(lambda s: s.upper().center(40, "-"))))

    def as_dict(self):
        return asdict(self)

    #
    # def update(self, d:dict[str, Any]) -> None:
    #     self.__dict__.update(d)

    @classmethod
    def load(cls, path: Path | str) -> "Configuration":
        """Load `path` configuration file (json) and return a dict."""
        with open(path) as f:
            js = f.read()
        try:
            return Configuration(**decodejs(js))
        except InvalidConfigurationKey as e:
            raise InvalidConfigurationKey(
                f"Error when loading '{path}' configuration file. {e.args[0]}\n"
                "The configuration file may be old, and keys must then be updated manually.\n"
                f"Valid keys are: {', '.join(Configuration.__annotations__)}."
            )


def encode2js(o, formatter=(lambda s: s), _level=0) -> str:
    """Encode dict `o` to JSON.

    If `formatter` is set, it must be a function used to format first-level
    keys of `o`."""

    def _dumps(o_: Any) -> str:
        return json.dumps(o_, ensure_ascii=False, cls=CustomJSONEncoder)

    if _level == 0 and not isinstance(o, dict):
        raise NotImplementedError
    if isinstance(o, dict):
        if _level == 0:
            blocks = []
            for k, v in o.items():
                blocks.append(f'"{formatter(k)}":\n' + encode2js(v, _level=_level + 1))
            return "{\n\n%s\n\n}" % ",\n\n".join(blocks)
        else:
            blocks = []
            indent = (_level - 1) * "\t"
            for k, v in o.items():
                # Warning: all JSON keys must be strings !
                blocks.append(f'{indent}"{k}": ' + encode2js(v, _level=_level + 1))
            return "{\n%s\n%s}" % (",\n".join(blocks), indent)
    elif isinstance(o, (tuple, set, list)):
        assert _level != 0
        if _level == 1:
            return "[\n%s\n]" % ",\n".join(_dumps(v) for v in o)
        else:
            return _dumps(o)
    else:
        return _dumps(o)


def keys2int(d: dict[str, T]) -> dict[int | str, T]:
    return {(int(k) if k.isdecimal() else k): v for k, v in d.items()}


def decodejs(js: str) -> dict[str, Any]:
    d = json.loads(js, object_hook=keys2int)
    new_d: dict[str, Any] = {}
    # Strip '-' from keys and convert them to lower case.
    for key in d:
        new_key = key.strip("-").lower()
        if new_key not in Configuration.__annotations__:
            raise InvalidConfigurationKey(f"Unknown key: {new_key!r}.")
        new_d[new_key] = d[key]
    # Students ID must be kept as strings.
    new_d["students_ids"] = {str(key): val for key, val in new_d["students_ids"].items()}
    return new_d


def real2apparent(
    original_q_num: OriginalQuestionNumber,
    original_a_num: OriginalAnswerNumber | None,
    config: Configuration,
    doc_id: DocumentId,
) -> tuple[ApparentQuestionNumber, ApparentAnswerNumber | None]:
    """Return apparent question number and answer number.

    If `a` is None, return only question number.

    By "apparent", it means question and answer numbers as they
    will appear in the PDF file, after shuffling questions and answers.

    Arguments `q` and `a` are real question and answer numbers, that is
    the ones before questions and answers were shuffled."""
    questions = config.ordering[doc_id]["questions"]
    answers = config.ordering[doc_id]["answers"]
    # Apparent question number (ie. after shuffling).
    # Attention, list index 0 corresponds to question number 1.
    pdf_q_num = ApparentQuestionNumber(questions.index(original_q_num) + 1)
    if original_a_num is None:
        return pdf_q_num, None
    for pdf_a_num, (ans_num, is_correct) in enumerate(answers[original_q_num], start=1):
        if ans_num == original_a_num:
            return pdf_q_num, ApparentAnswerNumber(pdf_a_num)
    raise IndexError(f"Answer {original_a_num} not found for question {original_q_num}.")


@typing.overload
def apparent2real(
    pdf_q_num: ApparentQuestionNumber,
    pdf_a_num: None,
    config: Configuration,
    doc_id: DocumentId,
) -> tuple[OriginalQuestionNumber, None]:
    """Signature when pdf_a_num is None."""


@typing.overload
def apparent2real(
    pdf_q_num: ApparentQuestionNumber,
    pdf_a_num: ApparentAnswerNumber,
    config: Configuration,
    doc_id: DocumentId,
) -> tuple[OriginalQuestionNumber, OriginalAnswerNumber]:
    """Signature when pdf_a_num is not None."""


def apparent2real(
    pdf_q_num: ApparentQuestionNumber,
    pdf_a_num: ApparentAnswerNumber | None,
    config: Configuration,
    doc_id: DocumentId,
) -> tuple[OriginalQuestionNumber, OriginalAnswerNumber | None]:
    """Return real question number and answer number.

    If `a` is None, return only question number.
    """
    questions = config.ordering[doc_id]["questions"]
    answers = config.ordering[doc_id]["answers"]
    # Real question number (ie. before shuffling).
    # Attention, first question is numbered 1, corresponding to list index 0.
    original_q_num = questions[pdf_q_num - 1]
    if pdf_a_num is None:
        return original_q_num, None
    # Real answer number (ie. before shuffling).
    original_a_num = answers[original_q_num][pdf_a_num - 1][0]
    return original_q_num, original_a_num


@typing.overload
def is_answer_correct(
    q_num: OriginalQuestionNumber,
    a_num: OriginalAnswerNumber,
    config: Configuration,
    doc_id: DocumentId,
    use_original_num: Literal[True] = True,
):
    """Function signature when `use_original_num` is `True`."""


@typing.overload
def is_answer_correct(
    q_num: ApparentQuestionNumber,
    a_num: ApparentAnswerNumber,
    config: Configuration,
    doc_id: DocumentId,
    use_original_num: Literal[False],
):
    """Function signature when `use_original_num` is `False`."""


def is_answer_correct(
    q_num: QuestionNumber,
    a_num: AnswerNumber,
    config: Configuration,
    doc_id: DocumentId,
    use_original_num: bool = True,
) -> bool | None:
    if use_original_num:
        # q_num and a_num are question and answer number *before* shuffling questions.
        for original_a_num, is_correct in config.ordering[doc_id]["answers"][OriginalQuestionNumber(q_num)]:
            if original_a_num == a_num:
                return is_correct
        raise IndexError(f"Answer {a_num} not found.")
    else:
        # q_num and a_num are question and answer number *after* shuffling questions.
        original_q_num = config.ordering[doc_id]["questions"][q_num - 1]
        return config.ordering[doc_id]["answers"][original_q_num][a_num - 1][1]


OriginalQuestionAnswersDict = dict[OriginalQuestionNumber, set[OriginalAnswerNumber]]
ApparentQuestionAnswersDict = dict[ApparentQuestionNumber, set[ApparentAnswerNumber]]
QuestionToAnswerDict = OriginalQuestionAnswersDict | ApparentQuestionAnswersDict


@typing.overload
def get_answers_with_status(
    config: Configuration, *, correct: bool | None, use_original_num: Literal[True] = True
) -> dict[DocumentId, OriginalQuestionAnswersDict]:
    """Function signature when `use_original_num` is `True`."""


@typing.overload
def get_answers_with_status(
    config: Configuration, *, correct: bool | None, use_original_num: Literal[False]
) -> dict[DocumentId, ApparentQuestionAnswersDict]:
    """Function signature when `use_original_num` is `False`."""


def get_answers_with_status(
    config: Configuration, *, correct: bool | None, use_original_num: bool = True
) -> dict[DocumentId, OriginalQuestionAnswersDict] | dict[DocumentId, ApparentQuestionAnswersDict]:
    """Return a dict containing the set of the correct answers for each question for each document ID.

    By default, questions and answers are numbered following their original order of definition
    in the ptyx file.

    If `use_original_num` is set to `False`, questions numbers and correct answers numbers returned
    will be apparent ones (i.e. the number that appear in the document, after shuffling).
    """
    if use_original_num:
        return _get_original_num_answers_with_status(config, correct=correct)
    else:
        return _get_apparent_num_answers_with_status(config, correct=correct)


def _get_original_num_answers_with_status(
    config: Configuration, *, correct: bool | None
) -> dict[DocumentId, OriginalQuestionAnswersDict]:
    correct_answers_by_id: dict[DocumentId, OriginalQuestionAnswersDict] = {}
    for doc_id in config.ordering:
        correct_answers: OriginalQuestionAnswersDict = {}
        questions = config.ordering[doc_id]["questions"]
        answers = config.ordering[doc_id]["answers"]
        for q in questions:
            # `q` is the 'real' question number, i.e. the question number before shuffling.
            # `a` is the 'real' answer number, i.e. the answer number before shuffling.
            correct_answers[q] = {a for (a, _is_correct) in answers[q] if _is_correct == correct}
        correct_answers_by_id[doc_id] = correct_answers
    return correct_answers_by_id


def _get_apparent_num_answers_with_status(
    config: Configuration, *, correct: bool | None
) -> dict[DocumentId, ApparentQuestionAnswersDict]:
    correct_answers_by_id: dict[DocumentId, ApparentQuestionAnswersDict] = {}
    for doc_id in config.ordering:
        correct_answers: ApparentQuestionAnswersDict = {}
        questions = config.ordering[doc_id]["questions"]
        answers = config.ordering[doc_id]["answers"]
        for i, q in enumerate(questions, start=1):
            # `i` is the 'apparent' question number.
            # `q` is the 'real' question number, i.e. the question number before shuffling.
            # `j` is the 'apparent' answer number.
            # `a` is the 'real' answer number, i.e. the answer number before shuffling.
            correct_answers[ApparentQuestionNumber(i)] = {
                ApparentAnswerNumber(j)
                for (j, (a, _is_correct)) in enumerate(answers[q], start=1)
                if _is_correct == correct
            }
        correct_answers_by_id[doc_id] = correct_answers
    return correct_answers_by_id
