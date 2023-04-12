#!/usr/bin/env python3
import csv
import subprocess
import tempfile
from math import inf
from pathlib import Path
from typing import Union, Literal, Optional

from ptyx_mcq.scan.amend import amend_all
from ptyx_mcq.scan.conflict_solver import ConflictSolver
from ptyx_mcq.scan.data_manager import DataStorage
from ptyx_mcq.scan.document_data import DocumentData, PicData, Page
from ptyx_mcq.scan.pdftools import PIC_EXTS
from ptyx_mcq.scan.scan_pic import (
    scan_picture,
    CalibrationError,
)
from ptyx_mcq.scan.scores_manager import ScoresManager
from ptyx_mcq.tools.config_parser import (
    StudentId,
    StudentName,
    DocumentId,
)
from ptyx_mcq.tools.io_tools import print_success, print_warning, ANSI_RESET, ANSI_GREEN


# -----------------------------------------
#                  Scan
#     Extract info from digitized documents
# -----------------------------------------
#    PTYX
#    Python LaTeX preprocessor
#    Copyright (C) 2009-2020  Nicolas Pourcelot
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


# File `compilation.py` is in ../.., so we have to "hack" `sys.path` a bit.
# script_path = dirname(abspath(sys._getframe().f_code.co_filename))
# sys.path.insert(0, join(script_path, '../..'))
# from ptyx.compilation import join_files, compile_latex

# from ..make.header import answers_and_score


class MissingQuestion(RuntimeError):
    """Error raised when some questions where not seen when scanning all data."""


class MissingConfigurationData(RuntimeError):
    """Error raised when some configuration data is missing."""


