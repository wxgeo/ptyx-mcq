#!/usr/bin/env python3

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


import csv
import string
import subprocess
import sys
import tempfile
from ast import literal_eval
from hashlib import blake2b
from math import inf
from multiprocessing import Pool
from pathlib import Path
from shutil import rmtree
from time import strftime
from typing import Iterator, Dict, TypedDict, Set, Tuple, List
from typing import Union, Literal, Optional

from PIL import Image
from numpy import int8, array, ndarray

# File `compilation.py` is in ../.., so we have to "hack" `sys.path` a bit.
# script_path = dirname(abspath(sys._getframe().f_code.co_filename))
# sys.path.insert(0, join(script_path, '../..'))
from ptyx.compilation import join_files, compile_latex

from . import scores
from .amend import amend_all
from .pdftools import extract_pdf_pictures, PIC_EXTS, number_of_pages
from .scan_pic import (
    scan_picture,
    ANSI_YELLOW,
    ANSI_RESET,
    ANSI_CYAN,
    ANSI_GREEN,
    ANSI_RED,
    color2debug,
    CalibrationError,
    PicData,
)
from .tools import search_by_extension, print_framed_msg
from ..compile.header import answers_and_score
from ..tools.config_parser import load, get_answers_with_status, Configuration


class FilesPaths(TypedDict, total=False):
    base: str
    skipped: Path
    verified: Path
    results: Path
    cfg: Path


class DocumentData(TypedDict):
    pages: Dict[int, PicData]
    name: str
    student_ID: str
    answered: Dict[int, Set[int]]  # {question: set of answers}
    score: float
    score_per_question: Dict[int, float]  # {question: score}


def pic_names_iterator(data: Dict[int, DocumentData]) -> Iterator[Path]:
    """Iterate over all pics found in data (i.e. all the pictures already analysed)."""
    for doc_data in data.values():
        for pic_data in doc_data["pages"].values():
            path = Path(pic_data["pic_path"])
            # return pdfhash/picnumber.png
            yield path.relative_to(path.parent.parent)


