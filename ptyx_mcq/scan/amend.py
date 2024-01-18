#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 29 14:49:37 2019

@author: nicolas
"""
from collections.abc import Generator
from itertools import chain
from os.path import join

# from typing import TYPE_CHECKING

from PIL import ImageDraw, ImageFont
from PIL.Image import Image
from ptyx_mcq.scan.data_handler import DataHandler
from .document_data import DocumentData

from .types_declaration import Pixel
from .color import Color, RGB
from ..tools.config_parser import DocumentId, OriginalQuestionNumber, QuestionNumberOrDefault


# if TYPE_CHECKING:
#     from ptyx_mcq.scan.scanner import MCQPictureParser


def amend_all(data_storage: DataHandler) -> None:
    """Amend all generated documents, adding the scores and indicating the correct answers."""
    cfg = data_storage.config
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
    max_score = data_storage.config.max_score
    assert isinstance(max_score, (float, int)), repr(max_score)
    N = len(data_storage.data)
    for i, (doc_id, doc_data) in enumerate(data_storage.data.items(), start=1):
        print(f"Generating the amended pdf files: {i}/{N}...", end="\r")
        amend_doc(doc_data, doc_id, max_score, max_score_per_question, data_storage)
    print("Generating the amended pdf files: OK" + len(f"{N}/{N}...") * " ")


def amend_doc(
    doc_data: DocumentData,
    doc_id: DocumentId,
    max_score: float,
    max_score_per_question: dict[QuestionNumberOrDefault, float],
    data_storage: DataHandler,
) -> None:
    correct_answers = data_storage.correct_answers[doc_id]
    neutralized_answers = data_storage.neutralized_answers[doc_id]
    pics = {}
    for page, page_data in doc_data.pages.items():
        top_left_positions: dict[OriginalQuestionNumber, Pixel] = {}
        # Convert to RGB picture.
        pic = data_storage.get_pic(doc_id, page).convert("RGB")
        if not page_data.positions:
            # The last page of the MCQ may be empty.
            # `float('+inf')` is used to ensure
            # it will be the last page when sorting.
            pics[float("+inf")] = pic
            continue
        # Drawing context
        draw = ImageDraw.Draw(pic)
        size = page_data.cell_size
        for (q, a), pos in page_data.positions.items():
            checked = a in page_data.answered[q]
            if a in neutralized_answers[q]:
                correct = None
            else:
                correct = a in correct_answers[q]
            _correct_checkboxes(draw, pos, checked, correct, size)
            if q in top_left_positions:
                i0, j0 = top_left_positions[q]
                i, j = pos
                top_left_positions[q] = (min(i, i0), min(j, j0))
            else:
                top_left_positions[q] = pos
        for q in top_left_positions:
            earn = doc_data.score_per_question[q]
            maximum = max_score_per_question.get(q, max_score_per_question["default"])
            assert isinstance(maximum, (float, int)), repr(maximum)
            i, j = top_left_positions[q]
            _write_score(draw, (i, j - 2 * size), earn, maximum, size)
        # We will now sort pages.
        # For that, we use questions numbers: the page which displays
        # the smaller questions numbers is the first one, and so on.
        # However, be careful to use displayed questions numbers,
        # since `q` is the question number *before shuffling*.
        q_num = page_data.questions_nums_conversion[q]
        pics[q_num] = pic
        # Sort pages now.
    pages: list[Image]
    _, pages = zip(*sorted(pics.items()))  # type: ignore
    draw = ImageDraw.Draw(pages[0])
    _write_score(draw, (2 * size, 4 * size), doc_data.score, max_score, 2 * size)
    pages[0].save(
        join(data_storage.dirs.pdf, f"{doc_data.name}-{doc_id}.pdf"),
        save_all=True,
        append_images=pages[1:],
    )


def _correct_checkboxes(
    draw: ImageDraw.ImageDraw, pos: Pixel, checked: bool, correct: bool | None, size: int
) -> None:
    i, j = pos
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
