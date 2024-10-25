#!/usr/bin/env python3
import concurrent.futures
import csv
import multiprocessing
import os
import sys

# import time
from io import BytesIO
from math import inf
from pathlib import Path
from typing import Union, Optional

# from numpy import ndarray
from ptyx.shell import print_warning, ANSI_RESET, ANSI_GREEN, print_success
from ptyx.sys_info import CPU_PHYSICAL_CORES
from ptyx_mcq.scan.data_gestion.conflict_handling.data_check.cl_fix import ClAnswersReviewer

from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq.scan.pdf.amend import amend_all

from ptyx_mcq.scan.data_gestion.conflict_handling import ConflictSolver
from ptyx_mcq.scan.data_gestion.data_handler import DataHandler, save_webp
from ptyx_mcq.scan.data_gestion.document_data import DocumentData, Page, PicData
from ptyx_mcq.scan.pdf.pdftools import PIC_EXTS
from ptyx_mcq.scan.picture_analyze.scan_pic import (
    scan_picture,
)
from ptyx_mcq.scan.picture_analyze.types_declaration import CalibrationError
from ptyx_mcq.scan.score_management.scores_manager import ScoresManager
from ptyx_mcq.tools.config_parser import (
    StudentId,
    StudentName,
    DocumentId,
)


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


class Silent:
    """A context manager enabling to discard any stdout output for a while.

    with Silent():
        ...
    """

    def __init__(self, silent=True):
        self.silent = silent

    def __enter__(self):
        if self.silent:
            self.stdout = sys.stdout
            sys.stdout = self

    def __exit__(self, exception_type, value, traceback):
        if self.silent:
            sys.stdout = self.stdout

    def write(self, x):
        pass

    def flush(self):
        pass