class MCQPictureParser:
    """Main class for parsing pdf files containing all the scanned MCQ."""

    def __init__(
        self,
        path: Union[str, Path],
        input_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.path = Path(path).expanduser().resolve()
        # Main paths.
        self.dirs: Dict[str, Path] = {}
        self.files: FilesPaths = {}
        # All data extracted from pdf files.
        self.data: Dict[int, DocumentData] = {}
        # Additional information entered manually.
        self.more_infos: Dict[int, Tuple[str, str]] = {}  # sheet_id: (name, student_id)
        self.config: Configuration = {}
        # Manually verified pages.
        self.verified: Set[Path] = set()
        # `name2docID` is used to retrieve the data associated with a name.
        # FORMAT: {name: test ID}
        self.name2docID: Dict[str, int] = {}
        # Set `already_seen` will contain all seen (ID, page) couples.
        # It is used to catch a hypothetical scanning problem:
        # we have to be sure that the same page on the same test is not seen
        # twice.
        self.already_seen: Set[Tuple[int, int]] = set()
        self.skipped: Set[Path] = set()
        self.warnings = False
        self.logname = strftime("%Y.%m.%d-%H.%M.%S") + ".log"
        self.correct_answers: Dict[int, Dict[int, Set[int]]] = {}  # {doc_id: {question: set of answers}}
        self._generate_paths(input_dir, output_dir)
        self._load_configuration()

    def _load_data(self) -> None:
        if self.dirs["data"].is_dir():
            for filename in self.dirs["data"].glob("*/*.scandata"):
                ID = int(filename.stem)
                with open(filename) as f:
                    try:
                        self.data[ID] = literal_eval(f.read())
                    except ValueError as e:
                        # Temporary patch.
                        # set() is not supported by literal_eval() until Python 3.9
                        # XXX: remove this once Ubuntu 22.04 will be released.
                        f.seek(0)
                        s = f.read()
                        if sys.version_info < (3, 9) and "set()" in s:
                            self.data[ID] = eval(s)
                        else:
                            print(f"ERROR when reading {filename} :")
                            raise e
                    except Exception:
                        print(f"ERROR when reading {filename} :")
                        raise

    def _store_data(self, pdf_hash: str, doc_id: int, p: int, matrix: ndarray = None) -> None:
        folder = self.dirs["data"] / pdf_hash
        folder.mkdir(exist_ok=True)
        with open(folder / f"{doc_id}.scandata", "w") as f:
            f.write(repr(self.data[doc_id]))
        # We will store a compressed version of the matrix.
        # (It would consume too much memory else).
        if matrix is not None:
            webp = folder / f"{doc_id}-{p}.webp"
            Image.fromarray((255 * matrix).astype(int8)).save(str(webp), format="WEBP")

    def get_pic(self, doc_id: int, page: int) -> Image.Image:
        webp = next(self.dirs["data"].glob(f"*/{doc_id}-{page}.webp"))
        return Image.open(str(webp))

    def get_matrix(self, doc_id: int, page: int) -> ndarray:
        # noinspection PyTypeChecker
        return array(self.get_pic(doc_id, page).convert("L")) / 255

    def _read_name_manually(
        self, doc_id: int, matrix: ndarray = None, p: int = None, default=None
    ) -> Tuple[str, str]:
        if matrix is None:
            assert p is not None
            matrix = self.get_matrix(doc_id, p)
        student_ids = self.config["students_ids"]
        student_ID = ""
        print("Name can not be read automatically.")
        print("Please read the name on the picture which will be displayed now.")
        input("-- Press enter --")
        #    subprocess.run(["display", "-resize", "1920x1080", pic_path])
        # TODO: use first letters of students name to find student.
        # (ask again if not found, or if several names match first letters)
        process = None
        while True:
            nlines = matrix.shape[1]
            # Don't relaunch process if it is still alive.
            # (process.poll() is not None for dead processes.)
            if process is None or process.poll() is not None:
                process = color2debug(matrix[0 : int(3 / 4 * nlines), :], wait=False)
            name = input("Student name or ID:").strip()
            if not name:
                if default is None:
                    continue
                name = default
            if student_ids:
                if name in student_ids:
                    name, student_ID = student_ids[name], name
                elif any((digit in name) for digit in string.digits):
                    # This is not a student name !
                    print("Unknown ID.")
                    continue
            print("Name: %s" % name)
            if input("Is it correct ? (Y/n)").lower() not in ("y", "yes", ""):
                continue
            if name:
                break
        process.terminate()
        # Keep track of manually entered information (will be useful
        # if `scan.py` has to be run again later !)
        #        self.more_infos[ID] = (name, student_ID)
        with open(self.files["cfg"], "a", newline="") as csvfile:
            writerow = csv.writer(csvfile).writerow
            writerow([str(doc_id), name, student_ID])
        return name, student_ID

    def _test_integrity(self) -> None:
        """For every test:
        - all pages must have been scanned,
        - all questions must have been seen."""
        questions_not_seen = {}
        pages_not_seen = {}
        for doc_id in self.data:
            questions = set(self.config["ordering"][doc_id]["questions"])
            diff = questions - set(self.data[doc_id]["answered"])
            if diff:
                questions_not_seen[doc_id] = ", ".join(str(q) for q in diff)
            # All tests may not have the same number of pages, since
            # page breaking will occur at a different place for each test.
            pages = set(self.config["boxes"][doc_id])
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
            raise RuntimeError("Questions not seen ! (Look at message above).")

    def _keep_previous_version(self, pic_data: PicData) -> bool:
        """Test if a previous version of the same page exist.

        If so, it probably means the page has been scanned twice, but it could
        also indicate a more serious problem (for example, tests with the same ID
        have been given to different students !).
        As a precaution, we should signal the problem to the user, and ask him
        what he wants to do.
        """
        doc_id = pic_data["ID"]
        p = pic_data["page"]

        # This page has never been seen before, everything is OK.
        if (doc_id, p) not in self.already_seen:
            self.already_seen.add((doc_id, p))
            return False

        # This is problematic: it seems like the same page has been seen twice.
        lastpic_path = pic_data["pic_path"]
        lastpic = Path(lastpic_path).relative_to(self.dirs["pic"])
        firstpic_path = self.data[doc_id]["pages"][p]["pic_path"]
        firstpic = Path(firstpic_path).relative_to(self.dirs["pic"])
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
        with open(self.files["skipped"], "a", newline="", encoding="utf8") as file:
            file.write(f"{skipped_pic}\n")

        if action == "l":
            # Remove first picture information.
            del self.data[doc_id]["pages"][p]
            self._store_data(firstpic.parent.name, doc_id, p)

        return action == "f"

    def _extract_name(self, doc_id: int, doc_data: DocumentData, matrix: ndarray, ask: bool = False) -> None:
        # TODO: what is matrix type ?
        pic_data = doc_data["pages"][1]
        # (a) The first page should contain the name
        #     ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾
        # However, if the name was already set (using `more_infos`),
        # don't overwrite it.
        if not doc_data["name"]:
            # Store the name read (except if ask not to do so).
            if not ask:
                doc_data["name"] = pic_data["name"]

        name = doc_data["name"]

        # (b) Update name manually if it was not found
        #     ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾

        if not name:
            name = self._read_name_manually(doc_id, matrix)[0]

        # (c) A name must not appear twice
        #     ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾ ‾
        while name in self.name2docID:
            print(f"Test #{self.name2docID[name]}: {name}")
            print(f"Test #{doc_id}: {name}")
            print_framed_msg(
                f"Error : 2 tests for same student ({name}) !\n"
                "Please modify at least one name (enter nothing to keep a name)."
            )
            # Remove twin name from name2doc_id, and get the corresponding previous test ID.
            ID0 = self.name2docID.pop(name)
            # Ask for a new name.
            name0, student_ID0 = self._read_name_manually(ID0, p=1, default=name)
            # Update all infos.
            self.name2docID[name0] = ID0
            self.data[ID0]["name"] = name0
            self.data[ID0]["student_ID"] = student_ID0
            # Ask for a new name for new test too.
            name = self._read_name_manually(doc_id, matrix, default=name)[0]

        assert name, "Name should not be left empty at this stage !"
        self.name2docID[name] = doc_id
        doc_data["name"] = name

    def _calculate_scores(self) -> None:
        cfg = self.config
        default_mode = cfg["mode"]["default"]
        default_correct = cfg["correct"]["default"]
        default_incorrect = cfg["incorrect"]["default"]
        default_skipped = cfg["skipped"]["default"]
        default_floor = cfg["floor"]["default"]
        default_ceil = cfg["ceil"]["default"]

        for doc_id in self.data:
            correct_ans = self.correct_answers[doc_id]
            neutralized_ans = self.neutralized_answers[doc_id]
            print(f'Test {doc_id} - {self.data[doc_id]["name"]}')
            doc_data = self.data[doc_id]
            for q in sorted(doc_data["answered"]):
                answered = set(doc_data["answered"][q])
                correct_ones = correct_ans[q]
                neutralized_ones = neutralized_ans[q]
                all_answers = {ans_num for ans_num, is_ok in cfg["ordering"][doc_id]["answers"][q]}

                # Neutralized answers must be removed from each set of answers.
                # (Typically, neutralized answers are answers which were detected faulty during or after the
                # examination).
                answered -= neutralized_ones
                correct_ones -= neutralized_ones
                all_answers -= neutralized_ones

                mode = cfg["mode"].get(q, default_mode)

                if mode == "skip":
                    # Used mostly to skip bogus questions.
                    print(f"Question {q} skipped...")
                    continue

                try:
                    func = getattr(scores, mode)
                except AttributeError:
                    raise AttributeError(f"Unknown evaluation mode: {mode!r}.")

                ans_data = scores.AnswersData(checked=answered, correct=correct_ones, all=all_answers)
                scores_data = scores.ScoreData(
                    correct=float(cfg["correct"].get(q, default_correct)),
                    skipped=float(cfg["skipped"].get(q, default_skipped)),
                    incorrect=float(cfg["incorrect"].get(q, default_incorrect)),
                )
                earn = func(ans_data, scores_data)

                floor = cfg["floor"].get(q, default_floor)
                assert floor is None or isinstance(floor, (float, int))
                if floor is not None and earn < floor:
                    earn = floor
                ceil = cfg["ceil"].get(q, default_ceil)
                assert ceil is None or isinstance(ceil, (float, int))
                if ceil is not None and earn > ceil:
                    earn = ceil

                if earn == scores_data.correct:
                    color = ANSI_GREEN
                elif earn == scores_data.incorrect:
                    color = ANSI_RED
                else:
                    color = ANSI_YELLOW
                print(f"-  {color}Rating (Q{q}): {color}{earn:g}{ANSI_RESET}")
                doc_data["score"] += earn
                doc_data["score_per_question"][q] = earn

    def generate_output(self) -> None:
        """Generate CSV files with scores and annotated documents."""
        max_score = self.config["max_score"]
        # Generate CSV file with results.
        scores = {doc_data["name"]: doc_data["score"] for doc_data in self.data.values()}
        # ~ print(scores)
        scores_path = self.dirs["output"] / "scores.csv"
        print(f"{ANSI_CYAN}SCORES (/{max_score:g}):{ANSI_RESET}")
        with open(scores_path, "w", newline="") as csvfile:
            writerow = csv.writer(csvfile).writerow
            writerow(("Name", "Score"))
            for name in sorted(scores):
                print(f" - {name}: {scores[name]:g}")
                writerow([name, scores[name]])
        if scores.values():
            mean = round(sum(scores.values()) / len(scores.values()), 2)
            print(f"{ANSI_YELLOW}Mean: {mean:g}/{max_score:g}{ANSI_RESET}")
        else:
            print("No score found !")
        print(f'\nResults stored in "{scores_path}"\n')

        # Generate CSV file with ID and pictures names for all students.
        info_path = self.dirs["output"] / "infos.csv"
        info = [
            (
                doc_data["name"],
                doc_data["student_ID"],
                doc_id,
                doc_data["score"],
                [doc_data["pages"][p]["pic_path"] for p in doc_data["pages"]],
            )
            for doc_id, doc_data in self.data.items()
        ]
        print(f"{ANSI_CYAN}SCORES (/{max_score:g}):{ANSI_RESET}")
        with open(info_path, "w", newline="") as csvfile:
            writerow = csv.writer(csvfile).writerow
            writerow(("Name", "Student ID", "Test ID", "Score", "Pictures"))
            for name, student_ID, doc_id, score, paths in sorted(info):
                paths_as_str = ", ".join(str(pth) for pth in paths)
                writerow([name, student_ID, f"#{doc_id}", score, paths_as_str])
        print(f'Infos stored in "{info_path}"\n')
        amend_all(self)

    def generate_correction(self, display_score: bool = True) -> None:
        """Generate pdf files, with the score and the table of correct answers for each test."""
        pdf_paths: List[Path] = []
        for doc_id, doc_data in self.data.items():
            # ~ identifier, answers, name, score, students, ids
            name = doc_data["name"]
            score = doc_data["score"]
            prefix = self.files["base"]
            path = self.dirs["pdf"] / f"{prefix}-{doc_id}-corr.score"
            pdf_paths.append(path)
            print(f"Generating pdf file for student {name} (subject {doc_id}, score {score})...")
            latex = answers_and_score(self.config, name, doc_id, (score if display_score else None))
            texfile_name = path.with_suffix(".tex")
            with open(texfile_name, "w") as texfile:
                texfile.write(latex)
                texfile.flush()
            compile_latex(texfile_name, dest=path, quiet=True)
        join_files(self.files["results"], pdf_paths, remove_all=True, compress=True)

    def _load_configuration(self) -> None:
        """Read configuration file, load configuration and calculate maximal score too."""
        configfile = search_by_extension(self.path, ".mcq.config.json")
        cfg: Configuration = load(configfile)
        self.correct_answers = get_answers_with_status(cfg, correct=True)
        self.neutralized_answers = get_answers_with_status(cfg, correct=None)
        default_mode = cfg["mode"]["default"]
        default_correct = cfg["correct"]["default"]

        max_score = 0
        # Take a random student test, and calculate max score for it.
        # Maximal score = (number of questions)x(score when answer is correct)
        for q in next(iter(cfg["ordering"].values()))["questions"]:
            if cfg["mode"].get(q, default_mode) != "skip":
                max_score += int(cfg["correct"].get(q, default_correct))
        cfg["max_score"] = max_score
        self.config = cfg

    def _make_dirs(self, reset: bool = False) -> None:
        """Generate output directory structure.

        If `reset` is True, remove all output directory content.
        """
        if reset and self.dirs["output"].is_dir():
            rmtree(self.dirs["output"])

        for directory in self.dirs.values():
            if not directory.is_dir():
                directory.mkdir()

    def _generate_paths(self, input_dir: Optional[Path] = None, output_dir: Optional[Path] = None) -> None:
        root = self.path
        if not root.is_dir():
            root = root.parent
            if not root.is_dir():
                raise FileNotFoundError("%s does not seem to be a directory !" % root)
        self.dirs["root"] = root

        # ------------------
        # Generate the paths
        # ------------------

        self.dirs["input"] = input_dir or (root / "scan")

        # `.scan` directory is used to write intermediate files.
        # Directory tree:
        # .scan/
        # .scan/pic -> pictures extracted from the pdf
        # .scan/cfg/more_infos.csv -> missing students names.
        # .scan/cfg/verified.csv -> pages already verified.
        # .scan/cfg/skipped.csv -> pages to skip.
        # .scan/scores.csv
        # .scan/data -> data stored as .scandata files (used to resume interrupted scan).
        self.dirs["output"] = output_dir or (self.dirs["root"] / ".scan")
        self.dirs["data"] = self.dirs["output"] / "data"
        self.dirs["cfg"] = self.dirs["output"] / "cfg"
        self.dirs["pic"] = self.dirs["output"] / "pic"
        self.dirs["pdf"] = self.dirs["output"] / "pdf"
        self.dirs["log"] = self.dirs["output"] / "log"

        self.files["base"] = search_by_extension(self.dirs["root"], ".ptyx").stem
        self.files["results"] = self.dirs["pdf"] / (self.files["base"] + "-results")

    #    def _extract_pictures_from_pdf(self):
    #        # First, we must test if pdf files have changed.
    #        # - calculate hash for each file.
    #        # - if nothing has changes, pass.
    #        # - if new pdf files are found, extract pictures from them and store their hash.
    #        # - if pdf files where modified or removed, regenerate everything.
    #        # hashlib.sha512(f.read()).hexdigest()

    def _load_all_info(self) -> None:
        """Load all information from files."""
        self._load_data()

        # Read manually entered information (if any).
        self.files["cfg"] = self.dirs["cfg"] / "more_infos.csv"
        if self.files["cfg"].is_file():
            with open(self.files["cfg"], "r", newline="") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    try:
                        sheet_ID, name, student_ID = row
                    except ValueError:
                        sheet_ID, name = row
                        student_ID = ""
                    self.more_infos[int(sheet_ID)] = (name, student_ID)
                print("Retrieved infos:", self.more_infos)

        # List manually verified pages.
        # They should not be verified anymore.
        self.files["verified"] = self.dirs["cfg"] / "verified.txt"
        if self.files["verified"].is_file():
            with open(self.files["verified"], "r", encoding="utf8", newline="") as file:
                self.verified = set(Path(line.strip()) for line in file.readlines())
                print("Pages manually verified:")
                for path in self.verified:
                    print(f"    • {path}")

        self.skipped = set(pic_names_iterator(self.data))

        # List skipped pictures.
        # Next time, they will be skipped with no warning.
        self.files["skipped"] = self.dirs["cfg"] / "skipped.txt"
        if self.files["skipped"].is_file():
            with open(self.files["skipped"], "r", encoding="utf8", newline="") as file:
                self.skipped |= set(Path(line.strip()) for line in file.readlines())
                print("Pictures skipped:")
                for path in sorted(self.skipped):
                    print(f"    • {path}")

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
            pic_path = self.dirs["pic"] / picture
        pic_data, _ = scan_picture(pic_path, self.config, manual_verification=manual_verification)
        print(pic_data)

    def _generate_current_pdf_hashes(self) -> Dict[str, Path]:
        """Return the hashes of all the pdf files found in `scan/` directory.

        Return: {hash: pdf path}
        """
        hashes = dict()
        for path in self.dirs["input"].glob("**/*.pdf"):
            with open(path, "rb") as pdf_file:
                hashes[blake2b(pdf_file.read(), digest_size=20).hexdigest()] = path
        return hashes

    def _update_input_data(self) -> None:
        """Test if input data has changed, and update it if needed."""
        hash2pdf: Dict[str, Path] = self._generate_current_pdf_hashes()

        def test_path(pth):
            if not pth.is_dir():
                raise RuntimeError(
                    f'Folder "{pth.parent}" should only contain folders.\n'
                    "You may clean it manually, or remove it with following command:\n"
                    f'rm -r "{pth.parent}"'
                )

        # For each removed pdf files, remove corresponding pictures and data
        for path in self.dirs["pic"].iterdir():
            test_path(path)
            if path.name not in hash2pdf:
                rmtree(path)
        for path in self.dirs["data"].iterdir():
            test_path(path)
            if path.name not in hash2pdf:
                rmtree(path)

        # For each new pdf files, extract all pictures
        to_extract: list[tuple[Path, Path]] = []
        with Pool() as pool:
            for pdfhash, pdfpath in hash2pdf.items():
                folder = self.dirs["pic"] / pdfhash
                if not folder.is_dir():
                    to_extract.append((pdfpath, folder))
                elif number_of_pages(pdfpath) != len(
                    [f for f in folder.iterdir() if f.suffix.lower() in PIC_EXTS]
                ):
                    # Extraction was probably interrupted
                    rmtree(folder)
                    folder.mkdir()
                    to_extract.append((pdfpath, folder))
            pool.starmap(extract_pdf_pictures, to_extract)

    def _warn(self, *values, sep=" ", end="\n") -> None:
        """Print to stdout and write to log file."""
        msg = sep.join(str(val) for val in values) + end
        print(msg)
        with open(self.dirs["log"] / self.logname, "a", encoding="utf8") as logfile:
            logfile.write(msg)
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
        self._make_dirs(reset)

        # Test if the PDF files of the input directory have changed and
        # extract the images from the PDF files if needed.
        self._update_input_data()
        # Load data from previous run
        self._load_all_info()

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
        self.name2docID = {d["name"]: ID for ID, d in data.items()}
        self.already_seen = set((ID, p) for ID, d in data.items() for p in d["pages"])
        pic_list = sorted(f for f in self.dirs["pic"].glob("*/*") if f.suffix.lower() in PIC_EXTS)

        assert all(isinstance(path, Path) for path in self.skipped)
        assert all(isinstance(path, Path) for path in self.verified)

        for i, pic_path in enumerate(pic_list, start=1):
            if not (start <= i <= end):
                continue
            # Make pic_path relative, so that folder may be moved if needed.
            pic_path = pic_path.relative_to(self.dirs["pic"])
            if pic_path in self.skipped:
                continue
            print("-------------------------------------------------------")
            print("Page", i)
            print("File:", pic_path)

            # 1) Extract all the data of an image
            #    ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾

            try:
                # Warning: manual_verification can be None, so the order is important
                # below : False and None -> False (but None and False -> None).
                manual_verification = (pic_path not in self.verified) and manual_verification
                pic_data, matrix = scan_picture(self.dirs["pic"] / pic_path, self.config, manual_verification)
                # `pic_data` FORMAT is specified in `scan_pic.py`.
                # (Search for `pic_data =` in `scan_pic.py`).
                pic_data["pic_path"] = str(pic_path)
                print()

            except CalibrationError:
                self._warn(f"WARNING: {pic_path} seems invalid ! Skipping...")
                input("-- PAUSE --")
                with open(self.files["skipped"], "a", newline="", encoding="utf8") as file:
                    file.write(f"{pic_path}\n")
                continue

            if pic_data["verified"]:
                # If the page has been manually verified, keep track of it,
                # so it won't be verified next time if a second pass is needed.
                with open(self.files["verified"], "a", newline="", encoding="utf8") as file:
                    file.write(f"{pic_path}\n")

            doc_id = pic_data["ID"]
            page = pic_data["page"]

            if self._keep_previous_version(pic_data):
                continue

            # 2) Gather data
            #    ‾‾‾‾‾‾‾‾‾‾‾
            name, student_ID = self.more_infos.get(doc_id, ("", ""))
            doc_data: DocumentData = data.setdefault(
                doc_id,
                DocumentData(
                    pages={}, name=name, student_ID=student_ID, answered={}, score=0, score_per_question={}
                ),
            )
            doc_data["pages"][page] = pic_data

            for q in pic_data["answered"]:
                ans = doc_data["answered"].setdefault(q, set())
                ans |= pic_data["answered"][q]
                # Simplify: doc_data["answered"][q] = set(pic_data["answered"][q])

            # 3) 1st page of the test => retrieve the student name
            #    ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
            if page == 1:
                self._extract_name(doc_id, doc_data, matrix)

            # Store work in progress, so we can resume process if something fails...
            self._store_data(pic_path.parent.name, doc_id, page, matrix)

        # ---------------------------
        # Test integrity
        # ---------------------------
        # For every test:
        # - all pages must have been scanned,
        # - all questions must have been seen.
        self._test_integrity()

        # ---------------------------
        # Calculate scores
        # ---------------------------
        # Calculate the score, taking care of the chosen mode.
        self._calculate_scores()
        print()

        # ---------------------------------------------------
        # Time to synthetize & store all those informations !
        # ---------------------------------------------------
        self.generate_output()

    def resolve_conflicts(self):
        """Resolve conflicts manually: unknown student ID, ambiguous answer..."""
        pass


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
