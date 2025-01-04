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
from ptyx.shell import ANSI_RESET, ANSI_GREEN, print_success
from ptyx.sys_info import CPU_PHYSICAL_CORES
from ptyx_mcq.scan.data.conflict_gestion.data_check.cl_fix import ClAnswersReviewer

from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION, IMAGE_FORMAT
from ptyx_mcq.scan.pdf.amend import amend_all

from ptyx_mcq.scan.data.conflict_gestion import ConflictSolver
from ptyx_mcq.scan.data import ScanData

from ptyx_mcq.scan.score_management.scores_manager import ScoresManager


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


class MCQPictureParser:
    """Main class for parsing pdf files containing all the scanned MCQ."""

    def __init__(
        self,
        path: Union[str, Path],
        input_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.scan_data = ScanData(Path(path), input_dir=input_dir, output_dir=output_dir)
        self.scores_manager = ScoresManager(self)

    @property
    def config(self):
        return self.scan_data.config

    def _generate_report(self) -> None:
        """Generate CSV files with some information concerning each student.

        Used mainly for debugging.
        """
        # TODO: Rewrite it.
        #       A XLSX file should be generated, with all scan information.
        #       - some stats (number of pdf, pages...)
        #       - all conflicts solved, notably duplicate pages found
        # Generate CSV file with ID and pictures names for all students.
        info_path = self.scan_data.files.infos
        # Sort data to make testing easier.
        info = sorted(
            (
                doc.student_name,
                doc.student_id,
                doc_id,
                doc.score,
                sorted(pic.short_path for page in doc for pic in page.pictures),
            )
            for doc_id, doc in self.scan_data.index.items()
        )

        with open(info_path, "w", newline="") as csvfile:
            writerow = csv.writer(csvfile).writerow
            writerow(("Name", "Student ID", "Test ID", "Score", "Pictures"))
            for name, student_id, doc_id, score, paths in info:
                paths_as_str = ", ".join(str(pth) for pth in paths)
                writerow([name, student_id, f"#{doc_id}", score, paths_as_str])
        print(f'Infos stored in "{info_path}"\n')

    def _generate_amended_pdf(self) -> None:
        amend_all(self.scan_data)

    def scan_single_picture(self, short_path: str | Path) -> None:
        """This is used for debugging (it allows to test one page specifically)."""
        # TODO: Still useful?
        #       Test it or remove it.
        short_path = str(short_path)
        if short_path.endswith(ext := f".{IMAGE_FORMAT}"):
            short_path = short_path[: -len(ext)]

        for pic in self.scan_data.pictures:
            if pic.short_path == short_path:
                break
        else:
            raise FileNotFoundError(f"Unable to find picture {short_path!r}.")
        ClAnswersReviewer.display_picture_with_detected_answers(pic)

    def analyze_pages(
        self,
        number_of_processes: int = 1,
        reset: bool = False,
    ) -> None:
        """First stage of the scan process: extract the pictures and read data from them.

        This stage is fully automatic and does not interact with the user.
        Any detected problem will be left as is and only be fixed in a future stage.

        Update `self.data_handler` with collected information.
        """

        # ---------------------------------------
        # Extract informations from the pictures.
        # ---------------------------------------
        print("\nProcessing pages...")

        if number_of_processes <= 0:
            cores = os.cpu_count()
            number_of_processes = 1 if cores is None else min(cores - 1, CPU_PHYSICAL_CORES)

        # TODO: number_of_processes=number_of_processes
        # Test if the PDF files of the input directory have changed and
        # extract the images from the PDF files if needed, then review pictures.
        self.scan_data.run(number_of_processes, reset=reset)
        print_success("Scan successful.")

        # ---------------------------
        # Read checkboxes
        # ---------------------------
        # Test whether each checkbox was checked.
        # self.data_handler.checkboxes.analyze_checkboxes(number_of_processes=number_of_processes)

    def solve_conflicts(self):
        """Resolve conflicts manually: unknown student ID, ambiguous answer..."""
        print("\nAnalyzing collected data:")
        ConflictSolver(self.scan_data).run()
        # TODO: make checkboxes export optional (this is
        #  only useful for debug)
        # print("\nExporting checkboxes...", end=" ")
        # self.scan_data.picture_analyzer.export_checkboxes()
        # print("done.")

    def calculate_scores(self):
        """Calculate the score, taking care of the chosen mode."""
        self.scores_manager.calculate_scores()
        self.scores_manager.print_scores()

    def generate_documents(self):
        """Generate all the documents at the end of the process (csv, xlsx and pdf files)."""
        self.scores_manager.generate_csv_file()
        self.scores_manager.generate_xlsx_file()
        cfg_path = str(self.scan_data.paths.configfile)
        assert cfg_path.endswith(CONFIG_FILE_EXTENSION)
        xlsx_symlink = Path(cfg_path[: -len(CONFIG_FILE_EXTENSION)] + ".scores.xlsx")
        xlsx_symlink.unlink(missing_ok=True)
        xlsx_symlink.symlink_to(self.scan_data.files.xlsx_scores)
        self._generate_report()
        self._generate_amended_pdf()

    def run(
        self,
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
        print("Read input data...")
        # Create directories.
        self.scan_data.paths.make_dirs()

        self.analyze_pages(number_of_processes=number_of_processes, reset=reset)

        # Resolve detected problems.
        self.solve_conflicts()

        # Calculate scores.
        self.calculate_scores()

        # Time to synthesize & store all those information!
        self.generate_documents()

        print(f"\n{ANSI_GREEN}Success ! {ANSI_RESET}:)")
