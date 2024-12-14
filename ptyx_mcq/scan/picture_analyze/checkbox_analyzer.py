from functools import partial
from pathlib import Path

from numpy import ndarray, array
from PIL import Image

from ptyx.shell import print_warning, print_info

from ptyx_mcq.parameters import SQUARE_SIZE_IN_CM, CELL_SIZE_IN_CM
from ptyx_mcq.scan.data.structures import DetectionStatus, PicData
from ptyx_mcq.scan.picture_analyze.calibration import calibrate, adjust_contrast
from ptyx_mcq.scan.picture_analyze.identify_doc import DebugInfo, read_doc_id_and_page
from ptyx_mcq.scan.picture_analyze.image_viewer import ImageViewer
from ptyx_mcq.scan.picture_analyze.square_detection import (
    test_square_color,
    eval_square_color,
    find_black_square,
    adjust_checkbox,
)
from ptyx_mcq.scan.picture_analyze.types_declaration import Pixel, Rectangle, CalibrationError
from ptyx_mcq.tools.colors import Color
from ptyx_mcq.tools.config_parser import (
    OriginalAnswerNumber,
    OriginalQuestionNumber,
    StudentId,
    StudentName,
    StudentIdFormat,
    Configuration,
    real2apparent,
)


def eval_checkbox_color(checkbox: ndarray, margin: int = 0) -> float:
    """Return an indicator of blackness, which is a float in range (0, 1).
    The bigger the float returned, the darker the square.

    This indicator is useful to compare several squares, and find the blacker one.
    Note that the core of the square is considered the more important part to assert
    blackness.
    """
    height, width = checkbox.shape
    assert width == height, (width, height)
    if width <= 2 * margin:
        raise ValueError("Square too small for current margins !")
    # Warning: pixels outside the sheet shouldn't be considered black !
    # Since we're doing a sum, 0 should represent white and 1 black,
    # so as if a part of the square is outside the sheet, it is considered
    # white, not black ! This explains the `1 - m[...]` below.
    square = 1 - checkbox[margin : width - margin, margin : width - margin]
    return square.sum() / (width - margin) ** 2


