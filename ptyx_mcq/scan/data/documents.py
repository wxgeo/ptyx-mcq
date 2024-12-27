from collections import ChainMap
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import NewType, Self, Mapping, Iterator, TYPE_CHECKING

from PIL import Image
from numpy import ndarray, array
from ptyx.shell import print_error

from ptyx_mcq.scan.picture_analyze.calibration import CalibrationData
from ptyx_mcq.scan.picture_analyze.identify_doc import IdentificationData
from ptyx_mcq.scan.picture_analyze.types_declaration import Pixel, Line, Col
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    StudentId,
    StudentName,
    OriginalQuestionAnswersDict,
    ApparentQuestionNumber,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    PageNum,
    CbxRef,
    Configuration,
)

if TYPE_CHECKING:
    from ptyx_mcq.scan.data import ScanData

PdfHash = NewType("PdfHash", str)
PicNum = NewType("PicNum", int)
PdfData = dict[PdfHash, dict[PicNum, tuple[CalibrationData, IdentificationData]]]
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


class RevisionStatus(Enum):
    MARKED_AS_CHECKED = auto()
    MARKED_AS_UNCHECKED = auto()

    def __repr__(self):
        return self.name


@dataclass(frozen=True)
class Student:
    """Data class regrouping information concerning one student."""

    id: StudentId
    name: StudentName

    def _as_str(self) -> str:
        return f"{self.name}\n{self.id}\n"

    @classmethod
    def _from_str(cls: "Student", file_content: str) -> "Student":
        try:
            student_name, student_id = file_content.strip().split("\n")
            return cls(name=StudentName(student_name), id=StudentId(student_id))
        except (ValueError, AttributeError):
            raise InvalidFormat(f"Incorrect file content: {file_content!r}")

    @classmethod
    def load(cls: Self, path: Path) -> Self:
        """Read the content of a student information file.

        May raise:
            - an OSError variant if the file is missing or unreadable.
            - an InvalidFormat if the file format is incorrect.
        """
        return cls._from_str(path.read_text(encoding="utf8"))

    def save(self, path: Path) -> None:
        path.write_text(self._as_str(), encoding="utf8")


# class Checkboxes(dict, Mapping[CbxRef, CbxState]):
#     """Dict containing all the checkboxes states (CHECKED, UNCHECKED, ...)."""
#
#     def _as_str(self) -> str:
#         # `{state!r}` and not `{state}`, to get "CHECKED" and not "CbxState.CHECKED".
#         return "\n".join(f"{q}, {a}: {state!r}" for (q, a), state in self.items()) + "\n"
#
#     @classmethod
#     def _from_str(cls: Self, content: str) -> Self:
#         cbx_states: Self = Checkboxes()
#         for line in content.split("\n"):
#             if line := line.strip():
#                 try:
#                     q_a, status = line.split(":")
#                     q, a = q_a.split(",")
#                     cbx_states[(OriginalQuestionNumber(int(q)), OriginalAnswerNumber(int(a)))] = getattr(
#                         CbxState, status.strip()
#                     )
#                 except (ValueError, AttributeError):
#                     raise InvalidFormat(f"Incorrect line: {line!r}")
#         return cbx_states
#
#     @classmethod
#     def load(cls: Self, path: Path) -> Self:
#         """Read the content of a checkboxes states file.
#
#         May raise:
#             - an OSError variant if the file is missing or unreadable.
#             - an InvalidFormat if the file format is incorrect.
#         """
#         return cls._from_str(path.read_text(encoding="utf8"))
#
#     def save(self, path: Path) -> None:
#         path.write_text(self._as_str(), encoding="utf8")
#
#     @property
#     def needs_review(self) -> bool:
#         return any(state.needs_review for state in self.values())


@dataclass
class Answer:
    answer_num: OriginalAnswerNumber
    # Should the checkbox have been checked?
    is_correct: bool | None
    # Position of the top-left pixel of the checkbox
    position: Pixel
    # State of the checkbox as detected by the program
    _initial_state: CbxState
    # State of the checkbox after user review, if any, else `None`.
    _amended_state: CbxState | None = None

    @property
    def state(self) -> CbxState:
        return self._initial_state if self._amended_state is None else self._amended_state

    def as_str(self, is_fix=False) -> str:
        state = self._amended_state if is_fix else self._initial_state
        return "" if state is None else f"{self.answer_num}: {state!r}"

    def as_hashable_tuple(self):
        return self.as_str(), self.as_str(is_fix=True)

    @property
    def needs_review(self) -> bool:
        return self._initial_state.needs_review


