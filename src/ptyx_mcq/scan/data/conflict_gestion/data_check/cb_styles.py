"""
Styles used to display checkboxes, according to their status, for review.
"""

from ptyx_mcq.scan.data.questions import CbxState
from ptyx_mcq.tools.colors import Color, RGB


class CbxColors:
    default_colors: dict[CbxState, RGB] = {
        CbxState.CHECKED: Color.blue,
        CbxState.PROBABLY_CHECKED: Color.green,
        CbxState.PROBABLY_UNCHECKED: Color.magenta,
        CbxState.UNCHECKED: Color.pink,
    }
    reviewed_colors: dict[CbxState, RGB] = {
        CbxState.CHECKED: Color.cyan,
        CbxState.UNCHECKED: Color.red,
    }


class CbxThickness:
    default_thicknesses: dict[CbxState, int] = {
        CbxState.CHECKED: 2,
        CbxState.PROBABLY_CHECKED: 5,
        CbxState.PROBABLY_UNCHECKED: 5,
        CbxState.UNCHECKED: 2,
    }
    reviewed_thicknesses: dict[CbxState, int] = {
        CbxState.CHECKED: 5,
        CbxState.UNCHECKED: 5,
    }
