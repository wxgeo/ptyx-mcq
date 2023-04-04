#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 29 14:49:37 2019

@author: nicolas
"""
from os.path import join

# from typing import TYPE_CHECKING

from PIL import ImageDraw, ImageFont
from PIL.Image import Image
from ptyx_mcq.scan.data_manager import DataStorage
from .document_data import DocumentData

from .square_detection import Pixel
from .color import Color
from ..tools.config_parser import DocumentId, OriginalQuestionNumber, QuestionNumberOrDefault


# if TYPE_CHECKING:
#     from ptyx_mcq.scan.scanner import MCQPictureParser


def amend_all(data_storage: DataStorage) -> None:
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
    data_storage: DataStorage,
) -> None:
    correct_answers = data_storage.correct_answers[doc_id]
    neutralized_answers = data_storage.neutralized_answers[doc_id]
    pics = {}
    for page, page_data in doc_data["pages"].items():
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
            earn = doc_data["score_per_question"][q]
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
    _write_score(draw, (2 * size, 4 * size), doc_data["score"], max_score, 2 * size)
    pages[0].save(
        join(data_storage.dirs.pdf, f"{doc_data['name']}-{doc_id}.pdf"),
        save_all=True,
        append_images=pages[1:],
    )


def _correct_checkboxes(
    draw: ImageDraw.ImageDraw, pos: Pixel, checked: bool, correct: bool | None, size: int
) -> None:
    i, j = pos
    margin = size // 2
    # Draw a blue square around the box (for debugging purpose).
    draw.rectangle((j, i, j + size, i + size), outline=Color.green)
    red = Color.red
    if correct is None:
        draw.rectangle((j, i, j + size, i + size), outline=Color.orange)
    elif checked and not correct:
        # Circle checkbox with red pen.
        try:
            draw.ellipse((j - margin, i - margin, j + size + margin, i + size + margin), width=2, outline=red)
        except TypeError:
            # old PIL versions (<5.1.3)
            draw.ellipse((j - margin, i - margin, j + size + margin, i + size + margin), outline=red)
    elif not checked and correct:
        # Check (cross) the box (with red pen).
        draw.line((j, i, j + size - 1, i + size - 1), fill=red, width=2)
        draw.line((j + size - 1, i, j, i + size - 1), fill=red, width=2)


def _write_score(draw: ImageDraw.ImageDraw, pos: Pixel, earn: float, maximum: float, size: int) -> None:
    i, j = pos
    fnt = ImageFont.truetype("FreeSerif.ttf", int(0.7 * size))
    draw.text((j, i), f"{round(earn, 2):g}/{round(maximum, 2):g}", font=fnt, fill=Color.red)
