from pathlib import Path

from PIL import Image
from numpy import array, amin, amax, ndarray  # , percentile, clip

from .color import Color
from .document_data import PicData, Page
from .types_declaration import (
    CalibrationError,
    Pixel,
    Shape,
    Rectangle,
)
from .calibration import calibrate
from .square_detection import (
    test_square_color,
    find_black_square,
    eval_square_color,
    adjust_checkbox,
)
from .tools import round
from .image_viewer import ImageViewer
from ..parameters import (
    SQUARE_SIZE_IN_CM,
    CELL_SIZE_IN_CM,
)
from ..tools.config_parser import (
    real2apparent,
    Configuration,
    StudentIdFormat,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    DocumentId,
    StudentName,
    StudentId,
)
from ..tools.io_tools import print_info, print_warning


# CornersPositions = dict[Corner, Pixel]


# TODO: calibrate grayscale too?
# At the bottom of the page, display 5 squares:
# Black - Gray - Light gray - White - Light gray - Gray - Black


# class PicData(TypedDict):
#     pages: dict
#     name: str
#     student_id: str
#     answered: dict
#     score: int
#     score_per_question: dict
#     pic_path: str


# def store_as_WEBP(m):
#    "Convert matrix to bytes using WEBP compression."
#    buffer = io.BytesIO()
#    im = Image.fromarray((255*m).astype(int8))
#    im.save(buffer, format="WEBP")
#    buffer.seek(0)
#    return buffer.read()
#
# def load_WEBP(b):
#    "Load WEBP image (bytes) and return corresponding matrix."
#    buffer = io.BytesIO(b)
#    im = Image.open(buffer)
#    return array(im)/255
#
# def load_as_matrix(pic_path: str):
#     return array(Image.open(pic_path).convert("L")) / 255
#
# def uncompress_array(buffer):
#    im = Image.open(buffer)
#    return array(im)/255


def read_doc_id_and_page(
    m: ndarray, pos: Pixel, f_square_size: float, debug_info: list[Shape]
) -> tuple[DocumentId, Page]:
    """Read the document ID and the page number.

    The document ID is encoded using a homemade barcode.
    This code is made of a band of 16 black or white squares.
    (Note that the first one is always black and is only used to detect the band).
    Example: ■■□■□■□■■□□□■□□■ = 0b100100011010101 =  21897
    It allows for 2**15 = 32 768 different values.
    """
    square_size = round(f_square_size)
    i, j = pos

    doc_id = 0

    # Test the color of the 15 following squares, and interpret it as a binary number.
    for k in range(24):
        j_ = round(j + (k + 1) * f_square_size)
        if test_square_color(m, i, j_, square_size, proportion=0.5, gray_level=0.5):
            doc_id += 2**k
        debug_info.append(Rectangle((i, j_), square_size, color=(Color.red if k % 2 else Color.blue)))

    # Nota: If necessary (although this is highly unlikely !), one may extend protocol
    # by adding a second band (or more !), starting with a black square.
    # This function will test if a black square is present below the first one ;
    # if so, the second band will be joined with the first
    # (allowing 2**30 = 1073741824 different values), and so on.

    page = doc_id % 256
    print("Page read: %s" % page)
    doc_id = doc_id // 256
    print("Test ID read: %s" % doc_id)

    return DocumentId(doc_id), Page(page)


