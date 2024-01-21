from dataclasses import dataclass
from enum import Enum
from math import hypot, atan, degrees
from typing import Literal, Iterator

from PIL import Image
from numpy import ndarray, flipud, fliplr, zeros, amin, dot, array

from ptyx_mcq.parameters import SQUARE_SIZE_IN_CM, CALIBRATION_SQUARE_SIZE, CALIBRATION_SQUARE_POSITION
from ptyx_mcq.scan.color import Color
from ptyx_mcq.scan.square_detection import eval_square_color, find_black_square
from ptyx_mcq.scan.tools import round

from ptyx_mcq.scan.types_declaration import (
    Pixel,
    MissingSquare,
    Rectangle,
    CalibrationError,
    Shape,
    CalibrationSquaresNotFound,
    Area,
    IdBandNotFound,
)
from ptyx_mcq.scan.image_viewer import ImageViewer
from ptyx_mcq.tools.io_tools import print_warning

ValidCornerStringValues = Literal["TL", "TR", "BL", "BR"]


class _VHPosition(Enum):
    """Base class for VPosition and HPosition."""

    def __invert__(self):
        return self.__class__(-self.value)


class VPosition(_VHPosition):
    """Vertical position.

    Use `~` operator to get the opposite position:

        >>> ~VPosition.TOP
        VPosition.BOTTOM
    """

    TOP = -1
    BOTTOM = 1


class HPosition(_VHPosition):
    """Horizontal position.

    Use `~` operator to get the opposite position:

        >>> ~HPosition.LEFT
        HPosition.RIGHT
    """

    LEFT = -1
    RIGHT = 1


@dataclass(frozen=True)
class Corner:
    """One of the four Corners."""

    v: VPosition
    h: HPosition

    def __invert__(self):
        return Corner(~self.v, ~self.h)

    def __str__(self):
        return f"Corner({self.v.name}, {self.h.name})"

    @property
    def name(self):
        return f"{self.v.name}-{self.h.name}"

    @staticmethod
    def from_string(name: ValidCornerStringValues) -> "Corner":
        assert name in CORNER_NAMES
        return Corner(
            v=VPosition.TOP if name[0] == "T" else VPosition.BOTTOM,
            h=HPosition.LEFT if name[1] == "L" else HPosition.RIGHT,
        )

    @staticmethod
    def convert(key: "ValidCornerKey") -> "Corner":
        match key:
            case Corner():
                return key
            case str():
                return Corner.from_string(key)
            case (VPosition() as v, HPosition() as h):
                return Corner(v, h)
            case _:
                raise TypeError

    def to_string(self) -> str:
        return self.v.name[0] + self.h.name[0]

    @property
    def opposite_corner(self) -> "Corner":
        return Corner(~self.v, ~self.h)

    @property
    def other_corner_on_same_line(self) -> "Corner":
        return Corner(self.v, ~self.h)

    @property
    def other_corner_on_same_column(self) -> "Corner":
        return Corner(~self.v, self.h)


CORNERS = frozenset(Corner(h, v) for h in VPosition for v in HPosition)
ValidCornerKey = ValidCornerStringValues | Corner | tuple[VPosition, HPosition]


@dataclass
class CornersPositions:
    TL: Pixel | None = None
    TR: Pixel | None = None
    BL: Pixel | None = None
    BR: Pixel | None = None

    @staticmethod
    def _convert_key(key: ValidCornerKey) -> str:
        match key:
            case str():
                return key
            case Corner():
                return key.to_string()
            case (VPosition() as h, HPosition() as v):
                return Corner(h, v).to_string()
            case _:
                raise TypeError(
                    f"{key!r} is not a valid value, it must be of type `Corner`,"
                    " a tuple (`VPosition`, `HPosition`) or a valid string"
                    f" (any of {', '.join(CORNER_NAMES)})."
                )

    def __getitem__(self, key: ValidCornerKey) -> Pixel | None:
        return getattr(self, self._convert_key(key))

    def __setitem__(self, key: ValidCornerKey, value: Pixel | None) -> None:
        setattr(self, self._convert_key(key), value)

    def __delitem__(self, key: ValidCornerKey) -> None:
        setattr(self, self._convert_key(key), None)

    def __delattr__(self, item: str) -> None:
        setattr(self, item, None)

    def __iter__(self) -> Iterator[Corner]:
        """Iterate over all corners whose position is not None."""
        return iter([Corner.from_string(name) for name in CORNER_NAMES if getattr(self, name) is not None])

    def flip(self) -> None:
        """Replace each corner with its opposite."""
        self.TL, self.BL, self.BR, self.TR = self.BR, self.TR, self.TL, self.BL

    def __len__(self) -> int:
        """Number of corners whose position is known."""
        return sum(1 for _ in self.values())

    def values(self) -> Iterator[Pixel]:
        """Return all positions whose value is not `None`."""
        return iter([value for name in CORNER_NAMES if (value := getattr(self, name)) is not None])

    def items(self) -> Iterator[tuple[Corner, Pixel]]:
        return iter(
            [
                (Corner.from_string(name), value)
                for name in CORNER_NAMES
                if (value := getattr(self, name)) is not None
            ]
        )


