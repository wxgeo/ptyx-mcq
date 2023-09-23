import csv
import signal
from hashlib import blake2b
from multiprocessing import Pool
from pathlib import Path
from shutil import rmtree
from types import FrameType
from typing import Iterator

from PIL import Image
from numpy import ndarray, array, int8

from ptyx_mcq.scan.checkbox_analyzer import analyze_checkboxes
from ptyx_mcq.scan.document_data import DocumentData, PicData, DetectionStatus, RevisionStatus, Page
from ptyx_mcq.scan.paths_handler import PathsHandler, DirsPaths, FilesPaths
from ptyx_mcq.scan.pdftools import number_of_pages, extract_pdf_pictures, PIC_EXTS
from ptyx_mcq.tools.config_parser import (
    Configuration,
    get_answers_with_status,
    DocumentId,
    StudentName,
    StudentId,
    OriginalQuestionAnswersDict,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
)
from ptyx_mcq.tools.extend_literal_eval import extended_literal_eval
from ptyx_mcq.tools.io_tools import ANSI_CYAN, ANSI_RESET, ANSI_YELLOW, ANSI_GREEN, print_error


def save_webp(matrix: ndarray, path: Path | str, lossless=False) -> None:
    """Save image content as a WEBP image."""
    Image.fromarray((255 * matrix).astype(int8)).save(str(path), format="WEBP", lossless=lossless)


def pic_names_iterator(data: dict[DocumentId, DocumentData]) -> Iterator[Path]:
    """Iterate over all pics found in data (i.e. all the pictures already analysed)."""
    for doc_data in data.values():
        for pic_data in doc_data.pages.values():
            path = Path(pic_data.pic_path)
            # return pdfhash/picnumber.png
            yield path.relative_to(path.parent.parent)


