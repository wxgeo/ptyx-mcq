from functools import partial
from math import degrees, atan, hypot
from pathlib import Path

from PIL import Image
from numpy import array, flipud, fliplr, dot, amin, amax, zeros, ndarray  # , percentile, clip

from .color import Color
from .document_data import PicData, Page, DetectionStatus
from .square_detection import (
    test_square_color,
    find_black_square,
    eval_square_color,
    adjust_checkbox,
    Pixel,
)
from .tools import round
from .visual_debugging import ArrayViewer
from ..parameters import (
    SQUARE_SIZE_IN_CM,
    CELL_SIZE_IN_CM,
    CALIBRATION_SQUARE_POSITION,
    CALIBRATION_SQUARE_SIZE,
)
from ..tools.config_parser import (
    real2apparent,
    is_answer_correct,
    Configuration,
    StudentIdFormat,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    DocumentId,
    StudentName,
    StudentId,
)
from ..tools.io_tools import ANSI_RESET, ANSI_YELLOW, ANSI_CYAN, ANSI_GRAY

CORNERS = frozenset(("tl", "tr", "bl", "br"))
CORNER_NAMES = {"tl": "top-left", "tr": "top-right", "bl": "bottom-left", "br": "bottom-right"}

CornersPositions = dict[str, Pixel]

# TODO: calibrate grayscale too.
# At the bottom of the page, display 5 squares:
# Black - Gray - Light gray - White - Light gray - Gray - Black


# class PicData(TypedDict):
#     pages: dict
#     name: str
#     student_ID: str
#     answered: dict
#     score: int
#     score_per_question: dict
#     pic_path: str


class CalibrationError(RuntimeError):
    """Error raised if calibration failed."""


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


def transform(pic: Image.Image, transformation: str, *args, **kw) -> tuple[Image.Image, ndarray]:
    """Return a transformed version of `pic` and its matrix."""
    # cf. http://stackoverflow.com/questions/5252170/
    # specify-image-filling-color-when-rotating-in-python-with-pil-and-setting-expand
    rgba = pic.convert("RGBA")
    rgba = getattr(rgba, transformation)(*args, **kw)
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    out = Image.composite(rgba, white, rgba)
    pic = out.convert(pic.mode)
    # noinspection PyTypeChecker
    return pic, array(pic) / 255.0


def find_black_cell(grid, ll: int, LL: int, detection_level: float) -> tuple[int, int]:
    for k in range(LL + ll):
        # j < ll <=> k - i < ll <=> k - ll < i <=> i >= k - ll + 1
        for i in range(max(0, k - ll + 1), min(k + 1, LL)):
            j = k - i
            #            if grid[i, j] < 100:
            #                i0 = half*i   # Add `half` and `m` to the function parameters
            #                j0 = half*j   # before running this code.
            #                color2debug(m, (i0, j0), (i0 + half, j0 + half))
            if grid[i, j] < detection_level:
                return i, j
    raise LookupError("Corner square not found.")


