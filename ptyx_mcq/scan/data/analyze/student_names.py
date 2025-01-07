from numpy import ndarray
from ptyx.shell import print_warning

from ptyx_mcq.scan.data.students import Student
from ptyx_mcq.scan.picture_analyze.identify_doc import DebugInfo
from ptyx_mcq.scan.picture_analyze.square_detection import eval_square_color, test_square_color
from ptyx_mcq.scan.picture_analyze.types_declaration import Pixel, Rectangle, Row, Col
from ptyx_mcq.tools.colors import Color
from ptyx_mcq.tools.config_parser import StudentId, StudentName, StudentIdFormat


def read_student_id_and_name(
    m: ndarray,
    students_ids: dict[StudentId, StudentName],
    pos: Pixel,
    id_format: StudentIdFormat,
    f_cell_size: float,
    debug_info: DebugInfo = None,
) -> Student:
    if debug_info is None:
        debug_info = []
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
        i = Row(round(i0 + n * f_cell_size))
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
            j = Col(round(j0 + (k + 1) * f_cell_size))

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
                    ev(m, i, Col(j + half_cell), half_cell)
                    + ev(m, Row(i + half_cell), j, half_cell)
                    + ev(m, Row(i + half_cell), Col(j + half_cell), half_cell)
                ) / 3
                black_cells.append((square_blackness, d))
                # print("Found:", d, square_blackness)

            debug_info.append(
                Rectangle((i, j), cell_size, color=(Color.cyan if is_black_enough else Color.red))
            )

        if black_cells:
            black_cells.sort(reverse=True)
            # print(black_cells)
            # Test if there is enough difference between the blackest
            # and the second blackest (minimal difference was set empirically).
            if len(black_cells) == 1 or black_cells[0][0] - black_cells[1][0] > 0.2:
                # The blackest one is chosen:
                digit = black_cells[0][1]
                student_id += digit
                # print(student_id)
    if student_id in students_ids:
        print("Student ID:", student_id)
        student_name = students_ids[StudentId(student_id)]
    else:
        print(f"ID list: {students_ids!r}")
        print_warning(f"Invalid student id {student_id!r}!")

    return Student(id=StudentId(student_id), name=StudentName(student_name))


# def read_student_name(m: ndarray, students: list[StudentName], top: int, f_square_size: float) -> StudentName:
#     # TODO: rewrite this function.
#     # Use .pos file to retrieve exact position of first square
#     # (just like in next section),
#     # instead of scanning a large area to detect first black square.
#     # Exclude the codebar and top squares from the search area.
#     # If rotation correction was well done, we should have i1 ≃ i2 ≃ i3.
#     # Anyway, it's safer to take the max of them.
#     student_name = StudentName("")
#     n_students = len(students)
#     square_size = round(f_square_size)
#     vpos = top + 2 * square_size
#     search_area = m[vpos : vpos + 4 * square_size, :]
#     i, j0 = find_black_square(search_area, size=square_size, error=0.3, mode="column").__next__()
#     # ~ color2debug((vpos + i, j0), (vpos + i + square_size, j0 + square_size), color=(0,255,0))
#     vpos += i + square_size
#     checked_squares = []
#     for k in range(1, n_students + 1):
#         j = round(j0 + 2 * k * f_square_size)
#         checked_squares.append(test_square_color(search_area, i, j, square_size))
#         # ~ if k > 15:
#         # ~ print(checked_squares)
#         # ~ color2debug((vpos + i, j), (vpos + i + square_size, j + square_size))
#     n = checked_squares.count(True)
#     if n == 0:
#         print("Warning: no student name !")
#     elif n > 1:
#         print("Warning: several students names !")
#         for i, b in enumerate(checked_squares):
#             if b:
#                 print(" - ", students[n_students - i - 1])
#     else:
#         student_number = n_students - checked_squares.index(True) - 1
#         student_name = students[student_number]
#     return student_name
