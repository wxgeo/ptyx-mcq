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
from pathlib import Path
from typing import TYPE_CHECKING

from numpy import ndarray, concatenate
from ptyx.shell import ANSI_CYAN, ANSI_RESET, ANSI_GREEN, ANSI_YELLOW

from ptyx_mcq.scan.data.analyze.checkboxes import analyze_checkboxes
from ptyx_mcq.scan.data.analyze.student_names import read_student_id_and_name
from ptyx_mcq.scan.data.structures import DetectionStatus, DocumentData, ReviewData, Student, Picture
from ptyx_mcq.scan.picture_analyze.checkbox_analyzer import eval_checkbox_color
from ptyx_mcq.scan.picture_analyze.square_detection import adjust_checkbox, test_square_color
from ptyx_mcq.scan.picture_analyze.types_declaration import Line, Col, Pixel
from ptyx_mcq.tools.config_parser import (
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    Page,
    DocumentId,
    CbxRef,
    StudentName,
    StudentId,
)
from ptyx_mcq.tools.pic import save_webp

if TYPE_CHECKING:
    from ptyx_mcq.scan.data.main_manager import DataHandler

CheckboxAnalyzeResult = dict[CbxRef, DetectionStatus]
CheckboxesPositions = dict[CbxRef, tuple[Line, Col]]


class InvalidFormat(RuntimeError):
    """Raised when a file has an invalid format and cannot be decoded."""


