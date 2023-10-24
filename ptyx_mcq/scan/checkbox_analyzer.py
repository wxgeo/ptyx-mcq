from functools import partial

from numpy import ndarray

from ptyx_mcq.scan.document_data import DetectionStatus
from ptyx_mcq.scan.square_detection import test_square_color
from ptyx_mcq.tools.config_parser import OriginalAnswerNumber, OriginalQuestionNumber


def eval_checkbox_color(checkbox: ndarray, margin: int = 0) -> float:
    """Return an indicator of blackness, which is a float in range (0, 1).
    The bigger the float returned, the darker the square.

    This indicator is useful to compare several squares, and find the blacker one.
    Note that the core of the square is considered the more important part to assert
    blackness.
    """
    height, width = checkbox.shape
    assert width == height, (width, height)
    if width <= 2 * margin:
        raise ValueError("Square too small for current margins !")
    # Warning: pixels outside the sheet shouldn't be considered black !
    # Since we're doing a sum, 0 should represent white and 1 black,
    # so as if a part of the square is outside the sheet, it is considered
    # white, not black ! This explains the `1 - m[...]` below.
    square = 1 - checkbox[margin : width - margin, margin : width - margin]
    return square.sum() / (width - margin) ** 2


def analyze_checkboxes(
    checkboxes: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], ndarray],
) -> dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], DetectionStatus]:
    detection_status: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], DetectionStatus] = {}
    # Store blackness of checkboxes, to help detect false positives
    # and false negatives.
    blackness = {}
    core_blackness = {}

    for (q, a), checkbox in checkboxes.items():
        # `q` and `a` are real questions and answers numbers, that is,
        # questions and answers numbers before shuffling.
        # The following will be used to detect false positives or false negatives later.
        blackness[(q, a)] = eval_checkbox_color(checkbox, margin=4)
        core_blackness[(q, a)] = eval_checkbox_color(checkbox, margin=7)
        # `q0` and `a0` keep track of apparent question and answers numbers,
        # which will be used on output to make debugging easier.

    # Various metrics used to compare the blackness of a checkbox with the other ones.
    floor = max(0.2 * max(blackness.values()), max(blackness.values()) - 0.4)
    upper_floor = max(0.2 * max(blackness.values()), max(blackness.values()) - 0.3)
    core_floor = max(0.2 * max(core_blackness.values()), max(core_blackness.values()) - 0.4)
    upper_core_floor = max(0.2 * max(core_blackness.values()), max(core_blackness.values()) - 0.3)
    # Add 0.03 to 1.5*mean, in case mean is almost 0.
    ceil = 1.5 * sum(blackness.values()) / len(blackness) + 0.02
    core_ceil = 1.2 * sum(core_blackness.values()) / len(core_blackness) + 0.01

    for (q, a), checkbox in checkboxes.items():
        test_square = partial(test_square_color, m=checkbox, i=0, j=0, size=checkbox.shape[0], margin=5)

        if (
            test_square(proportion=0.2, gray_level=0.65)
            # ~ test_square_color(m, i + 3, j + 3, cell_size - 7, proportion=0.4, gray_level=0.75) or
            # ~ test_square_color(m, i + 3, j + 3, cell_size - 7, proportion=0.45, gray_level=0.8) or
            or test_square(proportion=0.4, gray_level=0.90)
            or test_square(proportion=0.6, gray_level=0.95)
        ):
            if test_square(proportion=0.4, gray_level=0.9):
                detection_status[(q, a)] = DetectionStatus.CHECKED
            else:
                detection_status[(q, a)] = DetectionStatus.PROBABLY_CHECKED
        else:
            if test_square(proportion=0.2, gray_level=0.95) and blackness[(q, a)] > upper_floor:
                detection_status[(q, a)] = DetectionStatus.PROBABLY_UNCHECKED
            else:
                detection_status[(q, a)] = DetectionStatus.UNCHECKED

    def marked_as_checked(q_: OriginalQuestionNumber, a_: OriginalAnswerNumber) -> bool:
        return DetectionStatus.seems_checked(detection_status[(q_, a_)])

    # Test now for false negatives and false positives.

    # First, try to detect false negatives.
    # If a checkbox considered unchecked is notably darker than the others,
    # it is probably checked after all (and if not, it will most probably be caught
    # with false positives in next section).
    for q, a in blackness:  # pylint: disable=dict-iter-missing-items
        if not marked_as_checked(q, a) and (blackness[(q, a)] > ceil or core_blackness[(q, a)] > core_ceil):
            print("False negative detected", (q, a))
            # This is probably a false negative, but we'd better verify manually.
            detection_status[(q, a)] = DetectionStatus.PROBABLY_CHECKED

    # If a checkbox is tested as checked, but is much lighter than the darker one,
    # it is very probably a false positive.
    for q, a in blackness:  # pylint: disable=dict-iter-missing-items
        if marked_as_checked(q, a) and (
            blackness[(q, a)] < upper_floor or core_blackness[(q, a)] < upper_core_floor
        ):
            if blackness[(q, a)] < floor or core_blackness[(q, a)] < core_floor:
                print("False positive detected", (q, a), blackness[(q, a)], max(blackness.values()))
                # This is probably a false positive, but we'd better verify manually.
                detection_status[(q, a)] = DetectionStatus.PROBABLY_UNCHECKED
            else:
                # Probably note a false positive, but we should verify.
                detection_status[(q, a)] = DetectionStatus.PROBABLY_CHECKED

    return detection_status
