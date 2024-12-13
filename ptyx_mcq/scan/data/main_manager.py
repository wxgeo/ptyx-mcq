import csv
import signal
from io import BytesIO
from pathlib import Path
from types import FrameType
from typing import Iterator

from PIL import Image
from numpy import ndarray, array

from ptyx.shell import print_error

from ptyx_mcq.parameters import IMAGE_FORMAT
from ptyx_mcq.scan.data.analyze.checkboxes import CheckboxesDataAnalyzer
from ptyx_mcq.scan.data.extraction import PdfCollection, PdfHash, PicNum
from ptyx_mcq.scan.data.structures import (
    DocumentData,
    PicData,
    DetectionStatus,
    RevisionStatus,
)
from ptyx_mcq.scan.data.paths_manager import PathsHandler, DirsPaths, FilesPaths
from ptyx_mcq.tools.config_parser import (
    Configuration,
    get_answers_with_status,
    DocumentId,
    StudentName,
    StudentId,
    OriginalQuestionAnswersDict,
    Page,
)
from ptyx_mcq.tools.extend_literal_eval import extended_literal_eval


def pic_names_iterator(data: dict[DocumentId, DocumentData]) -> Iterator[Path]:
    """Iterate over all pics found in data (i.e. all the pictures already analysed)."""
    for doc_data in data.values():
        for pic_data in doc_data.pages.values():
            path = Path(pic_data.pic_path)
            # return pdfhash/picnumber.png
            yield path.relative_to(path.parent.parent)


def split_pic_path(path: Path) -> tuple[PdfHash, PicNum]:
    """Return the pdf hash and the picture's number from the picture's path."""
    return PdfHash(path.parent.name), PicNum(int(path.stem))


