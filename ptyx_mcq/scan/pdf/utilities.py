#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 23 22:54:07 2020

@author: nicolas
"""
from pathlib import Path

import pymupdf  # type: ignore


def number_of_pages(pdf_path: Path) -> int:
    """Return the number of pages of the pdf."""
    return len(pymupdf.Document(pdf_path))
