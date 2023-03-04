from dataclasses import dataclass, asdict, field
import json
from pathlib import Path
from typing import Any, TypeVar, TypedDict, Literal

T = TypeVar("T")


class OrderingConfiguration(TypedDict):
    questions: list[int]
    answers: dict[int, list[tuple[int, bool | None]]]


QuestionNumberOrDefault = Literal["default"] | int

StudentIdFormat = tuple[int, int, list[tuple[str, ...]]]


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
    mode: dict[QuestionNumberOrDefault, str]  # = field(default_factory=lambda: {"default": "some"})
    correct: dict[QuestionNumberOrDefault, float]  # = field(default_factory=lambda: {"default": 1})
    incorrect: dict[QuestionNumberOrDefault, float]  # = field(default_factory=lambda: {"default": 0})
    skipped: dict[QuestionNumberOrDefault, float]  # = field(default_factory=lambda: {"default": 0})
    floor: dict[QuestionNumberOrDefault, float | None]  # = field(default_factory=lambda: {"default": None})
    ceil: dict[QuestionNumberOrDefault, float | None]  # = field(default_factory=dict)
    id_format: StudentIdFormat | None = None
    students_ids: dict[str, str] = field(default_factory=dict)
    students_list: list[str] = field(default_factory=list)
    ordering: dict[int, OrderingConfiguration] = field(default_factory=dict)
    # ordering: {NUM: {'questions': [2,1,3...],
    #                  'answers': {1: [(2, True), (1, False), (3, True)...], ...}}, ...}
    boxes: dict[int, dict[int, dict[str, tuple[float, float]]]] = field(default_factory=dict)
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
        return Configuration(**decodejs(js))


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
        assert new_key in Configuration.__annotations__
        new_d[new_key] = d[key]  # type: ignore
    # Students ID must be kept as strings.
    new_d["students_ids"] = {str(key): val for key, val in new_d["students_ids"].items()}
    return new_d


def real2apparent(
    original_q_num: int, original_a_num: int | None, config: Configuration, doc_id: int
) -> tuple[int, int | None]:
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
    pdf_q_num = questions.index(original_q_num) + 1
    if original_a_num is None:
        return pdf_q_num, None
    for pdf_a_num, (ans_num, is_correct) in enumerate(answers[original_q_num], start=1):
        if ans_num == original_a_num:
            return pdf_q_num, pdf_a_num
    raise IndexError(f"Answer {original_a_num} not found for question {original_q_num}.")


def apparent2real(
    pdf_q_num: int, pdf_a_num: int | None, config: Configuration, doc_id: int
) -> tuple[int, int | None]:
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


def is_answer_correct(
    q_num: int, a_num: int, config: Configuration, doc_id: int, use_original_num: bool = True
) -> bool | None:
    if use_original_num:
        # q_num and a_num are question and answer number *before* shuffling questions.
        for original_a_num, is_correct in config.ordering[doc_id]["answers"][q_num]:
            if original_a_num == a_num:
                return is_correct
        raise IndexError(f"Answer {a_num} not found.")
    else:
        # q_num and a_num are question and answer number *after* shuffling questions.
        original_q_num = config.ordering[doc_id]["questions"][q_num - 1]
        return config.ordering[doc_id]["answers"][original_q_num][a_num - 1][1]


def get_answers_with_status(
    config: Configuration, *, correct: bool | None, use_original_num: bool = True
) -> dict[int, dict[int, set[int]]]:
    """Return a dict containing the set of the correct answers for each question for each document ID.

    By default, questions and answers are numbered following their original order of definition
    in the ptyx file.

    If `use_original_num` is set to `False`, questions numbers and correct answers numbers returned
    will be apparent ones (i.e. the number that appear in the document, after shuffling).
    """
    correct_answers_by_id = {}
    for doc_id in config.ordering:
        correct_answers = {}
        questions = config.ordering[doc_id]["questions"]
        answers = config.ordering[doc_id]["answers"]
        for i, q in enumerate(questions, start=1):
            # `i` is the 'apparent' question number.
            # `q` is the 'real' question number, i.e. the question number before shuffling.
            # `j` is the 'apparent' answer number.
            # `a` is the 'real' answer number, i.e. the answer number before shuffling.
            if use_original_num:
                correct_answers[q] = {a for (a, _is_correct) in answers[q] if _is_correct == correct}
            else:
                correct_answers[i] = {
                    j for (j, (a, _is_correct)) in enumerate(answers[q], start=1) if _is_correct == correct
                }
        correct_answers_by_id[doc_id] = correct_answers
    return correct_answers_by_id
