from dataclasses import dataclass
from enum import Enum
from typing import Literal, Iterator, Sequence

from numpy import ndarray

from ptyx_mcq.scan.color import RGB, Color


# --------------------------
#         POSITIONS
# ==========================

Pixel = tuple[int, int]
FloatPosition = tuple[float, float]


# --------------------------
#          CORNERS
# ==========================

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


# --------------------------
#          FIGURES
# ==========================


@dataclass(kw_only=True)
class FigureInfo:
    """Base class for all data classes providing information for figures.

    This is used intensively for debugging, but also to pass information
    about detected figures between functions.
    """

    color: RGB = Color.red
    thickness: int = 2
    fill: bool = False


@dataclass
class RectangleInfo(FigureInfo):
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
class AreaInfo(FigureInfo):
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
        details: Sequence[FigureInfo] | None = None,
        matrix: ndarray | None = None,
    ):
        super().__init__(*args)
        self.details: list[FigureInfo] = [] if details is None else list(details)
        self.matrix = matrix


class MissingSquare(CalibrationError):
    """Error raised when one of the calibration squares was not found in one of the corners."""


class CalibrationSquaresNotFound(CalibrationError):
    """Error raised when the calibration squares in the four corners of the page are not found."""


class IdBandNotFound(CalibrationError):
    """Error raised when the ID band on the top of the page is not found."""