class MCQPictureParser:
    """Main class for parsing pdf files containing all the scanned MCQ."""

    def __init__(
        self,
        path: Union[str, Path],
        input_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        # Set `already_seen` will contain all seen (ID, page) couples.
        # It is used to catch a hypothetical scanning problem:
        # we have to be sure that the same page on the same test is not seen
        # twice.
        self.already_seen: set[tuple[DocumentId, Page]] = set()
        self.warnings = False
        self.data_storage = DataStorage(Path(path), input_dir=input_dir, output_dir=output_dir)
        self.scores_manager = ScoresManager(self)

    @property
    def config(self):
        return self.data_storage.config

    @property
    def data(self):
        return self.data_storage.data

    def _test_integrity(self) -> None:
        """For every test:
        - all pages must have been scanned,
        - all questions must have been seen."""
        questions_not_seen = {}
        pages_not_seen = {}
        ordering = self.config.ordering
        for doc_id in self.data:
            try:
                doc_ordering = ordering[doc_id]
            except KeyError:
                raise MissingConfigurationData(
                    f"No configuration data found for document #{doc_id}.\n"
                    "Maybe you recompiled the ptyx file in the while ?\n"
                    f"(Launching `mcq make -n {max(self.data)}` might fix it.)"
                )
            questions = set(doc_ordering["questions"])
            diff = questions - set(self.data[doc_id]["answered"])
            if diff:
                questions_not_seen[doc_id] = ", ".join(str(q) for q in diff)
            # All tests may not have the same number of pages, since
            # page breaking will occur at a different place for each test.
            pages = set(self.config.boxes[doc_id])
            diff = pages - set(self.data[doc_id]["pages"])
            if diff:
                pages_not_seen[doc_id] = ", ".join(str(p) for p in diff)
        if pages_not_seen:
            self._warn("= WARNING =")
            self._warn("Pages not seen:")
            for doc_id in sorted(pages_not_seen):
                self._warn(f"    • Test {doc_id}: page(s) {pages_not_seen[doc_id]}")
        if questions_not_seen:
            self._warn("=== ERROR ===")
            self._warn("Questions not seen !")
            for doc_id in sorted(questions_not_seen):
                self._warn(f"    • Test {doc_id}: question(s) {questions_not_seen[doc_id]}")

        if questions_not_seen:
            # Don't raise an error for pages not found (only a warning in log)
            # if all questions were found, this was probably empty pages.
            raise MissingQuestion("Questions not seen ! (Look at message above).")

    def _keep_previous_version(self, pic_data: PicData) -> bool:
        """Test if a previous version of the same page exist.

        If so, it probably means the page has been scanned twice, but it could
        also indicate a more serious problem (for example, tests with the same ID
        have been given to different students !).
        As a precaution, we should signal the problem to the user, and ask him
        what he wants to do.
        """
        doc_id = pic_data.doc_id
        p = pic_data.page

        # This page has never been seen before, everything is OK.
        if (doc_id, p) not in self.already_seen:
            self.already_seen.add((doc_id, p))
            return False

        # This is problematic: it seems like the same page has been seen twice.
        lastpic_path = pic_data.pic_path
        lastpic = self.data_storage.relative_pic_path(lastpic_path)
        firstpic_path = self.data[doc_id]["pages"][p].pic_path
        firstpic = self.data_storage.relative_pic_path(firstpic_path)
        assert isinstance(lastpic_path, str)
        assert isinstance(firstpic_path, str)

        self._warn(f"WARNING: Page {p} of test #{doc_id} seen twice " f'(in "{firstpic}" and "{lastpic}") !')
        action = None
        keys = ("name", "student_ID", "answered")
        if all(pic_data[key] == self.data[doc_id]["pages"][p][key] for key in keys):  # type: ignore
            # Same information found on the two pages, just keep one version.
            action = "f"
            self._warn("Both page have the same information, keeping only first one...")

        # We have a problem: this is a duplicate.
        # In other words, we have 2 different versions of the same page.
        # Ask the user what to do.
        while action not in ("f", "l"):
            print("What must we do ?")
            print("- See pictures (s)")
            print("- Keep only first one (f)")
            print("- Keep only last one (l)")

            action = input("Answer:")
            if action == "s":
                with tempfile.TemporaryDirectory() as tmpdirname:
                    path = Path(tmpdirname) / "test.png"
                    # https://stackoverflow.com/questions/39141694/how-to-display-multiple-images-in-unix-command-line
                    subprocess.run(["convert", firstpic_path, lastpic_path, "-append", str(path)], check=True)
                    subprocess.run(["feh", "-F", str(path)], check=True)
                    input("-- pause --")
        # We must memorize which version should be skipped in case user
        # launch scan another time.
        skipped_pic = firstpic if action == "l" else lastpic
        self.data_storage.store_skipped_pic(skipped_pic)

        if action == "l":
            # Remove first picture information.
            del self.data[doc_id]["pages"][p]
            self.data_storage.store_doc_data(firstpic.parent.name, doc_id, p)

        return action == "f"

    def generate_report(self) -> None:
        """Generate CSV files with some information concerning each student.

        Used mainly for debugging.
        """
        # Generate CSV file with ID and pictures names for all students.
        info_path = self.data_storage.files.infos
        info = [
            (
                doc_data["name"],
                doc_data["student_ID"],
                doc_id,
                doc_data["score"],
                [doc_data["pages"][p].pic_path for p in doc_data["pages"]],
            )
            for doc_id, doc_data in self.data.items()
        ]

        with open(info_path, "w", newline="") as csvfile:
            writerow = csv.writer(csvfile).writerow
            writerow(("Name", "Student ID", "Test ID", "Score", "Pictures"))
            for name, student_ID, doc_id, score, paths in sorted(info):
                paths_as_str = ", ".join(str(pth) for pth in paths)
                writerow([name, student_ID, f"#{doc_id}", score, paths_as_str])
        print(f'Infos stored in "{info_path}"\n')

    def generate_amended_pdf(self) -> None:
        amend_all(self.data_storage)

    def scan_picture(self, picture: Union[str, Path], manual_verification: bool = True) -> None:
        """This is used for debuging (it allows to test pages one by one)."""
        # f1-pic-003.jpg (page 25)
        # f12-pic-005.jpg
        # f12-pic-003.jpg
        # f12-pic-004.jpg
        # f12-pic-013.jpg
        # f7-pic-013.jpg
        # f9-pic-004.jpg
        # f9-pic-005.jpg
        # f13-pic-002.jpg
        if not any(str(picture).endswith(ext) for ext in PIC_EXTS):
            raise TypeError("Allowed picture extensions: " + ", ".join(PIC_EXTS))
        pic_path = Path(picture).expanduser().resolve()
        if not pic_path.is_file():
            pic_path = self.data_storage.absolute_pic_path(picture)
        pic_data, _ = scan_picture(pic_path, self.config, manual_verification=manual_verification)
        print(pic_data)

    def _warn(self, *values, sep=" ", end="\n") -> None:
        """Print to stdout and write to log file."""
        msg = sep.join(str(val) for val in values) + end
        print_warning(msg)
        self.data_storage.write_log(msg)
        self.warnings = True

    def scan_all(
        self,
        start: int = 1,
        end: Union[int, float] = inf,
        manual_verification: Optional[bool] = None,
        ask_for_name: bool = False,
        reset: bool = False,
    ) -> None:
        """Extract information from pdf, calculate scores and annotate documents
        to display correct answers."""

        # Test if the PDF files of the input directory have changed and
        # extract the images from the PDF files if needed.
        print("Search for previous data...")
        self.data_storage.reload(reset=reset)

        # Dict `data` will collect data from all scanned tests.
        # ...............................................................
        # FORMAT: {ID: {'pages': (dict) the pages seen, and all related information,
        #               'answers': ({int: set}) the answers of the student for each question,
        #               'score': (float) the test score,
        #               'name': (str) the student name,
        #               'last_pic': (str) last image seen full path,
        #               },
        #           ...
        #          }
        # ...............................................................
        #

        # ---------------------------------------
        # Extract informations from the pictures.
        # ---------------------------------------
        data = self.data
        # self.name2docID = {d["name"]: ID for ID, d in data.items()}
        self.already_seen = set((ID, p) for ID, d in data.items() for p in d["pages"])
        pic_list = self.data_storage.get_pics_list()

        # assert all(isinstance(path, Path) for path in self.data_storage.skipped)
        # assert all(isinstance(path, Path) for path in self.data_storage.verified)

        for i, pic_path in enumerate(pic_list, start=1):
            if not (start <= i <= end):
                continue
            # Make pic_path relative, so that folder may be moved if needed.
            pic_path = self.data_storage.relative_pic_path(pic_path)
            if pic_path in self.data_storage.skipped:
                continue
            print("-------------------------------------------------------")
            print("Page", i)
            print("File:", pic_path)

            # 1) Extract all the data of an image
            #    ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾

            try:
                # Warning: manual_verification can be None, so the order is important
                # below : False and None -> False (but None and False -> None).
                manual_verification = (pic_path not in self.data_storage.verified) and manual_verification
                pic_data, matrix = scan_picture(
                    self.data_storage.absolute_pic_path(pic_path), self.config, manual_verification
                )
                # `pic_data` FORMAT is specified in `scan_pic.py`.
                # (Search for `pic_data =` in `scan_pic.py`).
                pic_data.pic_path = str(pic_path)
                print()

            except CalibrationError:
                self._warn(f"WARNING: {pic_path} seems invalid ! Skipping...")
                input("-- PAUSE --")
                self.data_storage.store_skipped_pic(pic_path)
                continue

            # if pic_data.verified:
            #     # If the page has been manually verified, keep track of it,
            #     # so it won't be verified next time if a second pass is needed.
            #     self.data_storage.store_verified_pic(pic_path)

            doc_id = pic_data.doc_id
            page = pic_data.page

            if self._keep_previous_version(pic_data):
                continue

            # 2) Gather data
            #    ‾‾‾‾‾‾‾‾‾‾‾
            name, student_ID = self.data_storage.more_infos.get(doc_id, (StudentName(""), StudentId("")))
            doc_data: DocumentData = data.setdefault(
                doc_id,
                DocumentData(
                    pages={}, name=name, student_ID=student_ID, answered={}, score=0, score_per_question={}
                ),
            )
            doc_data["pages"][page] = pic_data

            for q in pic_data.answered:
                ans = doc_data["answered"].setdefault(q, set())
                ans |= pic_data.answered[q]
                # Simplify: doc_data["answered"][q] = set(pic_data["answered"][q])

            # 3) 1st page of the test => retrieve the student name
            #    ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
            # if page == 1:
            #     self._extract_name(doc_id, doc_data, matrix)

            if page == 1:
                if doc_id in self.data_storage.more_infos:
                    doc_data["name"], doc_data["student_ID"] = self.data_storage.more_infos[doc_id]
                else:
                    doc_data["name"] = pic_data.name

            # Store work in progress, so we can resume process if something fails...
            self.data_storage.store_doc_data(pic_path.parent.name, doc_id, page, matrix)

        print("Scan successful.")

        # ---------------------------
        # Resolve detected problems
        # ---------------------------
        # Resolve conflicts manually: unknown student ID, ambiguous answer...
        print("\nAnalyzing collected data:")
        ConflictSolver(self.data_storage).resolve_conflicts()

        # ---------------------------
        # Test integrity
        # ---------------------------
        # For every test:
        # - all pages must have been scanned,
        # - all questions must have been seen.
        print("Test for data integrity...")
        self._test_integrity()
        print("Everything seems OK.")

        # ---------------------------
        # Calculate scores
        # ---------------------------
        # Calculate the score, taking care of the chosen mode.
        self.scores_manager.calculate_scores()
        self.scores_manager.print_scores()

        # ---------------------------------------------------
        # Time to synthesize & store all those informations !
        # ---------------------------------------------------
        self.scores_manager.generate_csv_file()
        self.scores_manager.generate_xlsx_file()
        cfg_ext = ".ptyx.mcq.config.json"
        cfg_path = str(self.data_storage.paths.configfile)
        assert cfg_path.endswith(cfg_ext)
        xlsx_symlink = Path(cfg_path[: -len(cfg_ext)] + ".scores.xlsx")
        xlsx_symlink.unlink(missing_ok=True)
        xlsx_symlink.symlink_to(self.data_storage.files.xlsx_scores)
        self.generate_report()
        self.generate_amended_pdf()
        print(f"\n{ANSI_GREEN}Success ! {ANSI_RESET}:)")


def scan(
    path: Path,
    reset: bool = False,
    ask_for_name: bool = False,
    verify: Literal["auto", "always", "never"] = "auto",
) -> None:
    """Implement `mcq scan` command."""
    if verify == "always":
        manual_verification: Optional[bool] = True
    elif verify == "never":
        manual_verification = False
    else:
        manual_verification = None
    MCQPictureParser(path).scan_all(
        reset=reset,
        ask_for_name=ask_for_name,
        manual_verification=manual_verification,
    )
    print_success("Students' marks successfully generated. :)")
