import subprocess
import tempfile
from os.path import join
from typing import overload, Literal, TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    # noinspection PyProtectedMember
    from PIL._imaging import PixelAccess
from numpy import ndarray, int8

from ptyx_mcq.tools.colors import Color, RGB
from ptyx_mcq.scan.picture_analyze.types_declaration import (
    Shape,
    Rectangle,
    Area,
    Line,
    Pixel,
    Col,
    Row,
)


class ImageViewer:
    """`ImageViewer` is used to display pictures annotated with colored rectangles, mainly for debugging.

    The picture to be displayed must be given as a numpy array.

    Parameters:
    `array` is an array containing the image data (image must be gray mode,
    each pixel represented by a float from 0 (black) to 1 (white)).

    Example:

        >> viewer = ImageViewer(array=array)
        >> viewer.add_rectangle((2, 5), (10, 15), color=Color.red, thickness=4)
        >> viewer.add_rectangle((10, 10), (30, 20), color=Color.blue, fill=True)
        >> viewer.display()

    The annotated picture can be displayed using `.display()` methode.

    Use `.clear()` method to remove all annotations.

    NOTA:
    - `feh` must be installed.
      On Ubuntu/Debian: sudo apt-get install feh
    - Left-dragging the picture with mouse inside feh removes blurring/antialiasing,
      making visual debugging a lot easier.
    """

    # TODO:
    #  Accept either an array, or directly a PIL image.
    #  If it is an array, convert it directly to a PIL image.
    #  (There is probably no need to store the array, just store the PIL image.)
    #  A methods set_array() should be created too, replacing property getter and setter.

    def __init__(self, *debug_info: Shape, array: ndarray = None, image: Image.Image = None):
        if image is None:
            if array is None:
                raise ValueError("Argument `array` or `image` must be specified.")
            self.image: Image.Image = self._get_image_from_array(array)
        else:
            if array is not None:
                raise ValueError("Arguments `array` and `image` must not be both specified.")
            self.image = image
        self._shapes: list[Shape] = []
        self.add_shapes(*debug_info)

    @staticmethod
    def _get_image_from_array(array: ndarray) -> Image.Image:
        return Image.fromarray((255 * array).astype(int8)).convert("RGB")

    def add_shapes(self, *shapes: Shape) -> None:
        for shape in shapes:
            if isinstance(shape, Rectangle):
                self.add_rectangle(
                    start=shape.position, width=shape.width, height=shape.height, color=shape.color
                )
            elif isinstance(shape, Area):
                self.add_area(start=shape.start, end=shape.end, color=shape.color)
            else:
                raise NotImplementedError(f"Unrecognized data: {shape!r}.")

    def add_area(
        self,
        start: Pixel,
        end: Pixel,
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
        or an RGB tuple ([0-255], [0-255], [0-255]).

        """
        self._shapes.append(Area(start, end, color=color, thickness=thickness, fill=fill))

    def add_rectangle(
        self,
        start: Pixel,
        width: int,
        height: int = None,
        color: RGB = Color.red,
        thickness: int = 2,
        fill: bool = False,
    ) -> None:
        if height is None:
            height = width
        i, j = start
        self.add_area(start, (Row(i + width), Col(j + height)), color=color, thickness=thickness, fill=fill)

    def add_line(self, start: Pixel, end: Pixel, color: RGB = Color.red, thickness: int = 2):
        """
        Annotate the image with a colored line.

        Drawing algorithm is very basic (no antialiasing...), but it is enough for debugging.
        """
        self._shapes.append(Line(start, end, color=color, thickness=thickness))

    def clear(self):
        """Clear all previous stored annotations."""
        self._shapes.clear()

    def _draw_rectangles(self) -> None:
        for shape in self._shapes:
            if isinstance(shape, (Area, Rectangle)):
                self._draw_rectangle(shape)
            elif isinstance(shape, Line):
                self._draw_line(shape.start, shape.end, shape.color, shape.thickness)
            else:
                raise NotImplementedError(f"Unknown shape type: {shape} ({type(shape)}).")

    def _set_pixel(self, pixels: "PixelAccess", i: int, j: int, color: RGB) -> None:
        if 0 <= i < self.image.height and 0 <= j < self.image.width:
            pixels[j, i] = color

    def _draw_rectangle(self, rectangle: Rectangle | Area) -> None:
        i1, j1 = rectangle.start
        i2, j2 = rectangle.end or rectangle.start
        if i2 is None:
            i2 = self.image.height - 1
        if j2 is None:
            j2 = self.image.width - 1
        i1 = Row(int(i1))
        i2 = Row(int(i2))
        j1 = Col(int(j1))
        j2 = Col(int(j2))
        if i2 < i1:
            i1, i2 = i2, i1
        if j2 < j1:
            j1, j2 = j2, j1

        color = rectangle.color
        thickness = rectangle.thickness
        pixels: "PixelAccess" = self.image.load()

        if rectangle.fill:
            for i in range(i1, i2 + 1):
                for j in range(j1, j2 + 1):
                    self._set_pixel(pixels, i, j, color)
        else:
            # left and right sides of rectangle
            for i in range(i1, i2 + 1):
                for j in range(j1, j1 + thickness):
                    self._set_pixel(pixels, i, j, color)
                for j in range(j2 + 1 - thickness, j2 + 1):
                    self._set_pixel(pixels, i, j, color)
            # top and bottom sides of rectangle
            for j in range(j1, j2 + 1):
                for i in range(i1, i1 + thickness):
                    self._set_pixel(pixels, i, j, color)
                for i in range(i2 + 1 - thickness, i2 + 1):
                    self._set_pixel(pixels, i, j, color)

    def _draw_line_in_vertical_mode(self, i1: Row, i2: Row, j1: Col, j2: Col, color: RGB = Color.red):
        pixels = self.image.load()
        if i2 == i1:
            raise ValueError("Horizontal line can't be drawn in vertical mode!")
        # Affine function : i -> j = a * i + b
        a = (j2 - j1) / (i2 - i1)
        b = j1 - a * i1
        for i in range(i1, i2):
            self._set_pixel(pixels, i, int(round(a * i + b)), color)

    def _draw_line_in_horizontal_mode(self, i1: Row, i2: Row, j1: Col, j2: Col, color: RGB = Color.red):
        pixels = self.image.load()
        if j2 == j1:
            raise ValueError("Vertical line can't be drawn in horizontal mode!")
        # Affine function : j -> i = a * j + b
        a = (i2 - i1) / (j2 - j1)
        b = i1 - a * j1
        for j in range(j1, j2):
            self._set_pixel(pixels, round(a * j + b), j, color)

    def _draw_line(self, start: Pixel, end: Pixel, color: RGB = Color.red, thickness: int = 2):
        i1, j1 = start
        i2, j2 = end
        if start == end:
            return
        # Try to center the thickened line around the axis "start - end".
        shift_range = range(_start := round(-(thickness - 1) / 2), _start + thickness)
        if abs(i2 - i1) > abs(j2 - j1):
            # The line is more vertical than horizontal.
            for k in shift_range:
                self._draw_line_in_vertical_mode(i1, i2, Col(j1 + k), Col(j2 + k), color)
        else:
            for k in shift_range:
                self._draw_line_in_horizontal_mode(Row(i1 + k), Row(i2 + k), j1, j2, color)

    @overload
    def display(self, wait: Literal[True] = True) -> subprocess.CompletedProcess:
        """Function signature when wait is True."""

    @overload
    def display(self, wait: Literal[False]) -> subprocess.Popen:
        """Function signature when wait is False."""

    def display(self, wait: bool = True) -> subprocess.CompletedProcess | subprocess.Popen:
        self._draw_rectangles()
        if subprocess.call(["which", "feh"]) != 0:
            raise RuntimeError(
                "The `feh` command is not found, please " "install it (`sudo apt install feh` on Ubuntu)."
            )
        with tempfile.TemporaryDirectory() as tmpdir_name:
            path = join(tmpdir_name, "test.png")
            self.image.save(path)
            process: subprocess.CompletedProcess | subprocess.Popen
            if wait:
                process = subprocess.run(["feh", "-F", path])
            else:
                process = subprocess.Popen(["feh", "-F", path], stdin=subprocess.DEVNULL)
            input("-- pause --\n")
            return process


def color2debug(
    array: ndarray,
    from_: Pixel = None,
    to_: Pixel = None,
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
        `color`: color given as an RGB tuple ([0-255], [0-255], [0-255]).
        `thickness`: the thickness of the border
        `fill`: indicates if the rectangle should be filled.

    Usage: color2debug((0,0), (200,10), color=(255, 0, 255))

    NOTA:
    - `feh` must be installed.
      On Ubuntu/Debian: sudo apt-get install feh
    - Left-dragging the picture with mouse inside feh removes blurring/antialiasing,
      making visual debugging a lot easier.
    """
    viewer = ImageViewer(array=array)
    if from_ is not None and to_ is not None:
        viewer.add_area(from_, to_, color=color, thickness=thickness, fill=fill)
    # noinspection PyTypeChecker
    viewer.display(wait=wait)