class DataHandler:
    """Store and retrieve the data.

    Parameters:
        - config_path: either the path of a configuration file (`.ptyx.mcq.config.json`),
            or a directory containing a single configuration file.
        -
    """

    def __init__(self, config_path: Path, input_dir: Path = None, output_dir: Path = None):
        self.paths = PathsHandler(config_path=config_path, input_dir=input_dir, output_dir=output_dir)
        self.input_pdf = PdfCollection(self)
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
        # When two versions of the same document are detected, a temporary document id
        # is given to the duplicates, to preserve id unicity until conflicts resolution phase.
        # The true id of the duplicate documents is stored in dict `self.duplicates_alias`:
        # `self.duplicates_alias`: list all alias id used for a scanned document's page.
        # self.duplicates_alias: dict[[DocumentId, Page], list[DocumentId]] = {}
        # Counter used to generate unique temporary id.
        # This is a negative integer, since all temporary ids will be negative integers.
        self._tmp_ids_counter = -1
        self.checkboxes = CheckboxesDataAnalyzer(self)
        # Get for each document and each page the corresponding pictures paths.
        self._index: dict[DocumentId, dict[Page, set[Path]]] | None = None

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

    def get_pic_data(self, path: Path) -> PicData:
        pdf_hash, pic_num = split_pic_path(path)
        return self.input_pdf.data[pdf_hash][pic_num]

    def write_log(self, msg: str) -> None:
        with open(self.paths.logfile_path, "a", encoding="utf8") as logfile:
            logfile.write(msg)

    @property
    def index(self) -> dict[DocumentId, dict[Page, set[Path]]]:
        if self._index is None:
            self._index = self._generate_index()
        return self._index

    def get_document_pic_paths(self, doc_id: DocumentId) -> set[Path]:
        """Get the paths of all the pics associated with the current document id."""
        return {path for page_paths in self.index[doc_id].values() for path in page_paths}

    def _generate_index(self) -> dict[DocumentId, dict[Page, set[Path]]]:
        """Return a dictionary, given for each page of each document the corresponding picture files.

        Most of the time, there must be only one single picture for each document page, but the page
        may have been scanned twice.
        """
        self._index = {}
        for pdf_hash, content in self.input_pdf.data.items():
            for pic_num, pic_data in content.items():
                self._index.setdefault(pic_data.doc_id, {}).setdefault(pic_data.page, set()).add(
                    pic_data.pic_path
                )
        return self._index

    def save_index(self) -> None:
        (folder := self.dirs.data / "index").mkdir(exist_ok=True)
        for doc_id, doc_paths in self.index.items():
            (folder / str(doc_id)).write_text(
                "\n".join(
                    f"{page}: "
                    + ", ".join(str(path.with_suffix("").relative_to(path.parent.parent)) for path in paths)
                    for page, paths in doc_paths.items()
                ),
                encoding="utf8",
            )

    @staticmethod
    def get_pic(pic_path: Path) -> Image.Image:
        if not pic_path.is_file():
            print_error(f"File not found: `{pic_path}`")
            raise FileNotFoundError(f'"{pic_path}"')
        try:
            return Image.open(str(pic_path))
        except Exception:
            print_error(f"Error when opening {pic_path}.")
            raise

    @classmethod
    def get_matrix(cls, pic_path: Path) -> ndarray:
        return array(cls.get_pic(pic_path).convert("L")) / 255

    # ==== OLD CODE ====

    def get_pics_list(self):
        """Return sorted pics list."""
        return sorted(f for f in self.dirs.pic.glob("*/*") if f.suffix.lower() == IMAGE_FORMAT)

    def relative_pic_path(self, pic_path: str | Path):
        """Return picture path relatively to the `.scan/pic/` parent directory."""
        return Path(pic_path).relative_to(self.dirs.pic)

    def absolute_pic_path(self, pic_path: str | Path) -> Path:
        return self.dirs.pic / pic_path

    def absolute_pic_path_for_page(self, doc_id: DocumentId, page: Page) -> Path:
        return self.absolute_pic_path(self.data[doc_id].pages[page].pic_path)

    def get_configuration(self, path: Path) -> Configuration:
        """Read configuration file, load configuration and calculate maximal score too."""
        cfg: Configuration = Configuration.load(path)
        self.correct_answers = get_answers_with_status(cfg, correct=True)
        self.neutralized_answers = get_answers_with_status(cfg, correct=None)
        return cfg

    def initialize(self, reset=False) -> None:
        """Load all information from files."""
        self.paths.make_dirs(reset)
        # self._update_input_data()
        # # Load data from previous run.
        # self._load_data()
        # self._load_more_infos()
        # self._load_manually_verified_pages_list()
        # self._load_skipped_pictures_list()

    # def _load_data(self) -> None:
    #     """Load cached data from previous scans, if any."""
    #     if self.dirs.data.is_dir():
    #         for filename in self.dirs.data.glob("*.scandata"):
    #             print(f"Loading: {filename}")
    #             doc_id = DocumentId(int(filename.stem))
    #             try:
    #                 with open(filename) as f:
    #                     self.data[doc_id] = extended_literal_eval(
    #                         f.read(),
    #                         {
    #                             "PicData": PicData,
    #                             "DocumentData": DocumentData,
    #                             "CHECKED": DetectionStatus.CHECKED,
    #                             "UNCHECKED": DetectionStatus.UNCHECKED,
    #                             "PROBABLY_CHECKED": DetectionStatus.PROBABLY_CHECKED,
    #                             "PROBABLY_UNCHECKED": DetectionStatus.PROBABLY_UNCHECKED,
    #                             "MARKED_AS_CHECKED": RevisionStatus.MARKED_AS_CHECKED,
    #                             "MARKED_AS_UNCHECKED": RevisionStatus.MARKED_AS_UNCHECKED,
    #                         },
    #                     )
    #             except Exception:
    #                 print(f"ERROR when reading {filename} :")
    #                 raise

    # def _load_more_infos(self) -> None:
    #     """Retrieve manually entered information (if any)."""
    #     if self.files.more_infos.is_file():
    #         with open(self.files.more_infos, "r", newline="") as csvfile:
    #             reader = csv.reader(csvfile)
    #             for row in reader:
    #                 try:
    #                     doc_id, name, student_id = row
    #                 except ValueError:
    #                     doc_id, name = row
    #                     student_id = ""
    #                 self.more_infos[DocumentId(int(doc_id))] = (StudentName(name), StudentId(student_id))
    #             print("Retrieved infos:", self.more_infos)
    #
    # def _load_manually_verified_pages_list(self):
    #     """Load the list of manually verified pages. They should not be verified anymore."""
    #     if self.files.verified.is_file():
    #         with open(self.files.verified, "r", encoding="utf8", newline="") as file:
    #             self.verified = set(Path(line.strip()) for line in file.readlines())
    #             print("Pages manually verified:")
    #             for path in self.verified:
    #                 print(f"    • {path}")

    # def _load_skipped_pictures_list(self) -> None:
    #     """List skipped pictures. Next time, they will be skipped with no warning."""
    #     # All pictures already analyzed in a previous run will be skipped.
    #     self.skipped = set(pic_names_iterator(self.data))
    #     # `self.files.skipped` is the path of a text file, listing additional pictures to skip (blank pages for ex.)
    #     if self.files.skipped.is_file():
    #         with open(self.files.skipped, "r", encoding="utf8", newline="") as file:
    #             self.skipped |= set(Path(line.strip()) for line in file.readlines())
    #             print("Pictures skipped:")
    #             for path in sorted(self.skipped):
    #                 print(f"    • {path}")

    def store_doc_data(
        self, pdf_hash: str, doc_id: DocumentId, p: int, matrix: ndarray | BytesIO | None = None
    ) -> None:
        """Store current scan data to be able to interrupt the scan and then resume it later.

        Argument `matrix` may be either a raw numpy array, or a BytesIO instance already in webp format.
        """
        # Keyboard interrupts should be delayed until all the data are saved.
        keyboard_interrupt = False

        def memorize_interrupt(signum: int, frame: FrameType | None) -> None:
            nonlocal keyboard_interrupt
            keyboard_interrupt = True

        previous_sigint_handler = signal.signal(signal.SIGINT, memorize_interrupt)
        # File <pdfhash>.index will index all the documents ids corresponding to this pdf.
        index_file = self.dirs.data / f"{pdf_hash}.index"
        if not index_file.is_file() or str(doc_id) not in set(index_file.read_text("utf-8").split()):
            with open(index_file, "a") as f:
                f.write(f"{doc_id}\n")
        # We will store a compressed version of the matrix (as a webp image).
        # (It would consume too much memory else).
        if isinstance(matrix, BytesIO):
            (self.dirs.data / f"{doc_id}-{p}.webp").write_bytes(matrix.getvalue())
        elif isinstance(matrix, ndarray):
            save_webp(matrix, self.dirs.data / f"{doc_id}-{p}.webp")
        # WARNING !
        # The `<doc_id>.scandata` file must be stored last, in case the process is interrupted.
        # This prevents from having non-existing webp files declared in a .scandata file.
        self.write_scandata_file(doc_id)

        signal.signal(signal.SIGINT, previous_sigint_handler)
        if keyboard_interrupt:
            raise KeyboardInterrupt

    def write_scandata_file(self, doc_id: DocumentId) -> None:
        """Create (or re-create) the .scandata file containing all the data for document `doc_id`."""
        with open(self.dirs.data / f"{doc_id}.scandata", "w") as f:
            f.write(repr(self.data[doc_id]))

    def store_additional_info(self, doc_id: DocumentId, name: StudentName, student_id: StudentId) -> None:
        with open(self.files.more_infos, "a", newline="") as csvfile:
            writerow = csv.writer(csvfile).writerow
            writerow([str(doc_id), name, student_id])

    def store_skipped_pic(self, skipped_pic: Path) -> None:
        with open(self.files.skipped, "a", newline="", encoding="utf8") as file:
            file.write(f"{skipped_pic}\n")

    def store_verified_pic(self, verified_pic: Path) -> None:
        with open(self.files.verified, "a", newline="", encoding="utf8") as file:
            file.write(f"{verified_pic}\n")

    def remove_doc_files(self, doc_id: DocumentId) -> None:
        """Remove all the data files associated with the document of id `doc_id`."""
        (self.dirs.data / f"{doc_id}.scandata").unlink(missing_ok=True)
        for webp in self.dirs.data.glob(f"{doc_id}-*.webp"):
            webp.unlink()
