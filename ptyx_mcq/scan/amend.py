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
from ..tools.config_parser import DocumentId, OriginalQuestionNumber


# if TYPE_CHECKING:
#     from ptyx_mcq.scan.scanner import MCQPictureParser


def amend_all(data_storage: DataStorage) -> None:
    """Amend all generated documents, adding the scores and indicating the correct answers."""
    max_score = data_storage.config.max_score
    assert max_score is not None
    N = len(data_storage.data)
    for i, (doc_id, doc_data) in enumerate(data_storage.data.items(), start=1):
        print(f"Generating the amended pdf files: {i}/{N}...", end="\r")
        amend_doc(doc_data, doc_id, max_score, data_storage)
    print("Generating the amended pdf files: OK" + len(f"{N}/{N}...") * " ")


def amend_doc(
    doc_data: DocumentData, doc_id: DocumentId, max_score: float, data_storage: DataStorage
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
            i, j = top_left_positions[q]
            _write_score(draw, (i, j - 2 * size), earn, size)
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
    _write_score(draw, (2 * size, 4 * size), f"{doc_data['score']:g}/{max_score:g}", 2 * size)
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


def _write_score(draw: ImageDraw.ImageDraw, pos: Pixel, earn: float | str, size: int) -> None:
    i, j = pos
    fnt = ImageFont.truetype("FreeSerif.ttf", int(0.7 * size))
    if isinstance(earn, float):
        earn = f"{earn:g}"
    draw.text((j, i), earn, font=fnt, fill=Color.red)