@dataclass
class Question:
    question_num: OriginalQuestionNumber
    answers: dict[OriginalQuestionNumber, Answer]

    def __iter__(self):
        return iter(answer for answer in self.answers.values())

    def as_str(self, is_fix=False) -> str:
        return (
            f"[{self.question_num}]\n"
            + "\n".join(a for answer in self if (a := answer.as_str(is_fix)))
            + "\n"
        )

    def as_hashable_tuple(self):
        return tuple(answer.as_hashable_tuple() for answer in self)

    @property
    def needs_review(self) -> bool:
        return any(answer.needs_review for answer in self)


@dataclass(kw_only=True)
class Picture:
    page: "Page"
    path: Path
    calibration_data: CalibrationData
    identification_data: IdentificationData
    questions: dict[OriginalQuestionNumber, Question]
    # _checkboxes: Checkboxes | None = None
    _initial_student: Student | None = None
    _amended_student: Student | None = None
    use: bool = True

    def __post_init__(self) -> None:
        try:
            self._load_student()
            self._load_checkboxes()
        except (OSError, InvalidFormat):
            pass

    def __iter__(self) -> Iterator[Question]:
        return iter(q for q in self.questions.values())

    def __eq__(self, other):
        if not isinstance(other, Picture):
            return False
        if self.questions is None or self.student is None or other.questions is None or other.student is None:
            raise ValueError("Unparsed pictures should not be compared. Analyze them before.")
        return self.as_hashable_tuple() == other.as_hashable_tuple()

    @property
    def scan_data(self) -> ScanData:
        return self.page.doc.parent

    @property
    def config(self) -> Configuration:
        return self.scan_data.config

    @property
    def doc_id(self) -> DocumentId:
        """The id of the original document."""
        return self.identification_data.doc_id

    @property
    def page_num(self) -> PageNum:
        """The page number in the original document."""
        return self.identification_data.page_num

    def as_hashable_tuple(self) -> tuple:
        return (
            self.student,
            self.identification_data.doc_id,
            self.identification_data.page_num,
            tuple(q.as_hashable_tuple() for q in self),
        )

    # ------------------
    #       Path
    # ==================

    def locate_file(self, local_path: Path | str) -> Path | None:
        return self.scan_data.paths.locate_file(f"{self.pdf_hash}/{local_path}")

    @property
    def dir(self):
        return self.path.parent

    @property
    def short_path(self) -> str:
        return str(self.path.with_suffix("").relative_to(self.path.parent.parent))

    @property
    def pdf_hash(self) -> PdfHash:
        return PdfHash(self.path.parent.name)

    @property
    def num(self) -> PicNum:
        return PicNum(int(self.path.stem))

    # -------------------
    #      Students
    # ===================

    @property
    def student(self) -> Student | None:
        """
        The student information found in this picture, if any, else `None`.

        Note that only the first page of a document will contain student information, so for all other pages,
        `None` will be returned instead.

        When setting the value, the new value will be automatically saved on drive,
        to be retrieved on an eventual later run.

        The first time the value is set, it will be saved in the `cache` directory.
        If it is modified later, the value will be saved in the `fix` directory then.
        """
        return self._initial_student if self._amended_student is None else self._amended_student

    @student.setter
    def student(self, student: Student):
        if self._initial_student is None:
            self._initial_student = student
            self._save_student()
        else:
            self._amended_student = student
            self._save_student(is_fix=True)

    def _load_student(self) -> None:
        if self.page_num == 1:
            path = self.locate_file(f"students/{self.num}")
            if path is not None:
                self._student = Student.load(path)

    def _save_student(self, is_fix=False) -> None:
        if self.student is not None:
            root = self.scan_data.paths.dirs.fix if is_fix else self.scan_data.paths.dirs.cache
            (folder := root / "students").mkdir(exist_ok=True)
            self.student.save(folder / str(self.num))

    # --------------------------
    #         Checkboxes
    # ==========================

    # @property
    # def checkboxes(self) -> Checkboxes:
    #     return self._checkboxes

    # @checkboxes.setter
    # def checkboxes(self, checkboxes: Checkboxes):
    #     is_fix = self._checkboxes is not None
    #     self._checkboxes = checkboxes
    #     self._save_checkboxes(is_fix=is_fix)

    def _load_checkboxes(self) -> None:
        path = self.locate_file(f"checkboxes/{self.num}")
        if path is not None:
            checkboxes = Checkboxes.load(path)
            if set(self.scan_data.config.boxes[self.doc_id][self.page_num]) == set(checkboxes):
                self._checkboxes = checkboxes

    def _save_checkboxes(self, is_fix=False) -> None:
        if self.checkboxes is not None:
            root = self.scan_data.paths.dirs.fix if is_fix else self.scan_data.paths.dirs.cache
            (folder := root / "checkboxes").mkdir(exist_ok=True)
            self.checkboxes.save(folder / str(self.num))

    def _boxes_latex_position(self, doc_id: DocumentId, page: PageNum) -> dict[CbxRef, tuple[float, float]]:
        try:
            # The page may contain no question, so return an empty dict by default.
            return self.config.boxes[doc_id].get(page, {})
        except KeyError:
            print(f"ERROR: doc id: {doc_id}, doc page: {page}")
            raise

    def get_checkboxes_positions(self) -> CbxPositions:
        """Retrieve the checkboxes positions in the pixel's matrix of the picture `pic`."""
        # The page may contain no question, so return an empty dict by default.
        boxes = self._boxes_latex_position(self.doc_id, self.page_num)
        return {q_a: self.xy2ij(*xy) for q_a, xy in boxes.items()}

    @property
    def answered(self) -> dict[OriginalQuestionNumber, set[OriginalAnswerNumber]]:
        """Answers checked by the student for each question."""
        # if self.questions is None:
        #     raise ValueError("Picture must be analyzed first.")
        return {q.question_num: {a for a in q if a.state.seems_checked} for q in self}

    # @property
    # def questions(self) -> list[OriginalQuestionNumber]:
    #     """All the (original) question numbers found in the picture."""
    #     return sorted({q for (q, a) in self.checkboxes})

    def _as_str(self) -> str:
        # `{state!r}` and not `{state}`, to get "CHECKED" and not "CbxState.CHECKED".
        return "\n".join(f"[{q}], {a}: {state!r}" for (q, a), state in self.items()) + "\n"

    @classmethod
    def _from_str(cls: Self, content: str) -> Self:
        cbx_states: Self = Checkboxes()
        for line in content.split("\n"):
            if line := line.strip():
                try:
                    q_a, status = line.split(":")
                    q, a = q_a.split(",")
                    cbx_states[(OriginalQuestionNumber(int(q)), OriginalAnswerNumber(int(a)))] = getattr(
                        CbxState, status.strip()
                    )
                except (ValueError, AttributeError):
                    raise InvalidFormat(f"Incorrect line: {line!r}")
        return cbx_states

    @classmethod
    def load(cls: Self, path: Path) -> Self:
        """Read the content of a checkboxes states file.

        May raise:
            - an OSError variant if the file is missing or unreadable.
            - an InvalidFormat if the file format is incorrect.
        """
        return cls._from_str(path.read_text(encoding="utf8"))

    def save(self, path: Path) -> None:
        path.write_text(self._as_str(), encoding="utf8")

    # ------------------
    #       Array
    # ==================

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


