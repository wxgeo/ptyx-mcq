#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 29 14:49:37 2019

@author: nicolas
"""
from collections.abc import Generator
from itertools import chain
from multiprocessing import Pool
from os.path import join

# from typing import TYPE_CHECKING

from PIL import ImageDraw, ImageFont
from PIL.Image import Image
from ptyx_mcq.scan.data.questions import Answer

from ptyx_mcq.scan.data import ScanData
from ptyx_mcq.scan.data.documents import Document

from ptyx_mcq.scan.picture_analyze.types_declaration import Pixel, Line, Col
from ptyx_mcq.tools.colors import Color, RGB
from ptyx_mcq.tools.config_parser import OriginalQuestionNumber, QuestionNumberOrDefault, real2apparent


# if TYPE_CHECKING:
#     from ptyx_mcq.scan.scanner import MCQPictureParser


def amend_all(scan_data: ScanData) -> None:
    """Amend all generated documents, adding the scores and indicating the correct answers."""
    cfg = scan_data.config
    default_weight = cfg.weight["default"]
    assert isinstance(default_weight, (int, float))
    default_correct = cfg.correct["default"]
    assert isinstance(default_correct, (int, float))
    max_score_per_question: dict[QuestionNumberOrDefault, float] = {
        "default": default_weight * default_correct
    }
    for question in set(cfg.correct) | set(cfg.weight) - {"default"}:
        _max_score = cfg.weight.get(question, default_weight) * cfg.correct.get(question, default_correct)
        max_score_per_question[question] = _max_score

    # Global maximal score.
    # Note that the global maximal score can not be easily deduced from the dict `max_score_per_question`,
    # since this dict only include customized questions scores, and since many versions of the same question
    # may appear in the dict, but only one of those versions was included in each generated document.
    max_score = scan_data.config.max_score
    assert isinstance(max_score, (float, int)), repr(max_score)
    number_of_documents = len(scan_data.index)
    counter = 0

    def print_progression(_):
        nonlocal counter
        counter += 1
        print(f"Generating the amended pdf files: {counter}/{number_of_documents}...", end="\r")

    print(f"Generating the amended pdf files: 0/{number_of_documents}", end="\r")
    pool = Pool()
    for doc in scan_data:
        pool.apply_async(amend_doc, (doc, max_score_per_question), callback=print_progression)
    pool.close()
    # noinspection PyTestUnpassedFixture
    pool.join()

    print(
        "Generating the amended pdf files: OK" + len(f"{number_of_documents}/{number_of_documents}...") * " "
    )


# TODO: maybe restrict the data passed to amend_doc?
#  For now, each document contain references to all scan_data,
#  so there is *a lot* of data to pickle when using multiprocessing.
def amend_doc(doc: Document, max_score_per_question: dict[QuestionNumberOrDefault, float]) -> None:
    config = doc.scan_data.config
    max_score = config.max_score
    doc_id = doc.doc_id
    # max_score_per_question: dict[QuestionNumberOrDefault, float],
    # data_storage: ScanData,
    images = {}
    for page in doc:
        pic = page.pic
        top_left_positions: dict[OriginalQuestionNumber, Pixel] = {}
        # Convert to RGB picture.
        img = pic.as_image().convert("RGB")
        if not pic.questions:
            # The last page of the MCQ may be empty.
            # `float('+inf')` is used to ensure
            # it will be the last page when sorting.
            images[float("+inf")] = img
            continue
        # Drawing context
        draw = ImageDraw.Draw(img)
        size = pic.calibration_data.cell_size
        for q, question in pic.questions.items():
            for a, answer in question.answers.items():
                _correct_checkboxes(draw, answer, size)
                if q in top_left_positions:
                    i0, j0 = top_left_positions[q]
                    i, j = answer.position
                    top_left_positions[q] = (min(i, i0), min(j, j0))
                else:
                    top_left_positions[q] = answer.position
        for q in top_left_positions:
            earn = pic.questions[q].score
            maximum = max_score_per_question.get(q, max_score_per_question["default"])
            assert isinstance(maximum, (float, int)), repr(maximum)
            i, j = top_left_positions[q]
            _write_score(draw, (i, Col(j - 2 * size)), earn, maximum, size)
        # We will now sort pages.
        # For that, we use questions numbers: the page which displays
        # the smaller questions numbers is the first one, and so on.
        # However, be careful to use displayed questions numbers,
        # since `q` is the question number *before shuffling*.
        q_num = real2apparent(q, None, config, doc_id)
        images[q_num] = img
        # Sort pages now.
    pages: list[Image]
    _, pages = zip(*sorted(images.items()))  # type: ignore
    draw = ImageDraw.Draw(pages[0])
    _write_score(draw, (Line(2 * size), Col(4 * size)), doc.score, max_score, 2 * size)
    pages[0].save(
        join(doc.scan_data.dirs.pdf, f"{doc.student.name}-{doc_id}.pdf"),
        save_all=True,
        append_images=pages[1:],
    )


def _correct_checkboxes(draw: ImageDraw.ImageDraw, answer: Answer, size: int) -> None:
    i, j = pos = answer.position
    checked = answer.checked
    correct = answer.is_correct
    margin = size // 3
    # Draw a blue square around each checkbox.
    # The square's border should be solid if the box has been detected as checked, and dashed otherwise.
    if checked:
        draw.rectangle((j, i, j + size, i + size), outline=Color.blue)
    else:
        _draw_dashed_rectangle(draw, pos, size, color=Color.blue, color2=Color.white)
    red = Color.red
    if correct is None:
        draw.rectangle((j, i, j + size, i + size), outline=Color.orange)
    elif checked and not correct:
        # Circle checkbox with red pen.
        draw.ellipse((j - margin, i - margin, j + size + margin, i + size + margin), outline=red)
        # Strike through the checkbox too.
        draw.line([(j - margin, i + size + margin), (j + size + margin, i - margin)], width=2, fill=Color.red)
    elif not checked and correct:
        # Check (cross) the box (with red pen).
        draw.line((j, i, j + size - 1, i + size - 1), fill=red, width=2)
        draw.line((j + size - 1, i, j, i + size - 1), fill=red, width=2)


def _write_score(draw: ImageDraw.ImageDraw, pos: Pixel, earn: float, maximum: float, size: int) -> None:
    i, j = pos
    fnt = ImageFont.truetype("FreeSerif.ttf", int(0.7 * size))
    # Add 0.0 to result after rounding, to prevent negative zeros (-0.0).
    # (Don't use `:zn` formatter, since it will fail on integers!)
    draw.text((j, i), f"{round(earn, 2) + 0.0:n}/{round(maximum, 2):n}", font=fnt, fill=Color.red)


def _dash_generator(
    start: int, stop: int, plain_step: int, blank_step: int, invert=False
) -> Generator[int, None, None]:
    """Like range(), but skip blank intervals to generate dashes.

    Unlike range, stop value is included (if it is not in a blank interval).
    """
    n = start
    while n <= stop:
        if invert:
            n += plain_step
            for i in range(n, min(n + blank_step, stop)):
                yield i
            n += blank_step
        else:
            for i in range(n, min(n + plain_step, stop)):
                yield i
            n += plain_step + blank_step


def _draw_dotted_rectangle(draw: ImageDraw.ImageDraw, pos: Pixel, size: int, color: RGB) -> None:
    """Draw a rectangle with dotted line using PIL.

    Current implementation is very limited, line width in particular can not be changed.
    """
    i0, j0 = pos
    pixels = chain(
        ((j, i0 + i) for j in (j0, j0 + size) for i in range(0, size + 1, 2)),
        ((j0 + j, i) for i in (i0, i0 + size) for j in range(0, size + 1, 2)),
    )
    draw.point(list(pixels), fill=color)


def _draw_dashed_rectangle(
    draw: ImageDraw.ImageDraw,
    pos: Pixel,
    size: int,
    color: RGB,
    color2: RGB | None = None,
    plain: int = 4,
    blank: int = 4,
    _invert=False,
) -> None:
    """Draw a rectangle with dashed line using PIL.

    Current implementation is very limited, line width in particular can not be changed.
    """
    i0, j0 = pos
    pixels = chain(
        (
            (j, i)
            for j in (j0, j0 + size)
            for i in _dash_generator(i0, i0 + size, plain, blank, invert=_invert)
        ),
        (
            (j, i)
            for i in (i0, i0 + size)
            for j in _dash_generator(j0, j0 + size, plain, blank, invert=_invert)
        ),
    )
    draw.point(list(pixels), fill=color)
    if color2 is not None:
        _draw_dashed_rectangle(draw, pos, size, color=color2, plain=plain, blank=blank, _invert=True)
