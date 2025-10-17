import multiprocessing
from collections.abc import Callable

# noinspection PyProtectedMember
from multiprocessing.pool import AsyncResult
from pathlib import Path
from typing import Iterator

from ptyx.pretty_print import print_error, print_info

from ptyx_mcq.scan.data.extract import PdfCollectionExtractor
from ptyx_mcq.scan.data.paths_manager import PathsHandler, DirsPaths, FilesPaths
from ptyx_mcq.scan.data.documents import Document, Page
from ptyx_mcq.scan.data.pictures import Picture
from ptyx_mcq.scan.data.questions import Question, Answer
from ptyx_mcq.scan.data.students import Student
from ptyx_mcq.scan.picture_analyze.calibration import CalibrationData
from ptyx_mcq.scan.data.analyze.checkboxes import CheckboxAnalyzeResult
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    Configuration,
    PageNum,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    is_answer_correct,
)
from ptyx_mcq.tools.io_tools import generate_progression_callback, Silent


class ScanData:
    """Store and retrieve the data.

    Parameters:
        - config_path: either the path of a configuration file (`.ptyx.mcq.config.json`),
            or a directory containing a single configuration file.
        -
    """

    def __init__(self, config_path: Path, input_dir: Path = None, output_dir: Path = None):
        self.paths = PathsHandler(config_path=config_path, input_dir=input_dir, output_dir=output_dir)
        self.input_pdf_extractor = PdfCollectionExtractor(self)
        # Read the configuration file and load the mcq configuration.
        self.config = Configuration.load(self.paths.configfile)
        # Navigate between documents.
        self._index: dict[DocumentId, Document] | None = None
        self._log_file = self.dirs.log / "pictures-analyze.txt"
        if self._log_file.is_file():
            open(self._log_file, "w").close()

    def __iter__(self) -> Iterator[Document]:
        return iter(self.used_docs.values())

    @property
    def pages(self) -> Iterator[Page]:
        return iter(page for doc in self for page in doc)

    @property
    def pictures(self) -> Iterator[Picture]:
        return iter(pic for doc in self for page in doc for pic in page)

    def initialize(self, reset=False) -> None:
        """Load all information from files."""
        self.paths.make_dirs(reset)
        self.input_pdf_extractor.save_hashes()

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

    def extract_pictures(
        self, number_of_processes: int | None, progression: Callable[..., None] = None
    ) -> None:
        """Extract all pdf files' data and generate the documents tree."""
        self.input_pdf_extractor.collect_data(
            number_of_processes=number_of_processes, progression=progression
        )

    def analyze_pictures(
        self, number_of_processes: int | None, progression: Callable[..., None] = None
    ) -> None:
        """Analyze all documents pictures, retrieving checkboxes states and students names and ids."""
        if progression is None:
            progression = generate_progression_callback("Analyzing all documents data", len(self.index))
        if number_of_processes == 1:
            self._sequential_analyze(progression=progression)
        else:
            self._parallel_analyze(number_of_processes=number_of_processes, progression=progression)
        print("Pictures data have been successfully retrieved.")

    def run(self, number_of_processes: int | None = None, reset=False) -> None:
        """Main method: extract pictures and analyze them, generating the documents tree."""
        self.initialize(reset=reset)
        self.extract_pictures(number_of_processes=number_of_processes)
        self.analyze_pictures(number_of_processes=number_of_processes)

    def _parallel_analyze(self, number_of_processes: int | None, progression: Callable[..., None]) -> None:
        pool: multiprocessing.pool.Pool
        results: dict[DocumentId, AsyncResult] = {}
        with multiprocessing.Pool(number_of_processes) as pool:
            for doc_id, doc in self.index.items():
                results[doc_id] = pool.apply_async(
                    self.analyze_doc, (doc, self._log_file), callback=progression
                )
            for doc_id, result in results.items():
                self.index[doc_id].update_info(*result.get())

    def _sequential_analyze(self, progression: Callable[..., None]) -> None:
        for doc_id, doc in self.index.items():
            doc.update_info(*self.analyze_doc(doc, self._log_file))
            progression()

    @staticmethod
    def analyze_doc(
        doc: Document, log_file: Path
    ) -> tuple[list[Student | None], list[CheckboxAnalyzeResult] | None]:
        with Silent(log_file=log_file):
            return doc.analyze()

    @property
    def index(self) -> dict[DocumentId, Document]:
        """Index of all documents, included discarded ones."""
        if self._index is None:
            self._generate_index()
            # Keep a track of the index, to make debugging easier.
            self.save_index()
            print("Index generated.")
        assert self._index is not None
        return self._index

    @property
    def used_docs(self) -> dict[DocumentId, Document]:
        """Index of used documents (discarded ones are not included)."""
        return {doc_id: doc for doc_id, doc in self.index.items() if doc.use}

    def _generate_index(self) -> None:
        """Generate the tree of all the documents.

        The arborescence is the following:
            scan_data > document > page > picture > question > answer.

        Most of the time, there is only one single picture for each document page, but the page
        may have been scanned twice or more, resulting in several versions of the same page.
        """
        self._index = {}
        for pdf_hash, content in self.input_pdf_extractor.data.items():
            for pic_num, (calibration_data, identification_data) in content.items():
                # noinspection PyProtectedMember
                self._index.setdefault(
                    doc_id := identification_data.doc_id, doc := Document(self, doc_id, {})
                ).pages.setdefault(
                    page_num := identification_data.page_num, page := Page(doc, page_num, [])
                )._pictures.append(
                    Picture(
                        page=page,
                        path=(pic_path := self.dirs.cache / f"{pdf_hash}/{pic_num}.webp"),
                        original_pdf=self.input_pdf_extractor.hash2pdf[pdf_hash],
                        calibration_data=calibration_data,
                        identification_data=identification_data,
                        questions=self._generate_questions_tree(doc_id, page_num, calibration_data, pic_path),
                    )
                )
        # Sort by document id and page number.
        self._index = {doc_id: self._index[doc_id] for doc_id in sorted(self._index)}
        for doc in self._index.values():
            doc.pages = {page_num: doc.pages[page_num] for page_num in sorted(doc.pages)}

    def _generate_questions_tree(
        self, doc_id: DocumentId, page_num: PageNum, calibration_data: CalibrationData, pic_path: Path
    ) -> dict[OriginalQuestionNumber, Question]:
        """
        Generate the tree of all the questions and answers of the given document, using configuration file.

        This is used when initializing the data structure.
        """
        answers_per_question: dict[OriginalQuestionNumber, dict[OriginalAnswerNumber, Answer]] = {}
        # The last page of a document may not contain any question at all, so the `.get(page_num, {})`.
        try:
            latex_positions = self.config.boxes[doc_id].get(page_num, {})
        except KeyError as e:
            print_info(f"Valid document IDs: {', '.join(str(_id) for _id in self.config.boxes)}")
            print_error(f"Unknown document ID: {doc_id} (file: {pic_path})")
            raise KeyError(
                f"Unknown document ID: {doc_id}\n"
                "Hint: are you sure you didn't print and scan another document (maybe a previous version)?"
            )
        for q, a in sorted(latex_positions):
            x, y = latex_positions[(q, a)]
            position = calibration_data.xy2ij(x, y)
            answers_per_question.setdefault(q, {})[a] = Answer(
                answer_num=a, position=position, is_correct=is_answer_correct(q, a, self.config, doc_id)
            )
        return {
            q: Question(question_num=q, answers={a: answer for a, answer in answers.items()})
            for q, answers in answers_per_question.items()
        }

    def save_index(self) -> None:
        """
        Save index on disk in a human-readable format.

        This used only to make debugging easier.
        """
        for doc in self:
            doc.save_index()