@dataclass
class Page:
    doc: "Document"
    page_num: PageNum
    pictures: list[Picture]

    @property
    def has_conflicts(self) -> bool:
        # No conflict is the data are the same (checkboxes + names).
        return len(self.used_pictures) >= 2

    @property
    def used_pictures(self) -> list[Picture]:
        return [pic for pic in self.pictures if pic.use]

    # @property
    # def _conflicting_versions(self) -> list[Picture]:
    #     return list({pic.as_hashable_tuple(): pic for pic in self.pictures}.values())

    @property
    def pic(self) -> Picture:
        assert self.pictures
        if self.has_conflicts:
            raise ValueError(
                f"Only one picture expected, but {len(self.pictures)} conflicting versions found."
            )
        return self.pictures[0]

    def disable_duplicates(self) -> None:
        """Remove pictures which contain the same information, keeping only conflicting versions."""
        seen = set()
        for pic in self.pictures:
            if pic.use:
                t = pic.as_hashable_tuple()
                if t in seen:
                    pic.use = False
                else:
                    seen.add(t)

    def __iter__(self) -> Iterator[Picture]:
        return iter(self.pictures)


@dataclass
class Document:
    parent: "ScanData"
    doc_id: DocumentId
    pages: dict[PageNum, Page]
    score: float | None = None
    score_per_question: dict[OriginalQuestionNumber, float] | None = None

    @property
    def first_page(self) -> Page | None:
        return self.pages.get(PageNum(1))

    @property
    def pictures(self) -> list[Picture]:
        """Return all the pictures associated with this document."""
        return [pic for page in self.pages.values() for pic in page.pictures]

    @property
    def answered(self) -> ChainMap[OriginalQuestionNumber, set[OriginalAnswerNumber]]:
        """Answers checked by the student for each question."""
        return ChainMap(*(page.pic.answered for page in self.pages.values()))

    def __iter__(self) -> Iterator[Page]:
        return iter(self.pages.values())

    @property
    def questions(self) -> list[OriginalQuestionNumber]:
        """All the (original) question numbers found in the picture."""
        return sorted({q for page in self for pic in page for (q, a) in pic.checkboxes})

    @property
    def student_name(self) -> StudentName:
        return self.pages[PageNum(1)].pic.student.name

    def _as_str(self):
        return "\n".join(
            f"{page.page_num}: " + ", ".join(pic.short_path for pic in page.pictures) for page in self
        )

    def save_index(self):
        """Save an index of all the document pages and the corresponding pictures."""
        (self.parent.dirs.index / str(self.doc_id)).write_text(self._as_str(), encoding="utf8")
