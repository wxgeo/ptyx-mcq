from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from numpy import array, ndarray  # , percentile, clip

from ptyx.shell import print_info, print_warning

from ptyx_mcq.scan.picture_analyze.identify_doc import IdentificationData
from ptyx_mcq.tools.colors import Color
from ptyx_mcq.scan.data_gestion.document_data import PicData
from ptyx_mcq.scan.picture_analyze.types_declaration import (
    CalibrationError,
    Pixel,
    Shape,
    Rectangle,
)
from ptyx_mcq.scan.picture_analyze.calibration import calibrate, adjust_contrast, CalibrationData
from ptyx_mcq.scan.picture_analyze.square_detection import (
    test_square_color,
    find_black_square,
    eval_square_color,
    adjust_checkbox,
)
from ptyx_mcq.tools.math import round
from ptyx_mcq.scan.picture_analyze.image_viewer import ImageViewer
from ptyx_mcq.parameters import (
    SQUARE_SIZE_IN_CM,
    CELL_SIZE_IN_CM,
)
from ptyx_mcq.tools.config_parser import (
    real2apparent,
    Configuration,
    StudentIdFormat,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    DocumentId,
    StudentName,
    StudentId,
    ApparentQuestionNumber,
    Page,
)


# TODO: calibrate grayscale too?
# At the bottom of the page, display 5 squares:
# Black - Gray - Light gray - White - Light gray - Gray - Black


def scan_picture(pic_path: Path, m: ndarray, config: Configuration, debug=False) -> IdentificationData:
    """Scan picture and return page identifier and list of answers for each question.

    - `pic_path` is a path pointing to a webp file.
    - `m` is the array corresponding to the image.
    - `config` is either a path pointing to a config file, or a dictionary
      containing the configuration (generated from a config file).
    - `debug` is set to `True`, the picture will be displayed
      with the interpretation done by this algorithm: checkboxes considered
      blackened by student will be shown in cyan, and all the other ones will be
      shown in red. If it is set to `None` (default), the user will be asked
      for manual verification only if recommended. If it is set to `False`,
      user will never be bothered.

    Return an `IdentificationData` instance.
    """

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
    debug_info: list[Shape] = []
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
