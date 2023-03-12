from typing import Literal, Iterator, Iterable, Tuple

from numpy import array, nonzero, transpose, ndarray

from ptyx_mcq.scan.visual_debugging import color2debug

Pixel = Tuple[int, int]


# def top_left_iterator(stop, step=1):
#     """Return an iterator for coordinates starting from top-left corner."""
#     # Pixels are visited starting from top-left corner
#     # in the following order:
#     # 1  3  8  15
#     # 4  2  6  13
#     # 9  7  5  11
#     # 16 14 12 10
#     for n in range(0, stop, step):
#         yield n, n
#         for k in range(n - step, -1, -step):
#             yield k, n
#             yield n, k


# def total_grayness(m):
#     return numpy.interp(m, [0, 0.2, 0.8, 1], [0, 0.1, 0.9, 1]).sum()


def find_black_rectangle(
    matrix: ndarray,
    width: int = 50,
    height: int = 50,
    error: float = 0.30,
    gray_level: float = 0.4,
    mode: Literal["row", "column"] = "row",
    debug=False,
) -> Iterator[Pixel]:
    """Detect a black rectangle of given size (in pixels) in matrix.

    The n*m matrix must contain only floats between 0 (white) and 1 (black).

    Optional parameters:
        - `error` is the ratio of white pixels allowed in the black square.
        - `gray_level` is the level above which a pixel is considered to be white.
           If it is set to 0, only black pixels will be considered black ; if it
           is close to 1 (max value), almost all pixels are considered black
           except white ones (for which value is 1.).
        - `mode` is either:
            * 'row' (picture is scanned row by row, from top to bottom)
            * 'column' (picture is scanned column by column, from left to right)

    Return a generator of (i, j) where i is line number and j is column number,
    indicating black squares top left corner.

    """
    # ~ color2debug(matrix)
    # First, convert grayscale image to black and white.
    if debug:
        print(
            f"`find_black_rectangle` parameters: width={width}, "
            f"height={height}, error={error}, gray_level={gray_level}"
        )
        color2debug(matrix)
    m = array(matrix, copy=False) < gray_level
    if debug:
        color2debug(1 - m)
    # Black pixels are represented by False, white ones by True.
    # pic_height, pic_width = m.shape
    per_line = (1 - error) * width
    per_col = (1 - error) * height
    goal = per_line * height
    # List of areas to avoid.
    to_avoid: list[tuple[int, int, int, int]] = []
    # Find a black pixel, starting from top left corner,
    # and scanning line by line (i.e. from top to bottom).
    if mode == "row":
        black_pixels: Iterable = nonzero(m)
    elif mode == "column":
        black_pixels = reversed(nonzero(transpose(array(m))))
    else:
        raise RuntimeError("Unknown mode: %s. Mode should be either 'row' or 'column'." % repr(mode))
    if debug:
        print(mode, black_pixels)
    for i, j in zip(*black_pixels):
        # Avoid detecting an already found square.
        if debug:
            print("Black pixel found at %s, %s" % (i, j))
        # ~ color2debug(m.astype(float), (i, j), (i + width, j + height), color=(255,0,255))
        if any(
            (li_min <= i <= li_max and co_min <= j <= co_max) for (li_min, li_max, co_min, co_max) in to_avoid
        ):
            continue
        assert m[i, j] == 1
        total = m[i : i + height, j : j + width].sum()
        if debug:
            print(f"Total: {total} | Goal: {goal}")
            if total >= goal / 5:
                color2debug(matrix, (i, j), (i + height, j + width))
        # ~ print(f'Black pixels ratio: {total}/{width*height} ; Min: {goal}.')
        # ~ input('- pause -')
        #        print("Detection: %s found (minimum was %s)." % (total, goal))
        if total >= goal:
            # ~ print("\nBlack square found at (%s,%s)." % (i, j))
            # Adjust detection if top left corner is a bit "damaged"
            # (i.e. if some pixels are missing there), or if this pixel is
            # only an artefact before the square.
            if debug:
                color2debug(matrix, (i, j), (i + 2, j + 2), fill=True)
            i0 = i
            j0 = j
            # Note: limit adjustment range (in case there are two consecutive squares)
            for _i in range(50):
                horizontal = vertical = False
                # Horizontal adjustment:
                try:
                    while abs(j - j0) < error * width and (
                        m[i : i + height, j + width + 1].sum() > per_col > m[i : i + height, j].sum()
                    ):
                        j += 1
                        if debug:
                            print("j+=1")
                        horizontal = True
                except IndexError:
                    pass
                # If square was already shifted horizontally in one way, don't try
                # to shift it in the opposite direction.
                if not horizontal:
                    try:
                        while (
                            abs(j - j0) < error * width
                            and m[i : i + height, j + width].sum() < per_col < m[i : i + height, j - 1].sum()
                        ):
                            j -= 1
                            if debug:
                                print("j-=1")
                            horizontal = True
                    except IndexError:
                        pass
                # Vertical adjustment:
                try:
                    while (
                        abs(i - i0) < error * height
                        and m[i + height + 1, j : j + width].sum() > per_line > m[i, j : j + width].sum()
                    ):
                        i += 1
                        if debug:
                            print("i+=1")
                        vertical = True
                except IndexError:
                    pass
                try:
                    while (
                        abs(i - i0) < error * height
                        and m[i + height, j : j + width].sum() < per_line < m[i - 1, j : j + width].sum()
                    ):
                        i -= 1
                        if debug:
                            print("i-=1")
                        vertical = True
                except IndexError:
                    pass
                if not (vertical or horizontal):
                    break
            else:
                print("Warning: adjustment of square position seems abnormally long... Skipping...")
            #
            #      Do not detect pixels there to avoid detecting
            #      the same square twice.
            #      ←—————————————————————————————————→
            #      ←——————————→  ←———————————————————→
            #      buffer zone      square itself
            #      ///////////   #####################
            #      ///////////   #####################
            #      ///////////   #####################
            #      ///////////   #####################
            #      ///////////   #####################
            #      ///////////   #####################
            #      ///////////   #####################
            #      ///////////   #####################
            #      ///////////   #####################
            #      ///////////   #####################
            #      ←——————————→  ←———————————————————→
            #      ≃ error*size          size

            # Avoid detecting an already found square.
            if any(
                (li_min <= i <= li_max and co_min <= j <= co_max)
                for (li_min, li_max, co_min, co_max) in to_avoid
            ):
                continue

            to_avoid.append((i - error * height - 1, i + height - 2, j - error * width - 1, j + width - 2))
            # ~ print("Final position of this new square is (%s, %s)" % (i, j))
            # ~ print("Forbidden areas are now:")
            # ~ print(to_avoid)
            if debug:
                input("-- pause --")
            yield i, j


