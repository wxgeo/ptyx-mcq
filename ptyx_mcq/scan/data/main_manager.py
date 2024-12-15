import signal
from io import BytesIO
from pathlib import Path
from types import FrameType

from numpy import ndarray

from ptyx_mcq.parameters import IMAGE_FORMAT
from ptyx_mcq.scan.data.analyze import PictureAnalyzer
from ptyx_mcq.scan.data.extraction import PdfCollection
from ptyx_mcq.scan.data.structures import (
    DocumentData,
    Picture,
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


# def pic_names_iterator(data: dict[DocumentId, DocumentData]) -> Iterator[Path]:
#     """Iterate over all pics found in data (i.e. all the pictures already analysed)."""
#     for doc_data in data.values():
#         for pic_data in doc_data.pages.values():
#             path = Path(pic_data.pic_path)
#             # return pdfhash/picnumber.png
#             yield path.relative_to(path.parent.parent)


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
        self.picture_analyzer = PictureAnalyzer(self)
        # Get for each document and each page the corresponding pictures paths.
        self._index: dict[DocumentId, dict[Page, set[Picture]]] | None = None

    def initialize(self, reset=False) -> None:
        """Load all information from files."""
        self.paths.make_dirs(reset)

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

    @property
    def index(self) -> dict[DocumentId, dict[Page, set[Picture]]]:
        if self._index is None:
            self._index = self._generate_index()
            # Keep a track of the index, to make debugging easier.
            self.save_index()
        return self._index

    def get_document_pictures(self, doc_id: DocumentId) -> set[Picture]:
        """Return all the pictures associated with the current document id."""
        return {pic for page_pics in self.index[doc_id].values() for pic in page_pics}

    def _generate_index(self) -> dict[DocumentId, dict[Page, set[Picture]]]:
        """Return a dictionary, given for each page of each document the corresponding pictures.

        Most of the time, there must be only one single picture for each document page, but the page
        may have been scanned twice.
        """
        self._index = {}
        for pdf_hash, content in self.input_pdf.data.items():
            for pic_num, pic_data in content.items():
                self._index.setdefault(pic_data.doc_id, {}).setdefault(pic_data.page, set()).add(
                    Picture(path=self.dirs.cache / f"{pdf_hash}/{pic_num}.webp", data=pic_data)
                )
        return self._index

    def save_index(self) -> None:
        (folder := self.dirs.data / "index").mkdir(exist_ok=True)
        for doc_id, doc_pics in self.index.items():
            (folder / str(doc_id)).write_text(
                "\n".join(
                    f"{page}: " + ", ".join(pic.encoded_path for pic in page_pics)
                    for page, page_pics in doc_pics.items()
                ),
                encoding="utf8",
            )

    def get_configuration(self, path: Path) -> Configuration:
        """Read configuration file, load configuration and calculate maximal score too."""
        cfg: Configuration = Configuration.load(path)
        self.correct_answers = get_answers_with_status(cfg, correct=True)
        self.neutralized_answers = get_answers_with_status(cfg, correct=None)
        return cfg

    # TODO: remove or update:
    # ========
    # OLD CODE
    # ========

    # def get_pics_list(self):
    #     """Return sorted pics list."""
    #     return sorted(f for f in self.dirs.cache.glob("*/*") if f.suffix.lower() == IMAGE_FORMAT)

    # def relative_pic_path(self, pic_path: str | Path):
    #     """Return picture path relatively to the `.scan/cache/` parent directory."""
    #     return Path(pic_path).relative_to(self.dirs.cache)
    #
    # def absolute_pic_path(self, pic_path: str | Path) -> Path:
    #     return self.dirs.cache / pic_path
    #
    # def absolute_pic_path_for_page(self, doc_id: DocumentId, page: Page) -> Path:
    #     return self.absolute_pic_path(self.data[doc_id].pages[page].pic_path)
    if False:

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