def review_picture(filename: str | Path, config: Configuration, debug=False) -> tuple[PicData, ndarray]:
    """Scan picture and return page identifier and list of answers for each question.

    - `filename` is a path pointing to a PNG file.
    - `config` is either a path pointing to a config file, or a dictionary
      containing the configuration (generated from a config file).
    - `manual_verification` is set to `True`, the picture will be displayed
      with the interpretation done by this algorithm: checkboxes considered
      blackened by student will be shown in cyan, and all the other ones will be
      shown in red. If it is set to `None` (default), the user will be asked
      for manual verification only if recommended. If it is set to `False`,
      user will never be bothered.

    Return a tuple:
        * a `PicData` instance,
        * an array representing the current picture.
    """
    filename = str(filename)
    # Convert to grayscale picture.
    pic: Image.Image = Image.open(filename).convert("L")
    m: ndarray = adjust_contrast(array(pic) / 255.0, filename=filename, debug=debug)

    # ------------------------------------------------------------------
    #                          CONFIGURATION
    # ------------------------------------------------------------------
    # Load configuration.
    students = config.students_list
    n_students = len(students)
    students_ids = config.students_ids

    # ------------------------------------------------------------------
    #                          CALIBRATION
    # ------------------------------------------------------------------

    try:
        m, h_pixels_per_mm, v_pixels_per_mm, (TOP, LEFT), (i, j) = calibrate(pic, m, debug=debug)
    except CalibrationError as e:
        if debug:
            ImageViewer(array=e.matrix, *e.details).display()
        raise e
    pixels_per_mm = (h_pixels_per_mm + 1.5 * v_pixels_per_mm) / 2.5

    # We should now have an accurate value for square size.
    f_square_size = SQUARE_SIZE_IN_CM * pixels_per_mm * 10
    square_size = round(f_square_size)
    print("Square size final value (pixels): %s (%s)" % (square_size, f_square_size))

    f_cell_size = CELL_SIZE_IN_CM * pixels_per_mm * 10
    cell_size = round(f_cell_size)

    # Henceforth, we can convert LaTeX position to pixel with a good precision.
    def xy2ij(x, y):
        """Convert (x, y) position (mm) to pixels (i,j).

        (x, y) is the position from the bottom left of the page in mm,
        as given by LaTeX.
        (i, j) is the position in pixels, where i is the line and j the
        column, starting from the top left of the image.
        """
        # Top left square is printed at 1 cm from the left and the top of the sheet.
        # 29.7 cm - 1 cm = 28.7 cm (A4 sheet format = 21 cm x 29.7 cm)
        return round((287 - y) * v_pixels_per_mm + TOP), round((x - 10) * h_pixels_per_mm + LEFT)

    # ------------------------------------------------------------------
    #                      READ IDENTIFIER
    # ------------------------------------------------------------------
    debug_info: DebugInfo = []
    doc_id, page = read_doc_id_and_page(m, (i, j), f_square_size, debug_info)

    # ------------------------------------------------------------------
    #                  IDENTIFY STUDENT (OPTIONAL)
    # ------------------------------------------------------------------

    student_name = StudentName("")
    student_id = StudentId("")

    if page == 1:
        # Read student name directly
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~

        if n_students:
            student_name = read_student_name(m, students, TOP, f_square_size)

        # Read student id, then find name
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        #
        elif students_ids:
            assert config.id_table_pos is not None
            assert config.id_format is not None
            student_id, student_name = read_student_id_and_name(
                m, students_ids, xy2ij(*config.id_table_pos), config.id_format, f_cell_size, debug_info
            )

        else:
            print_info("No students list.")

        print("Student name:", student_name)

    if debug:
        ImageViewer(array=m, *debug_info).display()

    # ------------------------------------------------------------------
    #                      READ ANSWERS
    # ------------------------------------------------------------------

    pic_data = PicData(
        doc_id=doc_id,  # ID of the test
        page=page,  # page number
        name=student_name,
        student_id=student_id,
        # answers checked by the student for each question:
        answered={},
        # Position of each checkbox in the page:
        positions={},
        cell_size=cell_size,
        # Translation table ({question number before shuffling: after shuffling})
        questions_nums_conversion={},
        detection_status={},
        revision_status={},
        pic_path="",
    )

    try:
        boxes = config.boxes[doc_id][page]
    except KeyError:
        print_warning(f"ID {doc_id!r} - page {page!r} not found in config file.")
        print_warning("This page doesn't seem to belong to the current document.")
        print_warning("Maybe some unrelated sheet was scanned by mistake?")
        return pic_data, m

    # ordering = config['ordering'][doc_id]
    mode = config.mode
    #    correct_answers = config['correct_answers']

    # Detect the answers.
    print("\n=== Reading answers ===")
    print(f"Mode of evaluation: {mode['default']!r}.")
    print("Rating:")
    print(f"• {config.correct['default']} for correctly answered question,")
    print(f"• {config.incorrect['default']} for wrongly answered question,")
    print(f"• {config.skipped['default']} for unanswered question.")
    print("Scanning...\n")

    # Using the config file to obtain correct answers list allows some easy customization
    # after the test was generated (this is useful if some tests questions were flawed).

    # Store the picture of the checkbox
    # boxes_content = {}

    for key, pos in boxes.items():
        i, j = xy2ij(*pos)
        i, j = adjust_checkbox(m, i, j, cell_size)
        # `q` and `a` are real questions and answers numbers, that is,
        # questions and answers numbers before shuffling.
        q_str, a_str = key[1:].split("-")
        q = OriginalQuestionNumber(int(q_str))
        a = OriginalAnswerNumber(int(a_str))
        # boxes_content[(q, a)] = m[i : i + cell_size, j : j + cell_size]
        pic_data.positions[(q, a)] = (i, j)
        # `q0` and `a0` keep track of apparent question and answers numbers,
        # which will be used on output to make debugging easier.
        q0, a0 = real2apparent(q, a, config, doc_id)
        pic_data.questions_nums_conversion[q] = q0

    # Keep matrix separate from other output data, as it is often not wanted
    # when debugging.

    return pic_data, m


# class CheckboxesExtractor:
#     def __init__(
#         self, config: Configuration, index: dict[DocumentId, dict[Page, set[Path]]], data: PdfData
#     ):
#         self.config = config
#         self.index = index
#         self.data = data
#
#     def get_checkbox(
#         self, doc_id: DocumentId, page: Page, q: OriginalQuestionNumber, a: OriginalAnswerNumber
#     ) -> ndarray:
#         boxes = self.config.boxes[doc_id][page]
