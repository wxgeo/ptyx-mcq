from typing import TypedDict, Dict, Set, Tuple, Optional


class PicData(TypedDict):
    # ID of the document:
    ID: int
    # page number:
    page: int
    name: str
    student_ID: str
    # answers checked by the student for each question:
    answered: Dict[int, Set[int]]
    # Position of each checkbox in the page:
    positions: Dict[Tuple[int, int], Tuple[int, int]]
    cell_size: int
    # Translation table ({question number before shuffling: after shuffling})
    questions_nums: Dict[int, int]
    # Manual verification by the user ?
    verified: Optional[bool]
    pic_path: str


class DocumentData(TypedDict):
    pages: dict[int, PicData]
    name: str
    student_ID: str
    answered: dict[int, set[int]]  # {question: set of answers}
    score: float
    score_per_question: dict[int, float]  # {question: score}