def find_black_square(
    matrix: ndarray, size: int, error: float = 0.4, gray_level: float = 0.4, **kw
) -> Iterator[Pixel]:
    return find_black_rectangle(matrix, width=size, height=size, error=error, gray_level=gray_level, **kw)


# def detect_all_squares(matrix, size=50, error=0.30):
#     return list(find_black_square(matrix, size=size, error=error))


def test_square_color(
    m: ndarray,
    i: int,
    j: int,
    size: int,
    proportion: float = 0.3,
    gray_level: float = 0.75,
    margin: int = 0,
    _debug=False,
) -> bool:
    """Return True if square is black, False else.

    (i, j) is top left corner of the square, where i is line number
    and j is column number.
    `proportion` is the minimal proportion of black pixels the square must have
    to be considered black (`gray_level` is the level below which a pixel
    is considered black).
    """
    if size <= 2 * margin + 4:
        raise ValueError("Square too small for current margins !")
    square = m[i + margin : i + size - margin, j + margin : j + size - margin] < gray_level
    if _debug:
        print(square, square.sum(), len(square) ** 2)
        print(
            "proportion of black pixels detected: %s (minimum required was %s)"
            % (square.sum() / size**2, proportion)
        )
    # Test also the core of the square, since borders may induce false
    # positives if proportion is kept low (like default value).
    core = square[2:-2, 2:-2]
    return square.sum() > proportion * len(square) ** 2 and core.sum() > proportion * len(core) ** 2


def eval_square_color(m: ndarray, i: int, j: int, size: int, margin: int = 0, _debug=False) -> float:
    """Return an indicator of blackness, which is a float in range (0, 1).
    The bigger the float returned, the darker the square.

    This indicator is useful to compare several squares, and find the blacker one.
    Note that the core of the square is considered the more important part to assert
    blackness.

    (i, j) is top left corner of the square, where i is line number
    and j is column number.
    """
    if size <= 2 * margin:
        raise ValueError("Square too small for current margins !")
    # Warning: pixels outside the sheet shouldn't be considered black !
    # Since we're doing a sum, 0 should represent white and 1 black,
    # so as if a part of the square is outside the sheet, it is considered
    # white, not black ! This explain the `1 - m[...]` below.
    square = 1 - m[i + margin : i + size - margin, j + margin : j + size - margin]
    return square.sum() / (size - margin) ** 2


def adjust_checkbox(
    m: ndarray, i: int, j: int, size: int, level1: float = 0.5, level2: float = 0.6, delta: int = 5
):
    # return (i, j)
    # Try to adjust top edge of the checkbox
    i0, j0 = i, j
    if m[i : i + size, j : j + 1].sum() < level1 * size:
        for i in range(i0 - delta, i0 + delta + 1):
            if m[i : i + size, j : j + 1].sum() > level2 * size:
                break
        else:
            i = i0
    if m[i : i + 1, j : j + size].sum() < level1 * size:
        for j in range(j0 - delta, j0 + delta + 1):
            if m[i : i + 1, j : j + size].sum() > level2 * size:
                break
        else:
            j = j0
    return i, j