class PictureAnalyzer:
    """
    Analyze a picture to extract student information and the state of checkboxes.

    Both operations are performed in a single pass to avoid opening the same picture twice.
    This optimization is necessary because pictures are stored on disk, not in memory,
    to prevent memory saturation.
    """

    def __init__(self, data_handler: "DataHandler"):
        self.data_handler: "DataHandler" = data_handler
        # self._checkboxes_state: dict[DocumentId, dict[Picture, dict[CbxRef, DetectionStatus]]] | None = None
        # self._students: dict[DocumentId, dict[Picture, Student]] | None = None
        self._info: dict[DocumentId, dict[Picture, ReviewData]] | None = None

    @property
    def dirs(self):
        return self.data_handler.dirs

    @property
    def data(self):
        return self.data_handler.data

    @property
    def config(self):
        return self.data_handler.config

    # -------------------
    #     Global info
    # ===================

    @property
    def info(self) -> dict[DocumentId, dict[Picture, ReviewData]]:
        """Retrieve the state of each checkbox (checked or not).

        The returned dictionary is cached. The method follows this process:
        1. Attempt to retrieve the dictionary from the cache.
        2. If not cached, try loading it from disk.
        3. As a last resort, generate the dictionary by evaluating the blackness of each checkbox.
        """
        if self._info is None:
            # Value not in cache.
            self._info = {}
            for doc_id in self.data_handler.index:
                # Try to load it from the disk.
                doc_info = self.load_info(doc_id)
                if doc_info is None:
                    # No corresponding data on the disk, generate the data, and write it on the disk.
                    print(f"Analyzing document: {doc_id}")
                    self._info[doc_id] = self.get_doc_info(doc_id)
                    self.save_info(doc_id)
                else:
                    self._info[doc_id] = doc_info
        assert self._info is not None
        return self._info

    def get_doc_info(self, doc_id: DocumentId) -> dict[Picture, ReviewData]:
        # Get all the pictures corresponding to the given document id.
        doc_pics = self.data_handler.get_document_pictures(doc_id)
        # Put pictures arrays in cache (there are not so much pictures for a single document).
        matrices = {pic: pic.as_matrix() for pic in doc_pics}
        # Analyze each checkbox.
        # All the checkboxes of the same document must be inspected together
        # to improve the checkboxes' states review, since a given student will probably
        # check all its document boxes in a consistent way.
        to_analyze = {pic: self.get_checkboxes(pic, matrix=matrices[pic]) for pic in doc_pics}
        if not to_analyze:
            print(f"No data: {doc_id}")
        checkboxes_states = analyze_checkboxes(to_analyze)
        return {
            pic: ReviewData(student=self.get_student(pic, matrices[pic]), checkboxes=checkboxes_states[pic])
            for pic in doc_pics
        }

    def load_info(self, doc_id: DocumentId) -> dict[Picture, ReviewData] | None:
        doc_students = self.load_student(doc_id)
        doc_cbx_states = self.load_checkboxes_state(doc_id)
        if doc_students is None or doc_cbx_states is None:
            return None
        assert len(doc_students) == len(doc_cbx_states)
        return {
            pic: ReviewData(student=doc_students[pic], checkboxes=doc_cbx_states[pic]) for pic in doc_students
        }

    def save_info(self, doc_id: DocumentId) -> None:
        self.save_checkboxes_state(doc_id)
        self.save_student(doc_id)

    # -------------------
    #     Students
    # ===================

    @property
    def students(self) -> dict[DocumentId, dict[Picture, Student]]:
        return {
            doc_id: {pic: review.student for pic, review in doc_info.items()}
            for doc_id, doc_info in self.info.items()
        }

    @property
    def checkboxes_state(self) -> dict[DocumentId, dict[Picture, dict[CbxRef, DetectionStatus]]]:
        return {
            doc_id: {pic: review.checkboxes for pic, review in doc_info.items()}
            for doc_id, doc_info in self.info.items()
        }

    def get_student_identification_table_position(self, pic: Picture) -> Pixel:
        """Get the position of the table where students check boxes to indicate their identifier."""
        return pic.data.xy2ij(*self.config.id_table_pos)

    def get_student(self, pic: Picture, matrix: ndarray) -> Student | None:
        """
        Recover the student information from the given picture.

        Return `None` if the document contains no such information.
        Note that the student name or identifier may be incorrect,
        since no verification occurs at this stage.
        """
        if pic.data.page != 1:
            return None
        pos = self.get_student_identification_table_position(pic)
        cfg = self.config
        return read_student_id_and_name(
            matrix, cfg.students_ids, pos, cfg.id_format, pic.data.calibration_data.f_cell_size
        )

    @staticmethod
    def _encode_student(student: Student) -> str:
        return f"{student.name}\n{student.id}\n"

    @staticmethod
    def _decode_student(file_content: str) -> Student:
        try:
            student_name, student_id = file_content.strip().split("\n")
            return Student(name=StudentName(student_name), id=StudentId(student_id))
        except (ValueError, AttributeError):
            raise InvalidFormat(f"Incorrect file content: {file_content!r}")

    def save_student(self, doc_id: DocumentId) -> None:
        for pic, student in self.students[doc_id].items():
            if student is not None:
                (folder := pic.dir / "students").mkdir(exist_ok=True)
                (folder / str(pic.num)).write_text(self._encode_student(student), encoding="utf8")

    def load_student(self, doc_id: DocumentId) -> dict[Picture, Student] | None:
        try:
            return {
                pic: self._decode_student((pic.dir / f"students/{pic.num}").read_text(encoding="utf8"))
                for pic in self.data_handler.get_document_pictures(doc_id)
            }
        except (OSError, InvalidFormat):
            return None

    # -------------------
    #     Checkboxes
    # ===================

    def get_checkboxes_positions(self, pic: Picture) -> CheckboxesPositions:
        """Retrieve the checkboxes positions in the pixel's matrix of the picture `pic`."""
        try:
            # The page may contain no question, so return an empty dict by default.
            boxes = self.config.boxes[pic.data.doc_id].get(pic.data.page, {})
        except KeyError:
            print(f"ERROR: doc id:{pic.data.doc_id}, doc page: {pic.data.page}")
            raise
        return {q_a: pic.data.xy2ij(*xy) for q_a, xy in boxes.items()}

    def get_checkboxes(self, pic: Picture, matrix: ndarray) -> dict[CbxRef, ndarray]:
        """Retrieve all the arrays representing the checkbox content for the picture `pic`."""
        cbx_content: dict[CbxRef, ndarray] = {}
        positions = self.get_checkboxes_positions(pic)
        cell_size = pic.data.calibration_data.cell_size
        for (q, a), (i, j) in positions.items():
            i, j = adjust_checkbox(matrix, i, j, cell_size)
            cbx_content[(q, a)] = matrix[i : i + cell_size, j : j + cell_size]
        return cbx_content

    @staticmethod
    def _encode_state(q_a: CbxRef, status: DetectionStatus) -> str:
        q, a = q_a
        return f"{q}, {a}: {status}"

    @staticmethod
    def _decode_state(line: str) -> tuple[CbxRef, DetectionStatus]:
        try:
            q_a, status = line.split(":")
            q, a = q_a.split(",")
            return (OriginalQuestionNumber(int(q)), OriginalAnswerNumber(int(a))), getattr(
                DetectionStatus, status
            )
        except (ValueError, AttributeError):
            raise InvalidFormat(f"Incorrect line: {line!r}")

    def _read_cbx_state_file(self, path) -> dict[CbxRef, DetectionStatus]:
        """Read the content of a checkboxes state file.

        May raise:
            - an OSError variant if the file is missing or unreadable.
            - an InvalidFormat if the file format is incorrect.
        """
        pic_cbx_status: dict[CbxRef, DetectionStatus] = {}
        for line in path.open("r", encoding="utf8"):
            q_a, status = self._decode_state(line)
            pic_cbx_status[q_a] = status
        return pic_cbx_status

    def save_checkboxes_state(self, doc_id: DocumentId) -> None:
        """Save to disk the checkboxes states for all the pictures associated with the given document id."""
        for pic, pic_cbx_state in self.checkboxes_state[doc_id].items():
            (folder := pic.dir / "checkboxes").mkdir(exist_ok=True)
            lines = (self._encode_state(q_a, status) for q_a, status in pic_cbx_state.items())
            (folder / str(pic.num)).write_text("\n".join(lines) + "\n", encoding="utf8")

    def load_checkboxes_state(
        self, doc_id: DocumentId
    ) -> dict[Picture, dict[CbxRef, DetectionStatus]] | None:
        """Load from disk the checkboxes states for all the pictures associated with the given document id."""
        doc_cbx_states: dict[Picture, dict[CbxRef, DetectionStatus]] = {}
        for page, page_pics in self.data_handler.index[doc_id].items():
            for pic in page_pics:
                try:
                    cbx_state_file = pic.dir / f"checkboxes/{pic.num}"
                    # Read the file and import its data.
                    result = self._read_cbx_state_file(cbx_state_file)
                    # Now, we should verify that the (<question_num>, <answer_num>) keys
                    # are the expected one. (Unexpected or missing keys are unlikely,
                    # yet maybe the disk is corrupted?)
                    expected = set(self.data_handler.config.boxes[doc_id][page])
                    if set(result) == expected:
                        doc_cbx_states[pic] = result
                    else:
                        # Missing (or incorrect) data!
                        return None
                except (InvalidFormat, OSError):
                    # The data was not found on disk or the data are invalid.
                    return None
        return doc_cbx_states
