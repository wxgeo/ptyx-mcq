"""
This module contains tools to check data completeness, ie:
    - all documents are complete (no missing page)
    - there are no duplicates (each document/page must appear only once)

Main classes:
    - `IntegrityChecker`: report integrity problems.
    - `IntegrityIssuesFixer`: fix reported issues (if possible), with user help.

The function `report_integrity_issues()`

"""

from typing import Literal

from PIL import Image, ImageDraw

from ptyx_mcq.scan.data import Picture
from ptyx_mcq.scan.data.conflict_gestion.integrity_check.fix import (
    AbstractIntegrityIssuesFixer,
)
from ptyx_mcq.scan.picture_analyze.image_viewer import ImageViewer
from ptyx_mcq.tools.colors import Color
from ptyx_mcq.tools.misc import copy_docstring


class ClIntegrityIssuesFixer(AbstractIntegrityIssuesFixer):
    """Command line integrity's issues fixer.

    Interact with the user to fix previously found problems.

    Main method is `run()`.
    """

    @copy_docstring(AbstractIntegrityIssuesFixer.select_version)
    def select_version(self, pic1: Picture, pic2: Picture) -> Literal[1, 2]:
        print("Choose which version to keep:")
        input("-- Press ENTER --")
        action = ""

        while action not in ("1", "2"):
            self._display_duplicates(pic1, pic2)
            print("What must we do ?")
            print("- Keep only 1st one (1)")
            print("- Keep only 2nd one (2)")
            print("If you want to see the pictures again, juste press ENTER.")
            action = input("Answer: ")

        return 1 if action == "1" else 2

    def _display_duplicates(self, pic1: Picture, pic2: Picture) -> None:
        # im1 = Image.open(pic_path1)
        # im2 = Image.open(pic_path2)
        im1 = pic1.as_image()
        im2 = pic2.as_image()
        dst = Image.new("RGB", (im1.width + im2.width, height := min(im1.height, im2.height)))
        dst.paste(im1, (0, 0))
        dst.paste(im2, (im1.width, 0))
        ImageDraw.Draw(dst).line([(im1.width, 0), (im1.width, height)], fill=Color.blue)

        ImageViewer(image=dst).display()
