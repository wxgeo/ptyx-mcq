"""
Analyze the data extracted from the input pdf.

This means:
- detecting checkboxes
- evaluating checkboxes state
- retrieving student name and identifier
"""
import concurrent.futures
import multiprocessing
from functools import partial
from typing import TYPE_CHECKING

from numpy import ndarray, concatenate
from ptyx.shell import ANSI_CYAN, ANSI_RESET, ANSI_GREEN, ANSI_YELLOW

from ptyx_mcq.scan.data.analyze.checkboxes import analyze_checkboxes, eval_checkbox_color
from ptyx_mcq.scan.data.analyze.student_names import read_student_id_and_name
from ptyx_mcq.scan.data.structures import CbxState, Student, Picture, Document, InvalidFormat, Checkboxes
from ptyx_mcq.scan.picture_analyze.square_detection import adjust_checkbox
from ptyx_mcq.scan.picture_analyze.types_declaration import Line, Col, Pixel
from ptyx_mcq.tools.config_parser import (
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    PageNum,
    DocumentId,
    CbxRef,
    StudentName,
    StudentId,
)

if TYPE_CHECKING:
    from ptyx_mcq.scan.data.main_manager import ScanData


CbxPositions = dict[CbxRef, tuple[Line, Col]]


class PictureAnalyzer:
    """
    Analyze a picture to extract student information and the state of checkboxes.

    Both operations are performed in a single pass to avoid opening the same picture twice.
    This optimization is necessary because pictures are stored on disk, not in memory,
    to prevent memory saturation.
    """

    def __init__(self, data_handler: "ScanData"):
        self.data_handler: "ScanData" = data_handler
        # self._checkboxes_state: dict[DocumentId, dict[Picture, dict[CbxRef, CbxState]]] | None = None
        # self._students: dict[DocumentId, dict[Picture, Student]] | None = None
        # self._info: dict[DocumentId, dict[Picture, ReviewData]] | None = None

    @property
    def dirs(self):
        return self.data_handler.dirs

    @property
    def index(self):
        return self.data_handler.index

    @property
    def config(self):
        return self.data_handler.config

    # -------------------
    #     Global info
    # ===================

    def run(self):
        """Analyze all pictures, and add corresponding data to them."""
        for doc_id, doc in self.index.items():
            self.update_doc_info(doc)

    def update_doc_info(self, doc: Document) -> None:
        """Retrieve the state of each checkbox (checked or not) and the student id and name.

        Attempt to load it from disk.
        If not found, generate the info by evaluating the blackness of each checkbox.
        """
        # Try to load it from the disk.
        doc_info = self.load_info(doc)
        if doc_info is None:
            # No corresponding data on the disk, generate the data, and write it on the disk.
            print(f"Analyzing document: {doc.doc_id}")
            doc_info = self.get_doc_info(doc)
            self.save_info(doc, doc_info)
        for pic, (student, cbx_states) in zip(doc.pictures, doc_info, strict=True):
            pic.checkboxes = cbx_states
            pic.student = student
            if pic.student is not None and pic.student.name == "":
                # The students name to ID mapping may have been updated
                # (using `mcq fix` for example).
                # Let's try again to get names from ID.
                name = self.config.students_ids.get(pic.student.id, StudentName(""))
                if name != "":
                    pic.student.name = name
                    pic.student.save(pic.dir / str(pic.num))

    def get_doc_info(self, doc: Document) -> list[tuple[Student | None, Checkboxes]]:
        """Analyze the state of each checkbox (checked or not) and the student id and name."""
        # Get all the pictures corresponding to the given document id.
        pictures = doc.pictures
        # Put pictures arrays in cache (there are not so much of them for a single document),
        # since they will be used both to analyze the answers and to read the student id.
        matrices = [pic.as_matrix() for pic in pictures]
        cbx = [self.get_checkboxes(pic, matrix) for pic, matrix in zip(pictures, matrices)]
        # Analyze each checkbox.
        # All the checkboxes of the same document must be inspected together
        # to improve the checkboxes' states review, since a given student will probably
        # check all its document boxes in a consistent way.
        return [
            ((self.get_student(pic, matrix) if pic.page_num == 1 else None), cbx_states)
            for pic, cbx_states, matrix in zip(pictures, analyze_checkboxes(cbx), matrices)
        ]

    def load_info(self, doc: Document) -> list[tuple[Student | None, Checkboxes]] | None:
        doc_students = self.load_students(doc)
        doc_cbx_states = self.load_checkboxes_states(doc)
        if doc_students is None or doc_cbx_states is None:
            return None
        return list(zip(doc_students, doc_cbx_states, strict=True))

    def save_info(self, doc: Document, doc_info: list[tuple[Student | None, Checkboxes]]) -> None:
        students_info, cbx_info = zip(*doc_info)
        self.save_checkboxes_states(doc, cbx_info)
        self.save_students(doc, students_info)

    # -------------------
    #     Students
    # ===================

    def get_student_identification_table_position(self, pic: Picture) -> Pixel:
        """Get the position of the table where students check boxes to indicate their identifier."""
        return pic.xy2ij(*self.config.id_table_pos)

    def get_student(self, pic: Picture, matrix: ndarray) -> Student | None:
        """
        Recover the student information from the given picture.

        Return `None` if the document contains no such information.
        Note that the student name or identifier may be incorrect,
        since no verification occurs at this stage.
        """
        if pic.page_num != 1:
            return None
        pos = self.get_student_identification_table_position(pic)
        cfg = self.config
        return read_student_id_and_name(
            matrix, cfg.students_ids, pos, cfg.id_format, pic.calibration_data.f_cell_size
        )

    @staticmethod
    def save_students(doc: Document, students_info: list[Student | None]) -> None:
        for pic, student in zip(doc.pictures, students_info):
            if student is not None:
                (folder := pic.dir / "students").mkdir(exist_ok=True)
                student.save(folder / str(pic.num))

    @staticmethod
    def _load_pic_student(pic: Picture) -> Student | None:
        return Student.load(pic.dir / f"students/{pic.num}") if pic.page_num == 1 else None

    def load_students(self, doc: Document) -> list[Student | None] | None:
        try:
            return [self._load_pic_student(pic) for pic in doc.pictures]
        except (OSError, InvalidFormat):
            return None

    # -------------------
    #     Checkboxes
    # ===================

    def _boxes_latex_position(self, doc_id: DocumentId, page: PageNum) -> dict[CbxRef, tuple[float, float]]:
        try:
            # The page may contain no question, so return an empty dict by default.
            return self.config.boxes[doc_id].get(page, {})
        except KeyError:
            print(f"ERROR: doc id: {doc_id}, doc page: {page}")
            raise

    def get_checkboxes_positions(self, pic: Picture) -> CbxPositions:
        """Retrieve the checkboxes positions in the pixel's matrix of the picture `pic`."""
        # The page may contain no question, so return an empty dict by default.
        boxes = self._boxes_latex_position(pic.doc_id, pic.page_num)
        return {q_a: pic.xy2ij(*xy) for q_a, xy in boxes.items()}

    def get_checkboxes(self, pic: Picture, matrix: ndarray = None) -> Checkboxes:
        """
        Retrieve all the arrays representing the checkbox content for the picture `pic`.

        Since reading the matrix from the corresponding webp file is quite slow,
        a cached matrix may be passed as argument; if missing, the matrix will be loaded from disk.
        """
        if matrix is None:
            matrix = pic.as_matrix()
        cbx_content = Checkboxes()
        positions = self.get_checkboxes_positions(pic)
        cell_size = pic.calibration_data.cell_size
        for (q, a), (i, j) in positions.items():
            i, j = adjust_checkbox(matrix, i, j, cell_size)
            cbx_content[(q, a)] = matrix[i : i + cell_size, j : j + cell_size]
        return cbx_content

    @staticmethod
    def save_checkboxes_states(doc: Document, cbx_info: list[Checkboxes]) -> None:
        """Save to disk the checkboxes states for all the pictures associated with the given document id."""
        for pic, cbx_states in zip(doc.pictures, cbx_info, strict=True):
            (folder := pic.dir / "checkboxes").mkdir(exist_ok=True)
            cbx_states.save(folder / str(pic.num))

    def load_checkboxes_states(self, doc: Document) -> list[Checkboxes] | None:
        """Load from disk the checkboxes states for all the pictures associated with the given document id."""
        doc_cbx_states: list[Checkboxes] = []
        for pic in doc.pictures:
            try:
                # Read the file and import its data.
                result: Checkboxes = Checkboxes.load(pic.dir / f"checkboxes/{pic.num}")
                # Now, we should verify that the (<question_num>, <answer_num>) keys
                # are the expected one. (Unexpected or missing keys are unlikely,
                # yet maybe the disk is corrupted?)
                expected = set(self._boxes_latex_position(pic.doc_id, pic.page_num))
                if set(result) == expected:
                    doc_cbx_states.append(result)
                else:
                    # Missing (or incorrect) data!
                    return None
            except (InvalidFormat, OSError):
                # The data was not found on disk or the data are invalid.
                return None
        return doc_cbx_states