def find_corner_square(
    m: ndarray,
    size: int,
    corner: str,
    *,
    max_whiteness: float = 0.55,
    tolerance: float = 0.2,
    viewer: ArrayViewer,
) -> tuple[int, int]:
    """Find the calibration black square of the given corner.

    The idea of the algorithm is the following:
        1. Convert the picture into a grid of big pixels of side half the
           searched square side.
        2. Search for the first big pixel dark enough, starting from the corner.

    Parameters:
        - `size` is the size in pixels of the square.
        - `corner` is the name of the corner (for example, "tb" for top-bottom).
        - `max_whiteness` is a safeguard value, to avoid false positives (i.e. detecting
           a black square in a white sheet).
        - `tolerance` is the maximal relative difference of whiteness between the darkest big pixel of
           the grid and the found one.
    """
    height, width = m.shape
    V, H = tuple(corner)  # for mypy support
    # First, flip the matrix if needed, so that the corner considered
    # is now the top left corner.
    if V == "b":
        m = flipud(m)
    if H == "r":
        m = fliplr(m)
    area: ndarray = m[: height // 4, : width // 4]
    #    color2debug(m, (0, 0), (L//4, l//4), color=Color.blue, display=False)

    # Then, split area into a mesh grid.
    # The mesh size is half the size of the searched square.
    half = size // 2
    LL = (height // 4) // half
    ll = (width // 4) // half
    grid = zeros((LL, ll))

    # For each mesh grid cell, we calculate the whiteness of the cell.
    # (Each pixel value varies from 0 (black) to 1 (white).)
    for i in range(LL):
        for j in range(ll):
            grid[i, j] = area[i * half : (i + 1) * half, j * half : (j + 1) * half].sum()

    # This is the darkest cell value.
    darkest = float(amin(grid))
    # We could directly collect the coordinates of this cell,
    # which are (grid.argmin()//ll, grid.argmin()%ll).
    # However, the search area is large, and we may detect as the
    # darkest cell one checkbox of the MCQ itself for example,
    # or the ID band.
    # Anyway, even if the core of the black square is not
    # the darkest cell, it should be almost as dark as the darkest.
    detection_level = darkest + tolerance * (half**2 - darkest)

    # Then, we will browse the mesh grid, starting from the top left corner,
    # following oblique lines (North-East->South-West), as follows:
    # 1  2  4  7
    # 3  5  8  11
    # 6  9  12 14
    # 10 13 15 16

    # We stop when we found a black cell.
    i, j = find_black_cell(grid, ll, LL, detection_level)

    # Now, we must adjust the position of the square.
    # First, let's adjust it vertically.
    # We have detected the core of the square.
    # The top part of the square (if any) is in the cell just above,
    # and the bottom part (if any) in the cell just below.
    if i == 0:
        i0 = 0
    elif i == LL - 1:
        i0 = half * i
    else:
        # t1 is the percentage of black pixels in the cell above, and t2
        # the percentage in the cell below.
        # We now have a good approximation of the percentage of the square
        # to be found in the upper cell and in the lower cell.
        # So, t2/(t1 + t2)*half is approximately the vertical position
        # of the square, starting from the top of the upper cell.
        t1 = grid[i - 1, j]
        t2 = grid[i + 1, j]
        if t1 + t2 == 0:
            raise NotImplementedError
        i0 = round((i - 1 + t2 / (t1 + t2)) * half)

    # Same procedure, but horizontally now.
    if j == 0:
        j0 = 0
    elif j == ll - 1:
        j0 = half * j
    else:
        t1 = grid[i, j - 1]
        t2 = grid[i, j + 1]
        if t1 + t2 == 0:
            raise NotImplementedError
        j0 = round((j - 1 + t2 / (t1 + t2)) * half)

    # Adjust line by line for more precision.
    # First, vertically.
    j1 = j0
    j2 = j0 + size
    shift_down = False
    while i0 < height // 4 - size and area[i0 + size, j1:j2].sum() < area[i0, j1:j2].sum():
        # shift one pixel down
        i0 += 1
        shift_down = True
    if not shift_down:
        while i0 > 0 and area[i0 - 1, j1:j2].sum() < area[i0 + size - 1, j1:j2].sum():
            # shift one pixel up
            i0 -= 1

    # Then, adjust horizontally.
    i1 = i0
    i2 = i0 + size
    shift_right = False
    while j0 < width // 4 - size and area[i1:i2, j0 + size].sum() < area[i1:i2, j0].sum():
        # shift one pixel right
        j0 += 1
        shift_right = True
    if not shift_right:
        while j0 > 0 and area[i1:i2, j0 - 1].sum() < area[i1:i2, j0 + size - 1].sum():
            # shift one pixel left
            j0 -= 1

    # Test the result. If the square is too dim, raise LookupError.
    whiteness_measure = m[i0 : i0 + size, j0 : j0 + size].sum() / size**2
    print(f"Corner square {corner} found...")
    #    color2debug(m, (i0, j0), (i0 + size, j0 + size))
    if whiteness_measure > max_whiteness:
        print(f"WARNING: Corner square {corner} not found " f"(not dark enough: {whiteness_measure}!)")
        viewer.add_square((i0, j0), size, color=Color.blue)
        raise LookupError(f"Corner square {corner} not found.")

    if V == "b":
        i0 = height - 1 - i0 - size
    if H == "r":
        j0 = width - 1 - j0 - size

    return i0, j0


def orthogonal(corner: str, positions: CornersPositions) -> bool:
    V = corner[0]  # Unpacking a string is disallowed for mypy!
    H = corner[1]
    corner1 = V + ("l" if H == "r" else "r")
    corner2 = ("t" if V == "b" else "b") + H
    i, j = positions[corner]
    i1, j1 = positions[corner1]
    i2, j2 = positions[corner2]
    v1 = i1 - i, j1 - j
    v2 = i2 - i, j2 - j
    cos_a = dot(v1, v2) / (hypot(*v1) * hypot(*v2))
    return abs(cos_a) < 0.06


def area_opposite_corners(positions: CornersPositions) -> tuple[Pixel, Pixel]:
    i1 = round((positions["tl"][0] + positions["tr"][0]) / 2)
    i2 = round((positions["bl"][0] + positions["br"][0]) / 2)
    j1 = round((positions["tl"][1] + positions["bl"][1]) / 2)
    j2 = round((positions["tr"][1] + positions["br"][1]) / 2)
    return (i1, j1), (i2, j2)


def detect_four_squares(
    m: ndarray,
    square_size: int,
    cm: float,
    *,
    debug=False,
) -> tuple[CornersPositions, Pixel, Pixel]:
    for tolerance in range(20, 50, 5):
        print(f"Searching for calibration corners ({tolerance=})...")
        try:
            return _detect_four_squares(
                m,
                square_size,
                cm,
                tolerance=tolerance / 100,
                debug=debug or tolerance > 40,
            )
        except CalibrationError as e:
            error = e
    else:
        # noinspection PyUnboundLocalVariable
        raise error


def _detect_four_squares(
    m: ndarray,
    square_size: int,
    cm: float,
    *,
    max_alignment_error_cm: float = 0.4,
    tolerance=0.2,
    debug=False,
) -> tuple[CornersPositions, Pixel, Pixel]:
    viewer = ArrayViewer(m)
    #    h = w = round(2*(1 + SQUARE_SIZE_IN_CM)*cm)
    # Make a mutable copy of frozenset CORNERS.
    corners = set(CORNERS)
    # `positions` is used to store the position (in pixels) of the calibration square of each corner.
    positions: CornersPositions = {}
    for corner in CORNERS:
        try:
            i, j = find_corner_square(m, square_size, corner, tolerance=tolerance, viewer=viewer)
            # ~ # We may have only detected a part of the square by restricting
            # ~ # the search area, so extend search by the size of the square.
            # ~ i, j = find_corner_square(m, square_size, corner, h + square_size,
            # ~ w + square_size, tolerance, whiteness)
            viewer.add_square((i, j), square_size)
            positions[corner] = i, j
            corners.remove(corner)
        except LookupError:
            pass

        # ~ if input(len(positions)) == 'd':
        # ~ color2debug(m)

    # If one calibration square is missing (a corner of the sheet is
    # folded for example), it will be generated from the others.

    #    color2debug(m)
    print(f"Corners detected: {len(positions)}")
    if len(positions) <= 2:
        viewer.display()
        raise CalibrationError("Only 2 squares found, calibration failed !")

    if len(positions) == 4:
        for V in "tb":
            h_shift = positions[f"{V}r"][0] - positions[f"{V}l"][0]
            if abs(h_shift) > max_alignment_error_cm * cm:
                print("Warning: Horizontal alignment problem in corners squares !")
                print(f"horizontal shift ({V}): {h_shift}")
        for H in "lr":
            v_shift = positions[f"b{H}"][1] - positions[f"t{H}"][1]
            if abs(v_shift) > max_alignment_error_cm * cm:
                print("Warning: Vertical alignment problem in corners squares !")
                print(f"vertical shift ({H}): {v_shift}")

    number_of_orthogonal_corners = 0
    # Try to detect false positives.
    if len(positions) == 4:
        # If only one corner is orthogonal, the opposite corner must be wrong.
        for corner in positions:
            if orthogonal(corner, positions):
                number_of_orthogonal_corners += 1
                orthogonal_corner = corner
        print(f"Number of orthogonal corners: {number_of_orthogonal_corners}")
        if number_of_orthogonal_corners == 1:
            # noinspection PyUnboundLocalVariable
            V, H = tuple(orthogonal_corner)  # (Unpacking a string is disallowed for mypy!)
            opposite_corner = ("t" if V == "b" else "b") + ("l" if H == "r" else "r")
            print(f"Removing {CORNER_NAMES[opposite_corner]} corner (not orthogonal !)")
            del positions[opposite_corner]

    if len(positions) == 4:
        # If there are 4 squares, and one is less dark than the others,
        # let's drop it and use only the 3 darkest.
        # (The 4th square will be generated again using the position of the 3 others).
        darkness = {}
        for corner, position in positions.items():
            darkness[corner] = eval_square_color(m, *position, square_size)

        lighter_corner = min(darkness, key=darkness.get)  # type: ignore
        if darkness[lighter_corner] < 0.4:
            print(
                f"Removing {CORNER_NAMES[lighter_corner]} corner "
                f"(too light: {darkness[lighter_corner]} !)"
            )
            del positions[lighter_corner]

    if len(positions) == 4:
        if number_of_orthogonal_corners <= 2:
            for i, j in positions.values():
                viewer.add_square((i, j), square_size)
            viewer.display()
            print("number_of_orthogonal_corners =", number_of_orthogonal_corners)
            raise CalibrationError("Something wrong with the corners !")

    for corner in CORNERS:
        if corner not in positions:
            print(
                f"Warning: {CORNER_NAMES[corner]} corner not found.\n"
                "Its position will be deduced from the 3 other corners."
            )
            V, H = tuple(corner)  # 'b' 'r'
            nV, nH = ("t" if V == "b" else "b"), ("l" if H == "r" else "r")
            # This is the opposite corner of the missing one.
            i0, j0 = positions[nV + nH]
            i1, j1 = positions[nV + H]
            i2, j2 = positions[V + nH]
            i = i2 + (i1 - i0)
            j = j2 + (j1 - j0)

            # Calculate the last corner (ABCD parallelogram <=> Vec{AB} = \Vec{DC})
            positions[corner] = (i, j)
            viewer.add_square((i, j), square_size, color=Color.cyan)

            # For example: positions['bl'] = positions['br'][0], positions['tl'][1]

    ij1, ij2 = area_opposite_corners(positions)

    if debug:
        viewer.add_area(ij1, ij2, color=Color.green)
        viewer.display()

    return positions, ij1, ij2


def find_document_id_band(
    m: ndarray, i: int, j1: int, j2: int, square_size: int, viewer: ArrayViewer
) -> Pixel:
    """Return the top left corner (coordinates in pixels) of the document ID band first square."""
    margin = square_size
    i1, i2 = i - margin, i + square_size + margin
    j1, j2 = j1 + 3 * square_size, j2 - 2 * square_size
    viewer.add_area((i1, j1), (i2, j2))
    search_area = m[i1:i2, j1:j2]
    i3, j3 = find_black_square(
        search_area, size=square_size, error=0.3, gray_level=0.5, mode="column", debug=False
    ).__next__()
    i3 += i1
    j3 += j1
    viewer.add_square((i3, j3), square_size)
    return i3, j3


def calibrate(pic: Image.Image, m: ndarray, debug=False) -> tuple[ndarray, float, float, Pixel, Pixel]:
    """Detect picture resolution and ensure correct orientation."""
    viewer = ArrayViewer(m)  # for debugging
    # Ensure that the picture orientation is portrait, not landscape.
    height, width = m.shape
    print(f"Picture dimensions : {height}px x {width}px.")

    if height < width:
        pic, m = transform(pic, "transpose", method=Image.ROTATE_90)
        height, width = m.shape

    assert width <= height

    # Calculate resolution (DPI and dots per cm).
    cm = m.shape[1] / 21
    # Unit conversion: 1 inch = 2.54 cm
    print(f"Detect pixels/cm: {cm} (dpi: {2.54*cm})")

    # Evaluate approximately squares size using image dpi.
    # Square size is equal to SQUARE_SIZE_IN_CM in theory, but this varies
    # in practice depending on printer and scanner parameters (margins...).
    square_size = round(SQUARE_SIZE_IN_CM * cm)
    calib_square = round(CALIBRATION_SQUARE_SIZE * cm)
    calib_shift_mm = 10 * (2 * CALIBRATION_SQUARE_POSITION + CALIBRATION_SQUARE_SIZE)

    # Detect the four big squares at the top left, top right, bottom left
    # and bottom right corners of the page.
    # This squares will be used to calibrate picture more precisely.

    #   1 cm                         1 cm
    #   <->                          <->
    #   ┌╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴┐↑
    #   |                              |↓ 1 cm
    #   |  ■                        ■  |
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   ┊                              ┊
    #   |  ■                        ■  |
    #   |                              |↑
    #   └╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴╴┘↓ 1 cm
    #

    # Detection algorithm is quite naive:
    # We'll search for a square alternatively in the four corners,
    # extending the search area and being more tolerant if needed.

    # First pass, to detect rotation.
    positions, *_ = detect_four_squares(m, calib_square, cm, debug=debug)
    print(positions)

    # Now, let's detect the rotation.
    (i1, j1), (i2, j2) = positions["tl"], positions["tr"]
    rotation_h1 = atan((i2 - i1) / (j2 - j1))
    (i1, j1), (i2, j2) = positions["bl"], positions["br"]
    rotation_h2 = atan((i2 - i1) / (j2 - j1))
    rotation_h = degrees(0.5 * (rotation_h1 + rotation_h2))
    print("Detected rotation (h): %s degrees." % round(rotation_h, 4))

    (i1, j1), (i2, j2) = positions["tl"], positions["bl"]
    rotation_v1 = atan((j1 - j2) / (i2 - i1))
    (i1, j1), (i2, j2) = positions["tr"], positions["br"]
    rotation_v2 = atan((j1 - j2) / (i2 - i1))
    rotation_v = degrees(0.5 * (rotation_v1 + rotation_v2))
    print("Detected rotation (v): %s degrees." % round(rotation_v, 4))

    # Rotate page.
    # (rotation_v should be a bit more precise than rotation_h).
    rotation = (rotation_h + 1.5 * rotation_v) / 2.5

    print(f"Rotate picture: {round(rotation, 4)}°")
    pic, m = transform(
        pic,
        "rotate",
        rotation,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )

    (i1, j1), (i2, j2) = positions["tl"], positions["br"]

    # XXX: implement other paper sheet sizes. Currently only A4 is supported.

    # Distance between the top left corners of the left and right squares is:
    # 21 cm - (margin left + margin right + 1 square width)
    h_pixels_per_mm = (j2 - j1) / (210 - calib_shift_mm)
    # Distance between the top left corners of the top and bottom squares is:
    # 29.7 cm - (margin top + margin bottom + 1 square height)
    v_pixels_per_mm = (i2 - i1) / (297 - calib_shift_mm)
    cm = 10 * (h_pixels_per_mm + 1.5 * v_pixels_per_mm) / 2.5
    print(f"Detect pixels/cm: {cm}")

    # Redetect calibration squares.
    print("ok")
    positions, (i1, j1), (i2, j2) = detect_four_squares(m, calib_square, cm, debug=debug)
    print("ok2")

    try:
        i3, j3 = find_document_id_band(m, i1, j1, j2, square_size, viewer)
    except StopIteration:
        # Orientation probably incorrect.
        print("Reversed page detected: 180° rotation.")
        pic, m = transform(pic, "transpose", method=Image.ROTATE_180)
        height, width = m.shape
        p = positions
        for corner in p:
            i, j = p[corner]
            i = height - 1 - i - calib_square
            j = width - 1 - j - calib_square
            p[corner] = i, j
            viewer.add_square((i, j), calib_square, color=Color.green)
        # Replace each tag by the opposite (top-left -> bottom-right).
        p["tl"], p["bl"], p["br"], p["tr"] = p["br"], p["tr"], p["tl"], p["bl"]
        # ~ color2debug(m)
        (i1, j1), (i2, j2) = area_opposite_corners(positions)
        # Redetect calibration squares.
        # ~ positions, (i1, j1), (i2, j2) = detect_four_squares(m, square_size, cm, debug=debug)
        try:
            i3, j3 = find_document_id_band(m, i1, j1, j2, square_size, viewer)
        except StopIteration:
            print("ERROR: Can't find identification band, displaying search areas in red.")
            print(i1, j1, i2, j2)
            viewer.display()
            raise CalibrationError("Can't find identification band !")

    # Distance between the top left corners of the left and right squares is:
    # 21 cm - (margin left + margin right + 1 square width)
    h_pixels_per_mm = (j2 - j1) / (210 - calib_shift_mm)
    # Distance between the top left corners of the top and bottom squares is:
    # 29.7 cm - (margin top + margin bottom + 1 square height)
    v_pixels_per_mm = (i2 - i1) / (297 - calib_shift_mm)
    #    cm = 10*(h_pixels_per_mm + 1.5*v_pixels_per_mm)/2.5

    print(positions)
    for i, j in positions.values():
        viewer.add_square((i, j), calib_square)
    viewer.add_square((i3, j3), square_size)
    if debug:
        viewer.display()
    # ~ input('- pause -')

    return m, h_pixels_per_mm, v_pixels_per_mm, positions["tl"], (i3, j3)


def read_doc_id_and_page(
    m: ndarray, pos: Pixel, f_square_size: float, viewer: ArrayViewer
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
        if k % 2:
            viewer.add_square((i, j_), square_size)
        else:
            viewer.add_square((i, j_), square_size, color=Color.blue)
        if test_square_color(m, i, j_, square_size, proportion=0.5, gray_level=0.5):
            doc_id += 2**k
            # ~ print((k, (i3, j)), " -> black")
        # ~ else:
        # ~ print((k, (i3, j)), " -> white")

    # ~ color2debug(m)
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
    viewer: ArrayViewer,
) -> tuple[StudentId, StudentName]:
    student_ID = ""
    student_name = ""
    cell_size = round(f_cell_size)
    half_cell = round(f_cell_size / 2)
    ID_length, max_digits, digits = id_format
    # ~ height = ID_length*cell_size
    i0, j0 = pos
    #            color2debug(m, (i0, j0), (i0 + cell_size, j0 + cell_size), color=(0,255,0))
    # Scan grid row by row. For each row, the darker cell is retrieved,
    # and the associated character is appended to the ID.
    all_ID_are_of_the_same_length = len(set(len(ID) for ID in students_ids)) == 1
    ev = eval_square_color
    for n in range(ID_length):
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
        if all_ID_are_of_the_same_length and len(digits_for_nth_character) == 1:
            # No need to read, there is no choice for this character !
            student_ID += digits_for_nth_character.pop()
            continue
        for k, d in enumerate(digits_for_nth_character):
            # Left ot the cell.
            j = round(j0 + (k + 1) * f_cell_size)
            # ~ val = eval_square_color(m, i, j, cell_size)
            # ~ print(d, val)

            # ~ color2debug(m, (i + 2, j + 2), (i - 2 + cell_size, j - 2+ cell_size), color=(1,1,0))
            if test_square_color(m, i, j, cell_size, gray_level=0.8):
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
                # ~ color2debug(m, (i, j + half_cell), (i + half_cell, j + 2*half_cell), display=True)
                black_cells.append((square_blackness, d))
                print("Found:", d, square_blackness)
                # ~ color2debug(m, (imin + i, j), (imin + i + cell_size, j + cell_size))
                viewer.add_square((i, j), cell_size, color=Color.cyan)
            else:
                viewer.add_square((i, j), cell_size)
        if black_cells:
            black_cells.sort(reverse=True)
            print(black_cells)
            # Test if there is enough difference between the blackest
            # and the second blackest (minimal difference was set empirically).
            if len(black_cells) == 1 or black_cells[0][0] - black_cells[1][0] > 0.2:
                # The blackest one is chosen:
                digit = black_cells[0][1]
                student_ID += digit
    if student_ID in students_ids:
        print("Student ID:", student_ID)
        student_name = students_ids[StudentId(student_ID)]
    else:
        print(f"ID list: {students_ids!r}")
        print(f"Warning: invalid student id {student_ID!r} !")
        # ~ color2debug(m)
    return StudentId(student_ID), StudentName(student_name)


def read_student_name(m: ndarray, students: list[StudentName], TOP: int, f_square_size: float) -> StudentName:
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
    vpos = TOP + 2 * square_size
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


def scan_picture(
    filename: str | Path, config: Configuration, manual_verification=None, debug=False
) -> tuple[PicData, ndarray]:
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
        * the following dictionary:
            {'ID': int,
            'page': int,
            'name': str, # student_name
            'student_ID': str,
            # answers checked by the student for each question:
            'answered': dict[int, set[int]],
            # Position of each checkbox in the page:
            'positions': dict[tuple[int, int], tuple[int, int]],
            'cell_size': int,
            # Translation table ({question number before shuffling: after shuffling})
            'questions_nums_conversion': dict[int, int],
            # Manual verification by the user ?
            'verified': bool|None}
        * an array representing the current picture.
    """
    filename = str(filename)
    # Convert to grayscale picture.
    pic: Image.Image = Image.open(filename).convert("L")
    # noinspection PyTypeChecker
    m: ndarray = array(pic) / 255.0
    viewer = ArrayViewer(m)
    # Increase contrast if needed (the lightest pixel must be white,
    # the darkest must be black).
    min_val = amin(m)
    max_val = amax(m)
    if debug:
        viewer.display()
        print(f"Old range: {min_val} - {max_val}")
    if min_val > 0 or max_val < 255 and max_val - min_val > 0.2:
        m = (m - min_val) / (max_val - min_val)
        viewer.array = m
        if debug:
            print(f"New range: {amin(m)} - {amax(m)}")
            viewer.display()
    else:
        print(f"Warning: not enough contrast in picture {filename!r} !")

    # ------------------------------------------------------------------
    #                          CONFIGURATION
    # ------------------------------------------------------------------
    # Load configuration.
    # if isinstance(config, str):
    #     config: Configuration = load(config)
    # ~ n_questions = config['questions']
    # ~ n_answers = config['answers (max)']
    students = config.students_list
    n_students = len(students)
    students_ids = config.students_ids

    # ------------------------------------------------------------------
    #                          CALIBRATION
    # ------------------------------------------------------------------

    m, h_pixels_per_mm, v_pixels_per_mm, (TOP, LEFT), (i, j) = calibrate(pic, m, debug=debug)
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
    doc_id, page = read_doc_id_and_page(m, (i, j), f_square_size, viewer)

    # ------------------------------------------------------------------
    #                  IDENTIFY STUDENT (OPTIONAL)
    # ------------------------------------------------------------------

    student_name = StudentName("")
    student_ID = StudentId("")

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
            student_ID, student_name = read_student_id_and_name(
                m, students_ids, xy2ij(*config.id_table_pos), config.id_format, f_cell_size, viewer
            )

        else:
            print("No students list.")

        print("Student name:", student_name)

    # ------------------------------------------------------------------
    #                      READ ANSWERS
    # ------------------------------------------------------------------

    pic_data = PicData(
        doc_id=doc_id,  # ID of the test
        page=page,  # page number
        name=student_name,
        student_ID=student_ID,
        # answers checked by the student for each question:
        answered={},
        # Position of each checkbox in the page:
        positions={},
        cell_size=cell_size,
        # Translation table ({question number before shuffling: after shuffling})
        questions_nums_conversion={},
        needs_review=False,
        detection_status={},
        revision_status={},
        pic_path="",
    )
    answered = pic_data.answered
    positions = pic_data.positions
    displayed_questions_numbers = pic_data.questions_nums_conversion
    detection_status = pic_data.detection_status

    try:
        boxes = config.boxes[doc_id][page]
    except KeyError:
        print(
            f"WARNING: ID {doc_id!r} - page {page!r} not found in config file !\n"
            f"Maybe ID {doc_id!r} - page {page!r} is an empty page ?"
        )
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

    # Store blackness of checkboxes, to help detect false positives
    # and false negatives.
    blackness = {}
    core_blackness = {}

    for key, pos in boxes.items():
        # ~ should_have_answered = set() # for debugging only.
        i, j = xy2ij(*pos)
        i, j = adjust_checkbox(m, i, j, cell_size)
        # `q` and `a` are real questions and answers numbers, that is,
        # questions and answers numbers before shuffling.
        q_str, a_str = key[1:].split("-")
        q = OriginalQuestionNumber(int(q_str))
        a = OriginalAnswerNumber(int(a_str))
        # `q0` and `a0` keep track of apparent question and answers numbers,
        # which will be used on output to make debugging easier.
        q0, a0 = real2apparent(q, a, config, doc_id)
        displayed_questions_numbers[q] = q0

        # answer_is_correct = (a in correct_answers)

        test_square = partial(test_square_color, m, i, j, cell_size, margin=5)
        # color_square = partial(viewer.add_square, (i, j), cell_size)

        if q not in answered:
            answered[q] = set()
            print(f"\n{ANSI_CYAN}• Question {q0}{ANSI_RESET} (Q{q})")

        # The following will be used to detect false positives or false negatives later.
        blackness[(q, a)] = eval_square_color(m, i, j, cell_size, margin=4)
        core_blackness[(q, a)] = eval_square_color(m, i, j, cell_size, margin=7)
        positions[(q, a)] = (i, j)

        answer_is_correct = is_answer_correct(q, a, config, doc_id)

        if (
            test_square(proportion=0.2, gray_level=0.65)
            # ~ test_square_color(m, i + 3, j + 3, cell_size - 7, proportion=0.4, gray_level=0.75) or
            # ~ test_square_color(m, i + 3, j + 3, cell_size - 7, proportion=0.45, gray_level=0.8) or
            or test_square(proportion=0.4, gray_level=0.90)
            or test_square(proportion=0.6, gray_level=0.95)
        ):
            # The student has checked this box.
            c = "■"
            answered[q].add(a)

            if not test_square(proportion=0.4, gray_level=0.9):
                detection_status[(q, a)] = DetectionStatus.PROBABLY_CHECKED
            else:
                detection_status[(q, a)] = DetectionStatus.CHECKED
        else:
            # This box was left unchecked.
            c = "□"
            if test_square(proportion=0.2, gray_level=0.95):
                detection_status[(q, a)] = DetectionStatus.PROBABLY_UNCHECKED
            else:
                detection_status[(q, a)] = DetectionStatus.UNCHECKED

        if answer_is_correct is None:
            # This answer was neutralized (ahem, the teacher probably made a mistake... ;))
            term_color = ANSI_GRAY
        elif c == "□" and answer_is_correct or c == "■" and not answer_is_correct:
            # Incorrect answer.
            term_color = ANSI_YELLOW
        else:
            # Great answer !
            term_color = ""

        print(f"  {term_color}{c} {a}  {ANSI_RESET}", end="\t")
        # ~ print('\nCorrect answers:', should_have_answered)
    print()

    # Test now for false negatives and false positives.

    # First, try to detect false negatives.
    # If a checkbox considered unchecked is notably darker than the others,
    # it is probably checked after all (and if not, it will most probably be caught
    # with false positives in next section).
    # Add 0.03 to 1.5*mean, in case mean is almost 0.
    ceil = 1.5 * sum(blackness.values()) / len(blackness) + 0.02
    core_ceil = 1.2 * sum(core_blackness.values()) / len(core_blackness) + 0.01
    for q, a in blackness:  # pylint: disable=dict-iter-missing-items
        if a not in answered[q] and (blackness[(q, a)] > ceil or core_blackness[(q, a)] > core_ceil):
            print("False negative detected", (q, a))
            # This is probably a false negative, but we'd better verify manually.
            manual_verification = manual_verification is not False
            answered[q].add(a)
            detection_status[(q, a)] = DetectionStatus.PROBABLY_CHECKED

    # If a checkbox is tested as checked, but is much lighter than the darker one,
    # it is very probably a false positive.
    floor = max(0.2 * max(blackness.values()), max(blackness.values()) - 0.4)
    upper_floor = max(0.2 * max(blackness.values()), max(blackness.values()) - 0.3)
    core_floor = max(0.2 * max(core_blackness.values()), max(core_blackness.values()) - 0.4)
    upper_core_floor = max(0.2 * max(core_blackness.values()), max(core_blackness.values()) - 0.3)
    for q, a in blackness:  # pylint: disable=dict-iter-missing-items
        if a in answered[q] and (
            blackness[(q, a)] < upper_floor or core_blackness[(q, a)] < upper_core_floor
        ):
            manual_verification = manual_verification is not False
            if blackness[(q, a)] < floor or core_blackness[(q, a)] < core_floor:
                print("False positive detected", (q, a), blackness[(q, a)], max(blackness.values()))
                # This is probably a false positive, but we'd better verify manually.
                answered[q].discard(a)
                # Change box color for manual verification.
                detection_status[(q, a)] = DetectionStatus.PROBABLY_UNCHECKED
            else:
                # Probably note a false positive, but we should verify.
                # Change box color for manual verification.
                detection_status[(q, a)] = DetectionStatus.PROBABLY_CHECKED

    if debug:
        viewer.display()

    pic_data.needs_review = (
        DetectionStatus.PROBABLY_CHECKED in detection_status.values()
        or DetectionStatus.PROBABLY_UNCHECKED in detection_status.values()
    )
    # Keep matrix separate from other output data, as it is often not wanted
    # when debugging.
    return pic_data, m