def read_student_id_and_name(
    m: ndarray,
    students_ids: dict[StudentId, StudentName],
    pos: Pixel,
    id_format: StudentIdFormat,
    f_cell_size: float,
    debug_info: list[Shape],
) -> tuple[StudentId, StudentName]:
    student_id = ""
    student_name = ""
    cell_size = round(f_cell_size)
    half_cell = round(f_cell_size / 2)
    id_length, max_digits, digits = id_format
    # ~ height = id_length*cell_size
    i0, j0 = pos
    #            color2debug(m, (i0, j0), (i0 + cell_size, j0 + cell_size), color=(0,255,0))
    # Scan grid row by row. For each row, the darker cell is retrieved,
    # and the associated character is appended to the ID.
    all_id_are_of_the_same_length = len(set(len(id_) for id_ in students_ids)) == 1
    ev = eval_square_color
    for n in range(id_length):
        # Top of the row.
        i = round(i0 + n * f_cell_size)
        black_cells = []
        # If a cell is black enough, a couple (indicator_of_blackness, digit)
        # will be appended to the list `cells`.
        # After scanning the whole row, we will assume that the blackest
        # cell of the row will be the one checked by the student,
        # as long as there is enough difference between the blackest
        # and the second blackest.
        digits_for_nth_character = sorted(digits[n])
        if all_id_are_of_the_same_length and len(digits_for_nth_character) == 1:
            # No need to read, there is no choice for this character !
            student_id += digits_for_nth_character.pop()
            continue
        for k, d in enumerate(digits_for_nth_character):
            # Left ot the cell.
            j = round(j0 + (k + 1) * f_cell_size)

            is_black_enough = test_square_color(
                m, i, j, cell_size, proportion=0.3, gray_level=0.85
            ) or test_square_color(m, i, j, cell_size, proportion=0.5, gray_level=0.9)

            if is_black_enough:
                # To test the blackness, we exclude the top left corner,
                # which contain the cell number and may alter the result.
                # So, we divide the cell in four squares, and calculate
                # the mean blackness of the bottom left, bottom right
                # and top right squares (avoiding the top left one).
                square_blackness = (
                    ev(m, i, j + half_cell, half_cell)
                    + ev(m, i + half_cell, j, half_cell)
                    + ev(m, i + half_cell, j + half_cell, half_cell)
                ) / 3
                black_cells.append((square_blackness, d))
                print("Found:", d, square_blackness)

            debug_info.append(
                Rectangle((i, j), cell_size, color=(Color.cyan if is_black_enough else Color.red))
            )

        if black_cells:
            black_cells.sort(reverse=True)
            print(black_cells)
            # Test if there is enough difference between the blackest
            # and the second blackest (minimal difference was set empirically).
            if len(black_cells) == 1 or black_cells[0][0] - black_cells[1][0] > 0.2:
                # The blackest one is chosen:
                digit = black_cells[0][1]
                student_id += digit
    if student_id in students_ids:
        print("Student ID:", student_id)
        student_name = students_ids[StudentId(student_id)]
    else:
        print(f"ID list: {students_ids!r}")
        print_warning(f"Invalid student id {student_id!r}!")

    return StudentId(student_id), StudentName(student_name)


def read_student_name(m: ndarray, students: list[StudentName], top: int, f_square_size: float) -> StudentName:
    # TODO: rewrite this function.
    # Use .pos file to retrieve exact position of first square
    # (just like in next section),
    # instead of scanning a large area to detect first black square.
    # Exclude the codebar and top squares from the search area.
    # If rotation correction was well done, we should have i1 ≃ i2 ≃ i3.
    # Anyway, it's safer to take the max of them.
    student_name = StudentName("")
    n_students = len(students)
    square_size = round(f_square_size)
    vpos = top + 2 * square_size
    search_area = m[vpos : vpos + 4 * square_size, :]
    i, j0 = find_black_square(search_area, size=square_size, error=0.3, mode="column").__next__()
    # ~ color2debug((vpos + i, j0), (vpos + i + square_size, j0 + square_size), color=(0,255,0))
    vpos += i + square_size
    checked_squares = []
    for k in range(1, n_students + 1):
        j = round(j0 + 2 * k * f_square_size)
        checked_squares.append(test_square_color(search_area, i, j, square_size))
        # ~ if k > 15:
        # ~ print(checked_squares)
        # ~ color2debug((vpos + i, j), (vpos + i + square_size, j + square_size))
    n = checked_squares.count(True)
    if n == 0:
        print("Warning: no student name !")
    elif n > 1:
        print("Warning: several students names !")
        for i, b in enumerate(checked_squares):
            if b:
                print(" - ", students[n_students - i - 1])
    else:
        student_number = n_students - checked_squares.index(True) - 1
        student_name = students[student_number]
    return student_name


def adjust_contrast(m: ndarray, filename: str, debug=False) -> ndarray:
    """Increase contrast if needed.

    The lightest pixel must be white, the darkest must be black."""
    min_val = amin(m)
    max_val = amax(m)
    if debug:
        print("Trying to maximize contrast..")
        print(f"Old range: {min_val} - {max_val}")
    if min_val > 0 or max_val < 255 and max_val - min_val > 0.2:
        m = (m - min_val) / (max_val - min_val)
        if debug:
            print(f"New range: {amin(m)} - {amax(m)}")
            # ImageViewer(m).display()
    else:
        print_warning(f"Not enough contrast in picture {filename!r}!")
    return m


def scan_picture(filename: str | Path, config: Configuration, debug=False) -> tuple[PicData, ndarray]:
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
