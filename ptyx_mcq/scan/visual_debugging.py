import subprocess
import tempfile
from dataclasses import dataclass
from os.path import join
from typing import Any, Optional, overload, Literal

from PIL import Image
from numpy import ndarray, int8

from ptyx_mcq.scan.color import Color, RGB

FloatPosition = tuple[float, float]


# TODO: rewrite this using a class.


@dataclass
class RectangularShape:
    start: FloatPosition
    end: Optional[FloatPosition] = None
    color: RGB = Color.red
    thickness: int = 2
    fill: bool = False


class ArrayViewer:
    """`ArrayViewer` is used to display pictures annotated with colored rectangles, mainly for debugging.

    The picture to be displayed must be given as a numpy array.

    Parameters:
    `array` is an array containing the image data (image must be gray mode,
    each pixel represented by a float from 0 (black) to 1 (white)).

    Example:

        >> viewer = ArrayViewer(array)
        >> viewer.add_rectangle((2, 5), (10, 15), color=Color.red, thickness=4)
        >> viewer.add_rectangle((10, 10), (30, 20), color=Color.blue, fill=True)
        >> viewer.display()

    The annotated picture can be displayed using `.display()` methode.

    Use `.clear()` method to remove all annotations.

    NOTA:
    - `feh` must be installed.
      On Ubuntu/Debian: sudo apt-get install feh
    - Left-dragging the picture with mouse inside feh removes blurring/anti-aliasing,
      making visual debugging a lot easier.
    """

    _array: Optional[ndarray] = None
    _pic: Optional[Image.Image] = None

    def __init__(self, array: ndarray = None):
        self._shapes: list[RectangularShape] = []
        if array is not None:
            self.array = array

    @property
    def array(self) -> ndarray | None:
        return self._array

    @array.setter
    def array(self, array: ndarray) -> None:
        self._array = array
        self._shapes.clear()

    def add_area(
        self,
        start: FloatPosition,
        end: FloatPosition = None,
        color: RGB = Color.red,
        thickness: int = 2,
        fill: bool = False,
    ) -> None:
        """
        Annotate the image with a colored rectangle.

        Parameters:
            `start`: a couple of coordinates describing one corner of the rectangle.
            `end`: the opposite corner of the rectangle.
            `color`: the color of the rectangle (both the border and the interior if fill is true)
            `thickness`: the thickness of the border
            `fill`: if true, fill the rectangle.

        The color can be an attribute of the `Color` class (like `Color.red`), for common color's names,
        or a RGB tuple ([0-255], [0-255], [0-255]).

        """
        self._shapes.append(RectangularShape(start, end, color=color, thickness=thickness, fill=fill))

    def add_rectangle(
        self,
        start: FloatPosition,
        width: int,
        height: int,
        color: RGB = Color.red,
        thickness: int = 2,
        fill: bool = False,
    ) -> None:
        i, j = start
        self.add_area(start, (i + width, j + height), color=color, thickness=thickness, fill=fill)

    def add_square(
        self,
        start: FloatPosition,
        size: int,
        color: RGB = Color.red,
        thickness: int = 2,
        fill: bool = False,
    ) -> None:
        self.add_rectangle(start, size, size, color=color, thickness=thickness, fill=fill)

    def clear(self):
        """Clear all previous stored annotations."""
        self._shapes.clear()

    def _draw_rectangles(self) -> None:
        if self.array is not None:
            self._pic = Image.fromarray((255 * self.array).astype(int8)).convert("RGB")
            for rectangle in self._shapes:
                self._draw_rectangle(rectangle)

    def _draw_rectangle(self, rectangle: RectangularShape) -> None:
        if self.array is None:
            return
        height, width = self.array.shape
        i1, j1 = rectangle.start
        i2, j2 = rectangle.end or rectangle.start
        if i2 is None:
            i2 = height - 1
        if j2 is None:
            j2 = width - 1
        imin, imax = int(max(min(i1, i2), 0)), int(min(max(i1, i2), height - 1))
        jmin, jmax = int(max(min(j1, j2), 0)), int(min(max(j1, j2), width - 1))
        assert 0 <= imin <= imax < height and 0 <= jmin <= jmax < width

        color = rectangle.color
        thickness = rectangle.thickness
        assert self._pic is not None
        pix: Any = self._pic.load()  # type:ignore

        if rectangle.fill:
            for i in range(imin, imax + 1):
                for j in range(jmin, jmax + 1):
                    pix[j, i] = color
        else:
            # left and right sides of rectangle
            for i in range(imin, imax + 1):
                for j in range(jmin, jmin + thickness):
                    pix[j, i] = color
                for j in range(jmax + 1 - thickness, jmax + 1):
                    pix[j, i] = color
            # top and bottom sides of rectangle
            for j in range(jmin, jmax + 1):
                for i in range(imin, imin + thickness):
                    pix[j, i] = color
                for i in range(imax + 1 - thickness, imax + 1):
                    pix[j, i] = color

    @overload
    def display(self, wait: Literal[True] = True) -> subprocess.CompletedProcess:
        """Function signature when wait is True."""

    @overload
    def display(self, wait: Literal[False]) -> subprocess.Popen:
        """Function signature when wait is False."""

    def display(self, wait: bool = True) -> subprocess.CompletedProcess | subprocess.Popen:
        if self.array is None:
            raise RuntimeError("No picture to display.")
        self._draw_rectangles()
        if subprocess.call(["which", "feh"]) != 0:
            raise RuntimeError(
                "The `feh` command is not found, please " "install it (`sudo apt install feh` on Ubuntu)."
            )
        with tempfile.TemporaryDirectory() as tmpdirname:
            path = join(tmpdirname, "test.png")
            assert self._pic is not None
            self._pic.save(path)
            process: subprocess.CompletedProcess | subprocess.Popen
            if wait:
                process = subprocess.run(["feh", "-F", path])
            else:
                process = subprocess.Popen(["feh", "-F", path], stdin=subprocess.DEVNULL)
            input("-- pause --\n")
            return process


def color2debug(
    array: ndarray,
    from_: FloatPosition = None,
    to_: FloatPosition = None,
    color: RGB = Color.red,
    thickness: int = 2,
    fill=False,
    wait=True,
):
    """Display picture with a red (by default) rectangle for debugging.

    Parameters:
        `array`: an array containing the image data (image must be gray mode,
        each pixel represented by a float from 0 (black) to 1 (white)).
        `from_`: represent one corner of the red rectangle.
        `to_`: represent opposite corner of the red rectangle.
        `color`: color given as a RGB tuple ([0-255], [0-255], [0-255]).
        `thickness`: the thickness of the border
        `fill`: indicates if the rectangle should be filled.

    Usage: color2debug((0,0), (200,10), color=(255, 0, 255))

    NOTA:
    - `feh` must be installed.
      On Ubuntu/Debian: sudo apt-get install feh
    - Left-dragging the picture with mouse inside feh removes blurring/anti-aliasing,
      making visual debugging a lot easier.
    """
    viewer = ArrayViewer(array)
    if from_ is not None:
        viewer.add_area(from_, to_, color=color, thickness=thickness, fill=fill)
    viewer.display(wait=wait)