class DataHandler:
    """Store and retrieve the data."""

    def __init__(self, config_path: Path, input_dir: Path = None, output_dir: Path = None):
        self.paths = PathsHandler(config_path=config_path, input_dir=input_dir, output_dir=output_dir)
        # All data extracted from pdf files.
        self.data: dict[DocumentId, DocumentData] = {}
        # Additional information entered manually.
        self.more_infos: dict[DocumentId, tuple[StudentName, StudentId]] = {}
        # Manually verified pages.
        self.verified: set[Path] = set()
        self.skipped: set[Path] = set()
        self.correct_answers: dict[DocumentId, OriginalQuestionAnswersDict] = {}
        self.neutralized_answers: dict[DocumentId, OriginalQuestionAnswersDict] = {}
        # self.paths.make_dirs()
        self.config: Configuration = self.get_configuration(self.paths.configfile)

    # def student_name_to_doc_id_dict(self) -> dict[StudentName, DocumentId]:
    #     """`student_name_to_doc_id` is used to retrieve the data associated with a name."""
    #     return {doc_data["name"]: doc_id for doc_id, doc_data in self.data.items()}

    @property
    def dirs(self) -> DirsPaths:
        return self.paths.dirs

    @property
    def files(self) -> FilesPaths:
        return self.paths.files

    @property
    def input_dir(self):
        return self.paths.input_dir

    @property
    def output_dir(self):
        return self.paths.output_dir

    def write_log(self, msg: str) -> None:
        with open(self.paths.logfile_path, "a", encoding="utf8") as logfile:
            logfile.write(msg)

    def get_pic(self, doc_id: int, page: int) -> Image.Image:
        try:
            webp = next(self.dirs.data.glob(f"{doc_id}-{page}.webp"))
        except StopIteration:
            print_error(f"File not found: `{doc_id}-{page}.webp`")
            raise
        try:
            return Image.open(str(webp))
        except Exception:
            print_error(f"Error when opening {webp}.")
            raise

    def get_matrix(self, doc_id: int, page: int) -> ndarray:
        # noinspection PyTypeChecker
        return array(self.get_pic(doc_id, page).convert("L")) / 255

    def get_pics_list(self):
        """Return sorted pics list."""
        return sorted(f for f in self.dirs.pic.glob("*/*") if f.suffix.lower() in PIC_EXTS)

    def relative_pic_path(self, pic_path: str | Path):
        """Return picture path relatively to the `.scan/pic/` parent directory."""
        return Path(pic_path).relative_to(self.dirs.pic)

    def absolute_pic_path(self, pic_path: str | Path):
        return self.dirs.pic / pic_path

    def get_configuration(self, path: Path) -> Configuration:
        """Read configuration file, load configuration and calculate maximal score too."""
        cfg: Configuration = Configuration.load(path)
        self.correct_answers = get_answers_with_status(cfg, correct=True)
        self.neutralized_answers = get_answers_with_status(cfg, correct=None)
        default_mode = cfg.mode["default"]
        default_correct = cfg.correct["default"]

        max_score: float = 0
        # Take a random student test, and calculate max score for it.
        # Maximal score = (number of questions)x(score when answer is correct)
        for q in next(iter(cfg.ordering.values()))["questions"]:
            if cfg.mode.get(q, default_mode) != "skip":
                max_score += cfg.correct.get(q, default_correct)
        cfg.max_score = max_score
        return cfg

    def reload(self, reset=False) -> None:
        """Load all information from files."""
        self.paths.make_dirs(reset)
        self._update_input_data()
        # Load data from previous run.
        self._load_data()
        self._load_more_infos()
        self._load_manually_verified_pages_list()
        self._load_skipped_pictures_list()

    def _load_data(self) -> None:
        if self.dirs.data.is_dir():
            for filename in self.dirs.data.glob("*.scandata"):
                print(f"Loading: {filename}")
                doc_id = DocumentId(int(filename.stem))
                try:
                    with open(filename) as f:
                        self.data[doc_id] = extended_literal_eval(
                            f.read(),
                            {
                                "PicData": PicData,
                                "DocumentData": DocumentData,
                                "CHECKED": DetectionStatus.CHECKED,
                                "UNCHECKED": DetectionStatus.UNCHECKED,
                                "PROBABLY_CHECKED": DetectionStatus.PROBABLY_CHECKED,
                                "PROBABLY_UNCHECKED": DetectionStatus.PROBABLY_UNCHECKED,
                                "MARKED_AS_CHECKED": RevisionStatus.MARKED_AS_CHECKED,
                                "MARKED_AS_UNCHECKED": RevisionStatus.MARKED_AS_UNCHECKED,
                            },
                        )
                except Exception:
                    print(f"ERROR when reading {filename} :")
                    raise

    def _load_more_infos(self) -> None:
        """Retrieve manually entered information (if any)."""
        if self.files.more_infos.is_file():
            with open(self.files.more_infos, "r", newline="") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    try:
                        doc_id, name, student_id = row
                    except ValueError:
                        doc_id, name = row
                        student_id = ""
                    self.more_infos[DocumentId(int(doc_id))] = (StudentName(name), StudentId(student_id))
                print("Retrieved infos:", self.more_infos)

    def _load_manually_verified_pages_list(self):
        """Load the list of manually verified pages. They should not be verified anymore."""
        if self.files.verified.is_file():
            with open(self.files.verified, "r", encoding="utf8", newline="") as file:
                self.verified = set(Path(line.strip()) for line in file.readlines())
                print("Pages manually verified:")
                for path in self.verified:
                    print(f"    • {path}")

    def _load_skipped_pictures_list(self) -> None:
        """List skipped pictures. Next time, they will be skipped with no warning."""
        self.skipped = set(pic_names_iterator(self.data))
        if self.files.skipped.is_file():
            with open(self.files.skipped, "r", encoding="utf8", newline="") as file:
                self.skipped |= set(Path(line.strip()) for line in file.readlines())
                print("Pictures skipped:")
                for path in sorted(self.skipped):
                    print(f"    • {path}")

    def store_doc_data(self, pdf_hash: str, doc_id: DocumentId, p: int, matrix: ndarray = None) -> None:
        """Store current scan data to be able to interrupt the scan and then resume it later."""
        # Keyboard interrupts should be delayed until all the data are saved.
        keyboard_interrupt = False

        def memorize_interrupt(signum: int, frame: FrameType | None) -> None:
            nonlocal keyboard_interrupt
            keyboard_interrupt = True

        previous_sigint_handler = signal.signal(signal.SIGINT, memorize_interrupt)
        with open(self.dirs.data / f"{pdf_hash}.index", "a") as f:
            f.write(str(doc_id) + "\n")
        # We will store a compressed version of the matrix.
        # (It would consume too much memory else).
        if matrix is not None:
            save_webp(matrix, self.dirs.data / f"{doc_id}-{p}.webp")
        # WARNING !
        # The .scandata file must be stored last, in case the process is interrupted.
        # This prevents from having non-existing webp files declared in the .scandata file.
        with open(self.dirs.data / f"{doc_id}.scandata", "w") as f:
            f.write(repr(self.data[doc_id]))

        signal.signal(signal.SIGINT, previous_sigint_handler)
        if keyboard_interrupt:
            raise KeyboardInterrupt

    def store_additional_info(self, doc_id: int, name: str, student_ID: str) -> None:
        with open(self.files.more_infos, "a", newline="") as csvfile:
            writerow = csv.writer(csvfile).writerow
            writerow([str(doc_id), name, student_ID])

    def store_skipped_pic(self, skipped_pic: Path) -> None:
        with open(self.files.skipped, "a", newline="", encoding="utf8") as file:
            file.write(f"{skipped_pic}\n")

    def store_verified_pic(self, verified_pic: Path) -> None:
        with open(self.files.verified, "a", newline="", encoding="utf8") as file:
            file.write(f"{verified_pic}\n")

    def _generate_current_pdf_hashes(self) -> dict[str, Path]:
        """Return the hashes of all the pdf files found in `scan/` directory.

        Return: {hash: pdf path}
        """
        hashes = dict()
        for path in self.paths.input_dir.glob("**/*.pdf"):
            with open(path, "rb") as pdf_file:
                hashes[blake2b(pdf_file.read(), digest_size=20).hexdigest()] = path
        return hashes

    def _update_input_data(self) -> None:
        """Test if input data has changed, and update it if needed."""
        hash2pdf: dict[str, Path] = self._generate_current_pdf_hashes()

        self._remove_obsolete_files(hash2pdf)

        # For each new pdf files, extract all pictures
        to_extract: list[tuple[Path, Path]] = []
        with Pool() as pool:
            for pdfhash, pdfpath in hash2pdf.items():
                folder = self.dirs.pic / pdfhash
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

    def _remove_obsolete_files(self, hash2pdf):
        """For each removed pdf files, remove corresponding pictures and data."""
        for path in self.dirs.pic.iterdir():
            if not path.is_dir():
                raise RuntimeError(
                    f'Folder "{path.parent}" should only contain folders.\n'
                    "You may clean it manually, or remove it with following command:\n"
                    f'rm -r "{path.parent}"'
                )
            if path.name not in hash2pdf:
                rmtree(path)
        for path in self.dirs.data.glob("*.index"):
            if path.stem not in hash2pdf:
                with open(path) as f:
                    doc_ids = set(f.read().split())
                for doc_id in doc_ids:
                    (self.dirs.data / f"{doc_id}.scandata").unlink(missing_ok=True)
                    for webp in self.dirs.data.glob(f"{doc_id}-*.webp"):
                        webp.unlink()
                path.unlink()

    def get_checkboxes(
        self, doc_id: DocumentId, page: Page
    ) -> dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], ndarray]:
        """For the document `doc_id`, get all the arrays representing the checkbox' pictures."""
        checkboxes: dict[tuple[OriginalQuestionNumber, OriginalAnswerNumber], ndarray] = {}
        positions = self.data[doc_id].pages[page].positions
        matrix = self.get_matrix(doc_id, page)
        cell_size = self.data[doc_id].pages[page].cell_size
        for (q, a), (i, j) in positions.items():
            checkboxes[(q, a)] = matrix[i : i + cell_size, j : j + cell_size]
        return checkboxes

    def _export_doc_checkboxes(self, doc_id: DocumentId) -> None:
        """Save the checkboxes of the document `doc_id` as .webm images in a directory."""
        (doc_dir := self.dirs.checkboxes / str(doc_id)).mkdir(exist_ok=True)
        for page, pic_data in self.data[doc_id].pages.items():
            for (q, a), matrix in self.get_checkboxes(doc_id, page).items():
                detection_status = pic_data.detection_status[(q, a)]
                revision_status = pic_data.revision_status.get((q, a))
                webm = doc_dir / f"{q}-{a}-{detection_status}-{revision_status}.webm"
                save_webp(matrix, webm)

    def export_checkboxes(self) -> None:
        """Save checkboxes as .webm images in a directory.

        Only export the checkboxes of the documents whose at least one page has been manually verified.
        This is used to build regressions tests.
        """
        to_export: set[DocumentId] = {
            doc_id
            for doc_id, doc_data in self.data.items()
            if any(
                (q, a) in pic_data.revision_status
                for page, pic_data in doc_data.pages.items()
                for (q, a) in self.get_checkboxes(doc_id, page)
            )
        }
        for doc_id in to_export:
            self._export_doc_checkboxes(doc_id)

    def display_analyze_results(self, doc_id: DocumentId) -> None:
        """Print the result of the checkbox analysis for document `doc_id` in terminal."""
        print(f"\n[Document {doc_id}]\n")
        for page, pic_data in self.data[doc_id].pages.items():
            print(f"\nPage {page}:")
            for q, q0 in pic_data.questions_nums_conversion.items():
                # `q0` is the apparent number of the question, as displayed on the document,
                # while `q` is the internal number of the question (attributed before shuffling).
                print(f"\n{ANSI_CYAN}• Question {q0}{ANSI_RESET} (Q{q})")
                for a, is_correct in self.config.ordering[doc_id]["answers"][q]:
                    match pic_data.detection_status[(q, a)]:
                        case DetectionStatus.CHECKED:
                            c = "■"
                            ok = is_correct
                        case DetectionStatus.PROBABLY_CHECKED:
                            c = "■?"
                            ok = is_correct
                        case DetectionStatus.UNCHECKED:
                            c = "□"
                            ok = not is_correct
                        case DetectionStatus.PROBABLY_UNCHECKED:
                            c = "□?"
                            ok = not is_correct
                        case other:
                            raise ValueError(f"Unknown detection status: {other!r}.")
                    term_color = ANSI_GREEN if ok else ANSI_YELLOW
                    print(f"  {term_color}{c} {a}  {ANSI_RESET}", end="\t")
            print()

    def analyze_checkboxes(self, display=False):
        """Determine whether each checkbox is checked or not, and update data accordingly."""
        for doc_id, doc_data in self.data.items():
            if all(
                len(pic_data.detection_status) == len(pic_data.positions)
                for pic_data in doc_data.pages.values()
            ):
                # The checkboxes of this document were already analyzed during a previous scan.
                continue

            checkboxes = {
                key: val for page in doc_data.pages for key, val in self.get_checkboxes(doc_id, page).items()
            }
            detection_status = analyze_checkboxes(checkboxes)
            for page, pic_data in doc_data.pages.items():
                for q, a in pic_data.positions:
                    pic_data.answered.setdefault(q, set())
                    status = pic_data.detection_status[(q, a)] = detection_status[(q, a)]
                    if DetectionStatus.seems_checked(status):
                        pic_data.answered[q].add(a)

                # Store results, to be able to interrupt and resume scan.
                self.store_doc_data(str(Path(pic_data.pic_path).parent), doc_id, page)
            if display:
                self.display_analyze_results(doc_id)
            else:
                print(f"Analyzing checkboxes of document {doc_id}...")

        # if debug:
        #     viewer.display()
