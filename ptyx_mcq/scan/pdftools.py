#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 23 22:54:07 2020

@author: nicolas
"""

from pathlib import Path
from shutil import rmtree

import fitz  # type: ignore

PIC_EXTS = (".jpg", ".jpeg", ".png")


def extract_pdf_pictures(pdf_file: Path, dest: Path) -> None:
    """Clear `dest` folder, then extract all pages of the pdf files inside."""
    rmtree(dest, ignore_errors=True)
    dest.mkdir()

    page: fitz.Page
    doc = fitz.Document(pdf_file)
    for i, page in enumerate(doc.pages()):
        # Extract picture if the page contains only a picture (this is quite fast).
        if _contain_only_a_single_image(page):
            xref: int = page.get_images()[0][0]
            img_info = doc.extract_image(xref)
            ext = img_info["ext"].lower()
            if f".{ext}" in PIC_EXTS:
                # This is a known format, proceed with extraction.
                (dest / f"{i:03d}.{ext}").write_bytes(img_info["image"])
                continue
        # In all other cases, we'll have to rasterize the whole page and save it as a JPG picture
        # (unfortunately, this is much slower than a simple extraction).
        page.get_pixmap(dpi=200, colorspace=fitz.Colorspace(fitz.CS_GRAY)).save(dest / f"{i:03d}.jpg")


def _contain_only_a_single_image(page: fitz.Page) -> bool:
    """Test if the page contains only a single picture."""
    return (
        len(page.get_images()) == 1
        and len(page.get_drawings()) == 0
        and len(page.get_textpage().extractBLOCKS()) == 0
    )


def number_of_pages(pdf_path: Path) -> int:
    """Return the number of pages of the pdf."""
    return sum(1 for page in fitz.Document(pdf_path).pages())
