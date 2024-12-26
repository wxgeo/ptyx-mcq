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


class PictureAnalyzer:
    """
    Analyze a picture to extract student information and the state of checkboxes.

    Both operations are performed in a single pass to avoid opening the same picture twice.
    This optimization is necessary because pictures are stored on disk, not in memory,
    to prevent memory saturation.
    """

    def __init__(self, data_handler: "ScanData"):
        self.data_handler: "ScanData" = data_handler

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
        # Step 1: evaluate checkboxes state if needed.
        matrices: dict[str:ndarray] = {}
        pictures = doc.pictures
        if any(pic.checkboxes is None for pic in pictures):
            # No corresponding data on the disk, generate the data, and write it on the disk.
            print(f"Analyzing checkboxes in document: {doc.doc_id}")
            # Put pictures arrays in cache (there are not so much of them for a single document),
            # since they will be used both to analyze the answers and to read the student id.
            matrices = {pic.short_path: pic.as_matrix() for pic in pictures}
            cbx = [self.get_checkboxes(pic, matrices[pic.short_path]) for pic in pictures]
            # Analyze each checkbox.
            # All the checkboxes of the same document must be inspected together
            # to improve the checkboxes' states review, since a given student will probably
            # check all its document boxes in a consistent way.
            for pic, cbx_states in zip(pictures, analyze_checkboxes(cbx)):
                pic.checkboxes = cbx_states

        # Step 2: retrieve student name and ID if needed.
        for pic in pictures:
            if pic.page_num == 1:
                if pic.student is None:
                    pic.student = self.get_student(pic, matrices.get(pic.short_path, pic.as_matrix()))
                elif pic.student.name == "":
                    # The ID have been read in a previous pass, but didn't match any known student at the time.
                    # In the while, the students name to ID mapping may have been updated (using `mcq fix` for example).
                    # So, let's try again to find the name corresponding to this ID.
                    name = self.config.students_ids.get(pic.student.id, StudentName(""))
                    if name != "":
                        pic.student = Student(name=name, id=pic.student.id)

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

    # -------------------
    #     Checkboxes
    # ===================

    def get_checkboxes(self, pic: Picture, matrix: ndarray = None) -> Checkboxes:
        """
        Retrieve all the arrays representing the checkbox content for the picture `pic`.

        Since reading the matrix from the corresponding webp file is quite slow,
        a cached matrix may be passed as argument; if missing, the matrix will be loaded from disk.
        """
        if matrix is None:
            matrix = pic.as_matrix()
        cbx_content = Checkboxes()
        positions = pic.get_checkboxes_positions()
        cell_size = pic.calibration_data.cell_size
        for (q, a), (i, j) in positions.items():
            i, j = adjust_checkbox(matrix, i, j, cell_size)
            cbx_content[(q, a)] = matrix[i : i + cell_size, j : j + cell_size]
        return cbx_content