CORNER_NAMES: tuple[ValidCornerStringValues] = ("TL", "TR", "BL", "BR")  # type:ignore


def find_black_cell(grid, width: int, height: int, detection_level: float) -> tuple[int, int]:
    """Find the "first" black-enough pixel in the grid.

     This pixel corresponds to a black (or almost black) square in the original picture.

    The mesh grid is browsed starting from the top left corner,
    following oblique lines (North-East->South-West), as follows:

        1  2  4  7
        3  5  8  11
        6  9  12 14
        10 13 15 16

    Return the black-enough pixel position.
    """
    for k in range(height + width):
        # j < ll <=> k - i < ll <=> k - ll < i <=> i >= k - ll + 1
        for i in range(max(0, k - width + 1), min(k + 1, height)):
            j = k - i
            #            if grid[i, j] < 100:
            #                i0 = half*i   # Add `half` and `m` to the function parameters
            #                j0 = half*j   # before running this code.
            #                color2debug(m, (i0, j0), (i0 + half, j0 + half))
            if grid[i, j] < detection_level:
                return i, j
    raise MissingSquare("Corner square not found.")


def find_corner_square(
    m: ndarray,
    size: int,
    corner: Corner,
    *,
    max_whiteness: float = 0.55,
    tolerance: float = 0.2,
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
    # First, flip the matrix if needed, so that the corner considered
    # is now the top left corner.
    if corner.v == VPosition.BOTTOM:
        m = flipud(m)
    if corner.h == HPosition.RIGHT:
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
        raise MissingSquare(
            f"Corner square {corner} not found.", details=[Rectangle((i0, j0), size, color=Color.blue)]
        )

    if corner.v == VPosition.BOTTOM:
        i0 = height - 1 - i0 - size
    if corner.h == HPosition.RIGHT:
        j0 = width - 1 - j0 - size

    return i0, j0


def orthogonal(corner: ValidCornerKey, positions: CornersPositions) -> bool:
    # v = corner[0]  # Unpacking a string is disallowed for mypy!
    # h = corner[1]
    # corner1 = v + ("l" if h == "r" else "r")
    # corner2 = ("t" if v == "b" else "b") + h
    corner = Corner.convert(corner)
    pos = positions[corner]
    pos1 = positions[corner.other_corner_on_same_line]
    pos2 = positions[corner.other_corner_on_same_column]
    assert pos is not None and pos1 is not None and pos2 is not None
    i, j = pos
    i1, j1 = pos1
    i2, j2 = pos2
    vect1 = i1 - i, j1 - j
    vect2 = i2 - i, j2 - j
    cos_a = dot(vect1, vect2) / (hypot(*vect1) * hypot(*vect2))
    return abs(cos_a) < 0.06


def area_defined_by_corners(positions: CornersPositions) -> tuple[Pixel, Pixel]:
    tl = positions.TL
    tr = positions.TR
    bl = positions.BL
    br = positions.BR
    assert tl is not None and tr is not None and bl is not None and br is not None
    i1 = round((tl[0] + tr[0]) / 2)
    i2 = round((bl[0] + br[0]) / 2)
    j1 = round((tl[1] + bl[1]) / 2)
    j2 = round((tr[1] + br[1]) / 2)
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
    debug_info: list[Shape] = []
    #    h = w = round(2*(1 + SQUARE_SIZE_IN_CM)*cm)
    # Make a mutable copy of frozenset CORNERS.
    corners = set(CORNERS)
    # `positions` is used to store the position (in pixels) of the calibration square of each corner.
    positions = CornersPositions()
    for corner in CORNERS:
        try:
            i, j = find_corner_square(m, square_size, corner, tolerance=tolerance)
            # ~ # We may have only detected a part of the square by restricting
            # ~ # the search area, so extend search by the size of the square.
            # ~ i, j = find_corner_square(m, square_size, corner, h + square_size,
            # ~ w + square_size, tolerance, whiteness)
            debug_info.append(Rectangle((i, j), square_size))
            positions[corner] = i, j
            corners.remove(corner)
        except MissingSquare as e:
            debug_info.extend(e.details)

        # ~ if input(len(positions)) == 'd':
        # ~ color2debug(m)

    # If one calibration square is missing (a corner of the sheet is
    # folded for example), it will be generated from the others.

    #    color2debug(m)
    print(f"Corners detected: {len(positions)}")
    if len(positions) <= 2:
        raise CalibrationSquaresNotFound("Only 2 squares found, calibration failed !", details=debug_info)

    if len(positions) == 4:
        for v in VPosition:
            pos1 = positions[v, HPosition.RIGHT]
            pos2 = positions[v, HPosition.LEFT]
            assert pos1 is not None and pos2 is not None
            h_shift = pos1[0] - pos2[0]
            if abs(h_shift) > max_alignment_error_cm * cm:
                print("Warning: Horizontal alignment problem in corners squares !")
                print(f"horizontal shift ({v}): {h_shift}")
        for h in HPosition:
            pos1 = positions[VPosition.BOTTOM, h]
            pos2 = positions[VPosition.TOP, h]
            assert pos1 is not None and pos2 is not None
            v_shift = pos1[1] - pos2[1]
            if abs(v_shift) > max_alignment_error_cm * cm:
                print("Warning: Vertical alignment problem in corners squares !")
                print(f"vertical shift ({h}): {v_shift}")

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
            opposite_corner = orthogonal_corner.opposite_corner
            print(f"Removing {opposite_corner.name} corner (not orthogonal!)")
            del positions[opposite_corner]

    if len(positions) == 4:
        # If there are 4 squares, and one is less dark than the others,
        # let's drop it and use only the 3 darkest.
        # (The 4th square will be generated again using the position of the 3 others).
        darkness = {}
        for corner in positions:
            pos = positions[corner]
            assert pos is not None
            darkness[corner] = eval_square_color(m, *pos, square_size)

        lighter_corner = min(darkness, key=darkness.get)  # type: ignore
        if darkness[lighter_corner] < 0.4:
            print(f"Removing {lighter_corner.name} corner " f"(too light: {darkness[lighter_corner]} !)")
            del positions[lighter_corner]

    if len(positions) == 4:
        if number_of_orthogonal_corners <= 2:
            debug_info.extend([Rectangle(pos, square_size) for pos in positions.values()])
            print("number_of_orthogonal_corners =", number_of_orthogonal_corners)
            raise CalibrationSquaresNotFound("Something wrong with the corners !", details=debug_info)

    for corner in CORNERS:
        if corner not in positions:
            print(
                f"Warning: {corner.name} corner not found.\n"
                "Its position will be deduced from the 3 other corners."
            )
            # This is the opposite corner of the missing one.
            pos0 = positions[corner.opposite_corner]
            pos1 = positions[corner.other_corner_on_same_column]
            pos2 = positions[corner.other_corner_on_same_line]
            assert pos0 is not None and pos1 is not None and pos2 is not None
            i0, j0 = pos0
            i1, j1 = pos1
            i2, j2 = pos2
            i = i2 + (i1 - i0)
            j = j2 + (j1 - j0)

            # Calculate the last corner (ABCD parallelogram <=> Vec{AB} = \Vec{DC})
            positions[corner] = (i, j)
            debug_info.append(Rectangle((i, j), square_size, color=Color.cyan))

            # For example: positions['bl'] = positions['br'][0], positions['tl'][1]

    ij1, ij2 = area_defined_by_corners(positions)

    if debug:
        debug_info.append(Area(ij1, ij2, color=Color.green))
        ImageViewer(array=m, *debug_info).display()

    return positions, ij1, ij2


def find_document_id_band(m: ndarray, i: int, j1: int, j2: int, square_size: int) -> Rectangle:
    """Return the top left corner (coordinates in pixels) of the document ID band first square."""
    margin = square_size
    i1, i2 = i - margin, i + square_size + margin
    j1, j2 = j1 + 3 * square_size, j2 - 2 * square_size
    search_area = m[i1:i2, j1:j2]
    try:
        i3, j3 = find_black_square(
            search_area, size=square_size, error=0.3, gray_level=0.5, mode="column", debug=False
        ).__next__()
    except StopIteration:
        raise IdBandNotFound(
            "The beginning of the ID band could not be found.",
            details=[
                Area((i1, j1), (i2, j2)),
            ],
        )
    i3 += i1
    j3 += j1
    return Rectangle((i3, j3), square_size)


def calibrate(pic: Image.Image, m: ndarray, debug=False) -> tuple[ndarray, float, float, Pixel, Pixel]:
    """Detect picture resolution and ensure correct orientation."""
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
    positions: CornersPositions
    # First pass is usually not worth displaying when debugging.
    positions, *_ = detect_four_squares(m, calib_square, cm, debug=False)
    print(positions)

    tl = positions.TL
    tr = positions.TR
    bl = positions.BL
    br = positions.BR
    assert tl is not None and tr is not None and bl is not None and br is not None

    # Now, let's detect the rotation.
    (i1, j1), (i2, j2) = tl, tr
    rotation_h1 = atan((i2 - i1) / (j2 - j1))
    (i1, j1), (i2, j2) = bl, br
    rotation_h2 = atan((i2 - i1) / (j2 - j1))
    rotation_h = degrees(0.5 * (rotation_h1 + rotation_h2))
    print("Detected rotation (h): %s degrees." % round(rotation_h, 4))

    (i1, j1), (i2, j2) = tl, bl
    rotation_v1 = atan((j1 - j2) / (i2 - i1))
    (i1, j1), (i2, j2) = tr, br
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

    (i1, j1), (i2, j2) = tl, br

    # XXX: implement other paper sheet sizes. Currently only A4 is supported.

    # Distance between the top left corners of the left and right squares is:
    # 21 cm - (margin left + margin right + 1 square width)
    h_pixels_per_mm = (j2 - j1) / (210 - calib_shift_mm)
    # Distance between the top left corners of the top and bottom squares is:
    # 29.7 cm - (margin top + margin bottom + 1 square height)
    v_pixels_per_mm = (i2 - i1) / (297 - calib_shift_mm)
    cm = 10 * (h_pixels_per_mm + 1.5 * v_pixels_per_mm) / 2.5
    print(f"Detect pixels/cm: {cm}")

    # Detect calibration squares again, to enhance accuracy.
    positions, (i1, j1), (i2, j2) = detect_four_squares(m, calib_square, cm, debug=debug)

    debug_info: list[Shape] = []

    try:
        first_id_square = find_document_id_band(m, i1, j1, j2, square_size)

    except IdBandNotFound as e:
        debug_info.extend(e.details)
        # Orientation probably incorrect.
        print("Reversed page detected: 180° rotation.")
        pic, m = transform(pic, "transpose", method=Image.ROTATE_180)
        height, width = m.shape
        for corner, position in positions.items():
            i, j = position
            i = height - 1 - i - calib_square
            j = width - 1 - j - calib_square
            positions[corner] = i, j
            debug_info.append(Rectangle((i, j), calib_square, color=Color.green))
        # Replace each tag by the opposite (top-left -> bottom-right).
        positions.flip()
        # ~ color2debug(m)
        (i1, j1), (i2, j2) = area_defined_by_corners(positions)
        # Redetect calibration squares.
        # ~ positions, (i1, j1), (i2, j2) = detect_four_squares(m, square_size, cm, debug=debug)
        try:
            first_id_square = find_document_id_band(m, i1, j1, j2, square_size)
        except IdBandNotFound as e:
            debug_info.extend(e.details)
            print_warning("Identification band not found!")
            if debug:
                print(f"Search area: {i1, j1, i2, j2}")
                print("Displaying search areas in red.")
                ImageViewer(array=m, *debug_info).display()
            raise IdBandNotFound("Can't find identification band!", details=debug_info, matrix=m)

    if debug:
        print(f"Detected corners positions: {positions}")

    # Distance between the top left corners of the left and right squares is:
    # 21 cm - (margin left + margin right + 1 square width)
    h_pixels_per_mm = (j2 - j1) / (210 - calib_shift_mm)
    # Distance between the top left corners of the top and bottom squares is:
    # 29.7 cm - (margin top + margin bottom + 1 square height)
    v_pixels_per_mm = (i2 - i1) / (297 - calib_shift_mm)
    #    cm = 10*(h_pixels_per_mm + 1.5*v_pixels_per_mm)/2.5

    debug_info.extend(Rectangle(position, calib_square) for position in positions.values())
    debug_info.append(first_id_square)

    if debug:
        print(f"Positions: {positions}")
        ImageViewer(array=m, *debug_info).display()
    # ~ input('- pause -')

    assert positions.TL is not None
    return m, h_pixels_per_mm, v_pixels_per_mm, positions.TL, first_id_square.position


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
