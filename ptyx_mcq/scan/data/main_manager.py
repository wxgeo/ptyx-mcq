import signal
from io import BytesIO
from pathlib import Path
from types import FrameType
from typing import Iterator

from numpy import ndarray

from ptyx_mcq.scan.data.analyze import PictureAnalyzer
from ptyx_mcq.scan.data.extraction import PdfCollection
from ptyx_mcq.scan.data.structures import (
    Picture,
    Document,
    Page,
)
from ptyx_mcq.scan.data.paths_manager import PathsHandler, DirsPaths, FilesPaths
from ptyx_mcq.tools.config_parser import (
    Configuration,
    get_answers_with_status,
    DocumentId,
    StudentName,
    StudentId,
    OriginalQuestionAnswersDict,
)


# def pic_names_iterator(data: dict[DocumentId, DocumentData]) -> Iterator[Path]:
#     """Iterate over all pics found in data (i.e. all the pictures already analysed)."""
#     for doc_data in data.values():
#         for pic_data in doc_data.pages.values():
#             path = Path(pic_data.pic_path)
#             # return pdfhash/picnumber.png
#             yield path.relative_to(path.parent.parent)


class ScanData:
    """Store and retrieve the data.

    Parameters:
        - config_path: either the path of a configuration file (`.ptyx.mcq.config.json`),
            or a directory containing a single configuration file.
        -
    """

    def __init__(self, config_path: Path, input_dir: Path = None, output_dir: Path = None):
        self.paths = PathsHandler(config_path=config_path, input_dir=input_dir, output_dir=output_dir)
        self.input_pdf = PdfCollection(self)

        # Additional information entered manually.
        self.more_infos: dict[DocumentId, tuple[StudentName, StudentId]] = {}
        # Manually verified pages.
        self.verified: set[Path] = set()
        self.skipped: set[Path] = set()
        self.correct_answers: dict[DocumentId, OriginalQuestionAnswersDict] = {}
        self.neutralized_answers: dict[DocumentId, OriginalQuestionAnswersDict] = {}
        # self.paths.make_dirs()
        self.config: Configuration = self.get_configuration(self.paths.configfile)
        self.picture_analyzer = PictureAnalyzer(self)
        # Navigate between documents.
        self._index: dict[DocumentId, Document] | None = None

    def __iter__(self) -> Iterator[Document]:
        return iter(self.index.values())

    @property
    def pages(self) -> Iterator[Page]:
        return iter(page for doc in self for page in doc)

    @property
    def pictures(self) -> Iterator[Picture]:
        return iter(pic for doc in self for page in doc for pic in page)

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
    def index(self) -> dict[DocumentId, Document]:
        if self._index is None:
            self._index = self._generate_index()
            # Keep a track of the index, to make debugging easier.
            self.save_index()
        return self._index

    def _generate_index(self) -> dict[DocumentId, Document]:
        """Return the index of all the documents.

        Most of the time, there must be only one single picture for each document page, but the page
        may have been scanned twice.
        """
        self._index = {}
        for pdf_hash, content in self.input_pdf.data.items():
            for pic_num, (calibration_data, identification_data) in content.items():
                self._index.setdefault(
                    doc_id := identification_data.doc_id, doc := Document(self, doc_id, {})
                ).pages.setdefault(
                    page_num := identification_data.page_num, page := Page(doc, page_num, [])
                ).pictures.append(
                    Picture(
                        page=page,
                        path=self.dirs.cache / f"{pdf_hash}/{pic_num}.webp",
                        calibration_data=calibration_data,
                        identification_data=identification_data,
                    )
                )
        return self._index

    def save_index(self) -> None:
        """
        Save index on disk in a human-readable format.

        This used only to make debugging easier.
        """
        for doc in self:
            doc.save_index()

    def get_configuration(self, path: Path) -> Configuration:
        """Read configuration file, load configuration and calculate maximal score too."""
        cfg: Configuration = Configuration.load(path)
        self.correct_answers = get_answers_with_status(cfg, correct=True)
        self.neutralized_answers = get_answers_with_status(cfg, correct=None)
        return cfg