class MCQPictureParser:
    """Main class for parsing pdf files containing all the scanned MCQ."""

    def __init__(
        self,
        path: Union[str, Path],
        input_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        # self.warnings = False
        self.data_handler = DataHandler(Path(path), input_dir=input_dir, output_dir=output_dir)
        self.scores_manager = ScoresManager(self)
        # Set `already_seen` will contain all seen (ID, page) couples.
        # It is used to catch a hypothetical scanning problem:
        # we have to be sure that the same page on the same test is not seen twice.
        self.already_seen: set[tuple[DocumentId, Page]] = set()

    @property
    def config(self):
        return self.data_handler.config

    @property
    def data(self):
        return self.data_handler.data

    def _generate_report(self) -> None:
        """Generate CSV files with some information concerning each student.

        Used mainly for debugging.
        """
        # Generate CSV file with ID and pictures names for all students.
        info_path = self.data_handler.files.infos
        # Sort data to make testing easier.
        info = sorted(
            (
                doc_data.name,
                doc_data.student_id,
                doc_id,
                doc_data.score,
                sorted(doc_data.pages[p].pic_path for p in doc_data.pages),
            )
            for doc_id, doc_data in self.data.items()
        )

        with open(info_path, "w", newline="") as csvfile:
            writerow = csv.writer(csvfile).writerow
            writerow(("Name", "Student ID", "Test ID", "Score", "Pictures"))
            for name, student_id, doc_id, score, paths in sorted(info):
                paths_as_str = ", ".join(str(pth) for pth in paths)
                writerow([name, student_id, f"#{doc_id}", score, paths_as_str])
        print(f'Infos stored in "{info_path}"\n')

    def _generate_amended_pdf(self) -> None:
        amend_all(self.data_handler)

    def scan_single_picture(self, picture: Union[str, Path]) -> None:
        """This is used for debugging (it allows to test one page specifically)."""
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
            pic_path = self.data_handler.absolute_pic_path(picture)
        pic_data, array = scan_picture(pic_path, self.config, debug=True)
        ClAnswersReviewer.display_picture_with_detected_answers(array, pic_data)
        print(pic_data)

    # def _warn(self, *values, sep=" ", end="\n") -> None:
    #     """Print to stdout and write to log file."""
    #     msg = sep.join(str(val) for val in values) + end
    #     print_warning(msg)
    #     self.data_handler.write_log(msg)
    #     self.warnings = True

    def _scan_current_page(
        self, pic_path: Path, silent=True, debug=False
    ) -> tuple[Path, PicData, BytesIO] | Path:
        with Silent(silent):
            print("-------------------------------------------------------")
            print("File:", pic_path)

            # 1) Extract all the data of an image
            #    ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾

            try:
                pic_data, matrix = scan_picture(
                    self.data_handler.absolute_pic_path(pic_path), config=self.config, debug=debug
                )
                # Warning: manual_verification can be None, so the order is important
                # below : False and None -> False (but None and False -> None).
                # if (pic_path not in self.data_handler.verified) and manual_verification:
                #     # TODO: modify pic_data to force manual verification.
                #     ...
                # `pic_data` FORMAT is specified in `scan_pic.py`.
                # (Search for `pic_data =` in `scan_pic.py`).
                pic_data.pic_path = str(pic_path)
                bytes_io = BytesIO()
                save_webp(matrix, bytes_io)
                return pic_path, pic_data, bytes_io

            except CalibrationError:
                return pic_path

    def _collect_pages(self, start: int, end: int | float) -> list[Path]:
        to_analyze: list[Path] = []
        for i, pic_path in enumerate(self.data_handler.get_pics_list(), start=1):
            if not (start <= i <= end):
                continue
            # Make pic_path relative, so that folder may be moved if needed.
            pic_path = self.data_handler.relative_pic_path(pic_path)
            if pic_path in self.data_handler.skipped:
                continue
            to_analyze.append(pic_path)
        return to_analyze

    def _handle_scan_result(self, scan_result: tuple[Path, PicData, BytesIO] | Path) -> None:
        """Store document retrieved data."""
        if isinstance(scan_result, Path):
            print_warning(f"{scan_result} seems invalid ! Skipping...")
            self.data_handler.store_skipped_pic(scan_result)
            return
        pic_path, pic_data, bytes_io = scan_result
        doc_id = pic_data.doc_id
        page = pic_data.page
        # Test whether a previous version of the same page exist:
        # if the same page has been seen twice, this may be problematic,
        # so call `._keep_previous_version()` to ask user what to do.
        # if (doc_id, page) in already_seen and self._keep_previous_version(pic_data):
        #     # If the user answered to skip the current page, just do it.
        #     continue
        if (doc_id, page) in self.already_seen:
            # There are two versions (at least) of the same document.
            # Store it for now, with a new temporary id, and resolve conflict later.
            doc_id = self.data_handler.create_new_temporary_id(doc_id, page)
        self.already_seen.add((doc_id, page))

        # 2) Gather data
        #    ‾‾‾‾‾‾‾‾‾‾‾
        name, student_id = self.data_handler.more_infos.get(doc_id, (StudentName(""), StudentId("")))
        doc_data: DocumentData = self.data.setdefault(
            doc_id,
            DocumentData(
                pages={},
                name=name,
                student_id=student_id,
                score=0,
                score_per_question={},
            ),
        )
        doc_data.pages[page] = pic_data

        # 3) 1st page of the test => retrieve the student name
        #    ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾

        if page == 1:
            if doc_id in self.data_handler.more_infos:
                doc_data.name, doc_data.student_id = self.data_handler.more_infos[doc_id]
            else:
                doc_data.name = pic_data.name
                doc_data.student_id = pic_data.student_id

                # Store work in progress, so we can resume process if something fails...

        # print("[", time.time() - t, "]")
        self.data_handler.store_doc_data(pic_path.parent.name, doc_id, page, bytes_io)
        # print(time.time() - t)
        # t = time.time()

    def _serial_scanning(self, to_analyze: list[Path], debug=False):
        """Scan all documents sequentially using only one process.

        This is usually slower, but easier to debug.
        """
        # No multiprocessing
        for i, pic_path in enumerate(to_analyze, start=1):
            scan_result: tuple[Path, PicData, BytesIO] | Path = self._scan_current_page(
                pic_path, silent=False, debug=debug
            )
            self._handle_scan_result(scan_result)
            # print(f"Page {i}/{len(to_analyze)} processed.", end="\r")

    def _parallel_scanning(self, to_analyze: list[Path], number_of_processes: int, debug=False):
        """Scan all documents using several processes running in parallel.

        This is default behaviour on most platform, since it takes advantage of multi-cores computers,
        though it is harder to debug.
        """
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=number_of_processes, mp_context=multiprocessing.get_context("spawn")
        ) as executor:
            # Use an iterator, to limit memory consumption.
            todo = (
                executor.submit(self._scan_current_page, pic_path, True, debug) for pic_path in to_analyze
            )

            # t = time.time()
            for i, future in enumerate(concurrent.futures.as_completed(todo), start=1):
                scan_result: tuple[Path, PicData, BytesIO] | Path = future.result()
                self._handle_scan_result(scan_result)
                print(f"Page {i}/{len(to_analyze)} processed.", end="\r")

    def analyze_pages(
        self,
        start: int = 1,
        end: Union[int, float] = inf,
        number_of_processes: int = 1,
        reset: bool = False,
        debug: bool = False,
    ) -> None:
        """First stage of the scan process: extract the pictures and read data from them.

        This stage is fully automatic and does not interact with the user.
        Any detected problem will be left as is and only be fixed in a future stage.

        Update `self.data_handler` with collected information.
        """
        # Test if the PDF files of the input directory have changed and
        # extract the images from the PDF files if needed.
        print("Search for previous data...")
        self.data_handler.reload(reset=reset)

        # ---------------------------------------
        # Extract informations from the pictures.
        # ---------------------------------------
        print("\nProcessing pages...")
        self.already_seen = {(ID, p) for ID, d in self.data.items() for p in d.pages}

        to_analyze = self._collect_pages(start, end)
        if number_of_processes <= 0:
            cores = os.cpu_count()
            number_of_processes = 1 if cores is None else min(cores - 1, CPU_PHYSICAL_CORES)
        if number_of_processes == 1:
            self._serial_scanning(to_analyze, debug=debug)
        else:
            # t = time.time()
            self._parallel_scanning(to_analyze, number_of_processes=number_of_processes, debug=debug)
            # print(time.time() - t)

        # gc.collect()
        print_success("Scan successful.")

        # ---------------------------
        # Read checkboxes
        # ---------------------------
        # Test whether each checkbox was checked.
        self.data_handler.checkboxes.analyze_checkboxes(number_of_processes=number_of_processes)

    def solve_conflicts(self):
        """Resolve conflicts manually: unknown student ID, ambiguous answer..."""
        print("\nAnalyzing collected data:")
        ConflictSolver(self.data_handler).run()
        # TODO: make checkboxes export optional (this is
        #  only useful for debug)
        print("\nExporting checkboxes...", end=" ")
        self.data_handler.checkboxes.export_checkboxes()
        print("done.")

    def calculate_scores(self):
        """Calculate the score, taking care of the chosen mode."""
        self.scores_manager.calculate_scores()
        self.scores_manager.print_scores()

    def generate_documents(self):
        """Generate all the documents at the end of the process (csv, xlsx and pdf files)."""
        self.scores_manager.generate_csv_file()
        self.scores_manager.generate_xlsx_file()
        cfg_path = str(self.data_handler.paths.configfile)
        assert cfg_path.endswith(CONFIG_FILE_EXTENSION)
        xlsx_symlink = Path(cfg_path[: -len(CONFIG_FILE_EXTENSION)] + ".scores.xlsx")
        xlsx_symlink.unlink(missing_ok=True)
        xlsx_symlink.symlink_to(self.data_handler.files.xlsx_scores)
        self._generate_report()
        self._generate_amended_pdf()

    def run(
        self,
        start: int = 1,
        end: Union[int, float] = inf,
        manual_verification: Optional[bool] = None,
        number_of_processes: int = 0,
        debug: bool = False,
        reset: bool = False,
    ) -> None:
        """Main method: extract pictures, analyze them, calculate scores and generate reports.

        Extract information from pdf, calculate scores and annotate documents
        to display correct answers.

        If `cores` is 0 or less, cores number is automatically calculated.
        Set cores to `1` to disable multiprocessing.
        """

        # Extract information from scanned documents.
        self.analyze_pages(
            start=start, end=end, number_of_processes=number_of_processes, reset=reset, debug=debug
        )

        # Resolve detected problems.
        self.solve_conflicts()

        # Calculate scores.
        self.calculate_scores()

        # Time to synthesize & store all those information!
        self.generate_documents()

        print(f"\n{ANSI_GREEN}Success ! {ANSI_RESET}:)")
