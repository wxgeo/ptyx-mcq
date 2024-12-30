from pathlib import Path
from typing import Iterator


from ptyx_mcq.scan.data.extraction import PdfCollection
from ptyx_mcq.scan.data.paths_manager import PathsHandler, DirsPaths, FilesPaths
from ptyx_mcq.scan.data.documents import Document, Page
from ptyx_mcq.scan.data.pictures import Picture
from ptyx_mcq.scan.data.questions import Question, Answer
from ptyx_mcq.scan.picture_analyze.calibration import CalibrationData
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    StudentName,
    StudentId,
    OriginalQuestionAnswersDict,
    Configuration,
    get_answers_with_status,
    PageNum,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
    is_answer_correct,
)


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
        self.config: Configuration = self.get_configuration(self.paths.configfile)
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

    def analyze_pictures(self) -> None:
        for doc_id, doc in self.index.items():
            doc.update_info()
        print("Pictures data have been successfully retrieved.")

    @property
    def index(self) -> dict[DocumentId, Document]:
        if self._index is None:
            self._generate_index()
            # Keep a track of the index, to make debugging easier.
            self.save_index()
            print("Index generated.")
        assert self._index is not None
        return self._index

    def _generate_index(self) -> None:
        """Generate the tree of all the documents.

        The arborescence is the following:
            scan_data > document > page > picture > question > answer.

        Most of the time, there is only one single picture for each document page, but the page
        may have been scanned twice or more, resulting in several versions of the same page.
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
                        questions=self._generate_questions_tree(doc_id, page_num, calibration_data),
                    )
                )
        # Sort by document id and page number.
        self._index = {doc_id: self._index[doc_id] for doc_id in sorted(self._index)}
        for doc in self._index.values():
            doc.pages = {page_num: doc.pages[page_num] for page_num in sorted(doc.pages)}

    def _generate_questions_tree(
        self, doc_id: DocumentId, page_num: PageNum, calibration_data: CalibrationData
    ) -> dict[OriginalQuestionNumber, Question]:
        """
        Generate the tree of all the questions and answers of the given document, using configuration file.

        This is used when initializing the data structure.
        """
        answers_per_question: dict[OriginalQuestionNumber, dict[OriginalAnswerNumber, Answer]] = {}
        # The last page of a document may not contain any question at all, so the `.get(page_num, {})`.
        latex_positions = self.config.boxes[doc_id].get(page_num, {})
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

    def get_configuration(self, path: Path) -> Configuration:
        """Read configuration file, load configuration and calculate maximal score too."""
        cfg: Configuration = Configuration.load(path)
        self.correct_answers = get_answers_with_status(cfg, correct=True)
        self.neutralized_answers = get_answers_with_status(cfg, correct=None)
        return cfg
