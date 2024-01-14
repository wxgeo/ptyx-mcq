from dataclasses import dataclass
from typing import Sequence

from numpy import ndarray

from ptyx_mcq.scan.color import RGB, Color


# --------------------------
#         POSITIONS
# ==========================

Pixel = tuple[int, int]
FloatPosition = tuple[float, float]


# --------------------------
#          FIGURES
# ==========================


@dataclass(kw_only=True)
class Shape:
    """Base class for all data classes providing information for figures.

    This is used intensively for debugging, but also to pass information
    about detected figures between functions.
    """

    color: RGB = Color.red
    thickness: int = 2
    fill: bool = False


@dataclass
class Rectangle(Shape):
    position: Pixel
    width: int
    height: int | None = None

    def __post_init__(self):
        if self.height is None:
            self.height = self.width

    @property
    def end(self) -> Pixel:
        assert self.height is not None
        return self.position[0] + self.height, self.position[1] + self.width


@dataclass
class Area(Shape):
    start: Pixel
    end: Pixel


# --------------------------
#           ERRORS
# ==========================


class CalibrationError(RuntimeError):
    """Error raised if calibration failed."""

    def __init__(
        self,
        *args,
        details: Sequence[Shape] | None = None,
        matrix: ndarray | None = None,
    ):
        super().__init__(*args)
        self.details: list[Shape] = [] if details is None else list(details)
        self.matrix = matrix


class MissingSquare(CalibrationError):
    """Error raised when one of the calibration squares was not found in one of the corners."""


class CalibrationSquaresNotFound(CalibrationError):
    """Error raised when the calibration squares in the four corners of the page are not found."""


class IdBandNotFound(CalibrationError):
    """Error raised when the ID band on the top of the page is not found."""
