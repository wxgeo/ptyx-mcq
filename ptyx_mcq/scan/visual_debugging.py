import subprocess
import tempfile
from os.path import join

from PIL import Image
from numpy import ndarray, int8

from ptyx_mcq.scan.color import Color, RGB

FloatPosition = tuple[float, float]


# TODO: rewrite this using a class.


# noinspection PyDefaultArgument
def color2debug(
    array: ndarray = None,
    from_: FloatPosition = None,
    to_: FloatPosition = None,
    color: RGB = Color.red,
    display: bool = True,
    thickness: int = 2,
    fill=False,
    _d={},
    wait=True,
):
    """Display picture with a red (by default) rectangle for debugging.
    The annotated picture can be displayed immediately (default), or the annotation can be memorized,
    if `display` is set to `False`.
    It allows to display several annotations at once.

    Launch this function without argument to clear all previous stored annotations.

    Parameters:
    `array` is an array containing the image data (image must be gray mode,
    each pixel represented by a float from 0 (black) to 1 (white)).
    `from_` represent one corner of the red rectangle.
    `to_` represent opposite corner of the red rectangle.
    `color` is given as a RGB tuple ([0-255], [0-255], [0-255]).
    `fill` (True|False) indicates if the rectangle should be filled.

    Usage: color2debug((0,0), (200,10), color=(255, 0, 255))

    If you need to display `n` rectangles, call `color2debug()` with
    `display=False` for the first `n-1` rectangles, and then with
    `display=True` for the last rectangle.

    `_d` is used internally to store values between two runs, if display=False.

    NOTA:
    - `feh` must be installed.
      On Ubuntu/Debian: sudo apt-get install feh
    - Left-dragging the picture with mouse inside feh removes blurring/anti-aliasing,
      making visual debugging a lot easier.
    """
    if array is None:
        _d.clear()
        return
    ID = id(array)
    if ID not in _d:
        # Load image only if not loaded previously.
        # .astype(int8) will make more arrays representable.
        _d[ID] = Image.fromarray((255 * array).astype(int8)).convert("RGB")
    rgb = _d[ID]
    height, width = array.shape
    if from_ is not None:
        if to_ is None:
            to_ = from_
        i1, j1 = from_
        i2, j2 = to_
        if i2 is None:
            i2 = height - 1
        if j2 is None:
            j2 = width - 1
        pix = rgb.load()
        imin, imax = int(min(i1, i2)), int(max(i1, i2))
        jmin, jmax = int(min(j1, j2)), int(max(j1, j2))

        def set_pix(i: int, j: int, color: RGB) -> None:
            """Set safely pixel color (if `i` or `j` is incorrect, do nothing)."""
            if 0 <= i < height and 0 <= j < width:
                pix[j, i] = color

        if fill:
            for i in range(imin, imax + 1):
                for j in range(jmin, jmax + 1):
                    set_pix(i, j, color)
        else:
            # left and right sides of rectangle
            for i in range(imin, imax + 1):
                for j in range(jmin, jmin + thickness):
                    set_pix(i, j, color)
                for j in range(jmax + 1 - thickness, jmax + 1):
                    set_pix(i, j, color)
            # top and bottom sides of rectangle
            for j in range(jmin, jmax + 1):
                for i in range(imin, imin + thickness):
                    set_pix(i, j, color)
                for i in range(imax + 1 - thickness, imax + 1):
                    set_pix(i, j, color)

    if display:
        del _d[ID]
        if subprocess.call(["which", "feh"]) != 0:
            raise RuntimeError(
                "The `feh` command is not found, please " "install it (`sudo apt install feh` on Ubuntu)."
            )
        with tempfile.TemporaryDirectory() as tmpdirname:
            path = join(tmpdirname, "test.png")
            rgb.save(path)
            process: subprocess.CompletedProcess | subprocess.Popen
            if wait:
                process = subprocess.run(["feh", "-F", path])
            else:
                process = subprocess.Popen(["feh", "-F", path], stdin=subprocess.DEVNULL)
            input("-- pause --\n")
            return process
