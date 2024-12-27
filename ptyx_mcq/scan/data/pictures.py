from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, TYPE_CHECKING

from PIL import Image
from numpy import ndarray, array
from ptyx.shell import print_error

from ptyx_mcq.scan.data.analyze.checkboxes import CheckboxAnalyzeResult
from ptyx_mcq.scan.data.analyze.student_names import read_student_id_and_name

from ptyx_mcq.parameters import FIX_DIR
from ptyx_mcq.scan.data.extraction import PdfHash, PicNum
from ptyx_mcq.scan.data.students import Student
from ptyx_mcq.scan.data.questions import CbxPositions, InvalidFormat, CbxState, Question
from ptyx_mcq.scan.picture_analyze.calibration import CalibrationData
from ptyx_mcq.scan.picture_analyze.identify_doc import IdentificationData
from ptyx_mcq.scan.picture_analyze.square_detection import adjust_checkbox
from ptyx_mcq.scan.picture_analyze.types_declaration import Pixel
from ptyx_mcq.tools.config_parser import (
    OriginalQuestionNumber,
    Configuration,
    DocumentId,
    PageNum,
    CbxRef,
    OriginalAnswerNumber,
)

if TYPE_CHECKING:
    from ptyx_mcq.scan.data import Page, ScanData


@dataclass(kw_only=True)
class Picture:
    """
    Stock all the information of a scanned picture.

    `path` is the path of the corresponding image on the filesystem.

    """

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
        self._load_student()
        self._load_checkboxes_state(is_fix=False)
        self._load_checkboxes_state(is_fix=True)

    def __iter__(self) -> Iterator[Question]:
        return iter(q for q in self.questions.values())

    def __eq__(self, other):
        if not isinstance(other, Picture):
            return False
        if self.questions is None or self.student is None or other.questions is None or other.student is None:
            raise ValueError("Unparsed pictures should not be compared. Analyze them before.")
        return self.as_hashable_tuple() == other.as_hashable_tuple()

    @property
    def scan_data(self) -> "ScanData":
        return self.page.doc.scan_data

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

    # def locate_file(self, local_path: Path | str) -> Path | None:
    #     return self.scan_data.paths.locate_file(f"{self.pdf_hash}/{local_path}")

    @property
    def cache_dir(self) -> Path:
        """The directory where all the automatically retrieved data are saved."""
        return self.path.parent

    # TODO: fix -> patch?
    @property
    def fix_dir(self) -> Path:
        """The directory where all the data modified by the user are saved."""
        return self.path.parent.parent.parent / f"{FIX_DIR}/{self.pdf_hash}"

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

        The first time the value is set, it will be saved in the `.cache` directory.
        If it is modified later, the value will be saved in the `.fix` directory then.
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
            self._initial_student = Student.load(self.cache_dir / f"students/{self.num}")
            self._amended_student = Student.load(self.fix_dir / f"students/{self.num}")

    def _save_student(self, is_fix=False) -> None:
        if self.student is not None:
            root = self.fix_dir if is_fix else self.cache_dir
            (folder := root / "students").mkdir(exist_ok=True)
            self.student.save(folder / str(self.num))

    @property
    def _student_identification_table_position(self) -> Pixel:
        """Get the position of the table where students check boxes to indicate their identifier."""
        return self.calibration_data.xy2ij(*self.config.id_table_pos)

    def retrieve_student(self, matrix: ndarray) -> Student | None:
        """
        Retrieve the student information from this picture.

        Return `None` if the document contains no such information.
        Note that the student name or identifier may be incorrect,
        since no verification occurs at this stage.
        """
        if self.page_num != 1:
            return None
        cfg = self.config
        return read_student_id_and_name(
            matrix,
            cfg.students_ids,
            self._student_identification_table_position,
            cfg.id_format,
            self.calibration_data.f_cell_size,
        )

    @property
    def student_reviewed(self) -> bool:
        return self._amended_student is not None

    # --------------------------
    #         Checkboxes
    # ==========================

    def _load_checkboxes_state(self, is_fix=False) -> None:
        path = (self.fix_dir if is_fix else self.cache_dir) / f"checkboxes/{self.num}"
        try:
            for part in path.read_text(encoding="utf8").split("["):
                if part:
                    q, answers_content = part.split("]")
                    self.questions[OriginalQuestionNumber(int(q))].update_from_str(
                        answers_content, is_fix=is_fix
                    )
        except (ValueError, OSError):
            pass

    def _save_checkboxes_state(self, is_fix=False) -> None:
        (folder := (self.fix_dir if is_fix else self.cache_dir) / f"checkboxes").mkdir(exist_ok=True)
        (folder / str(self.num)).write_text(
            "\n".join(question.as_str(is_fix=is_fix) for question in self), encoding="utf8"
        )

    @property
    def answered(self) -> dict[OriginalQuestionNumber, set[OriginalAnswerNumber]]:
        """Answers checked by the student for each question."""
        return {q.question_num: {a for a in q if a.state.seems_checked} for q in self}

    def get_checkboxes(self, matrix: ndarray = None) -> dict[CbxRef, ndarray]:
        """
        Retrieve all the arrays representing the checkbox content for the picture `pic`.

        Since reading the matrix from the corresponding webp file is quite slow,
        a cached matrix may be passed as argument; if missing, the matrix will be loaded from disk.
        """
        if matrix is None:
            matrix = self.as_matrix()
        cbx_content: dict[CbxRef, ndarray] = {}
        cell_size = self.calibration_data.cell_size
        for q, question in self.questions.items():
            for a, answer in question.answers.items():
                i, j = answer.position
                i, j = adjust_checkbox(matrix, i, j, cell_size)
                cbx_content[(q, a)] = matrix[i : i + cell_size, j : j + cell_size]
        return cbx_content

    @property
    def checkboxes_analyzed(self) -> bool:
        return all(question.analyzed for question in self)

    def update_checkboxes_states(self, states: CheckboxAnalyzeResult) -> None:
        for (q, a), state in states.items():
            self.questions[q].answers[a].state = state
        self._save_checkboxes_state()

    @property
    def checkboxes_need_review(self) -> bool:
        return any(question.needs_review for question in self)

    @property
    def checkbox_reviewed(self) -> bool:
        return any(question.reviewed for question in self)

    # ------------------
    #       Array
    # ==================

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
