import multiprocessing
import operator
from multiprocessing.pool import AsyncResult
from pathlib import Path
from shutil import rmtree
from typing import Iterator, Callable

from ptyx.pretty_print import print_info, print_error
from ptyx_mcq.scan.data.documents import Document, Page, AnalyzeResult
from ptyx_mcq.scan.data.extract import PdfCollectionExtractor, PageData, Event
from ptyx_mcq.scan.data.paths_manager import PathsHandler, DirsPaths, FilesPaths
from ptyx_mcq.scan.data.pictures import Picture
from ptyx_mcq.scan.data.questions import Answer, Question
from ptyx_mcq.scan.data.students import Student
from ptyx_mcq.scan.picture_analyze.calibration import CalibrationData
from ptyx_mcq.tools.io_tools import generate_progression_callback, Silent
from ptyx_mcq.tools.parse_config.config import Configuration, is_answer_correct
from ptyx_mcq.tools.parse_config.subtypes import (
    DocumentId,
    PageNum,
    OriginalQuestionNumber,
    OriginalAnswerNumber,
)


class ScanData:
    """Store and retrieve the data.

    Parameters:
        - config_path: either the path of a configuration file (`.ptyx.mcq.config.json`),
            or a directory containing a single configuration file.
        - input_dir: the directory of the PDF files containing the scanned students' work (default: scan/)
        - output_dir: the directory where all the generated files will take place (default: out/)

    To start the scan process, call `Scandata.run()`.
    """

    def __init__(self, config_path: Path, input_dir: Path | None = None, output_dir: Path | None = None):
        self.paths = PathsHandler(config_path=config_path, input_dir=input_dir, output_dir=output_dir)
        self.input_pdf_extractor = PdfCollectionExtractor(self)
        # Read the configuration file and load the mcq configuration.
        self.config = Configuration.load(self.paths.configfile)
        # Navigate between documents.
        self._index: dict[DocumentId, Document] | None = None
        self._log_file = self.dirs.log / "pictures-analyze.txt"
        if self._log_file.is_file():
            open(self._log_file, "w").close()

    @property
    def is_initialized(self) -> bool:
        """

        This can be used by a third-party tool to detect if a scan process was already run.

        Testing directly the state of `self.index` is not possible, since the index is build on demand,
        so any request on `self.index` will generate a scan process if needed.
        """
        return self.input_pdf_extractor.is_initialized

    def reset(self) -> None:
        """
        Remove all scan generated data.

        This is used by `ptyx-mcq-corrector` to reinitialize the scan operation.
        """
        self.initialize(reset=True)
        self._generate_index()

    def reset_review(self) -> None:
        """
        Remove all review generated data.

        This is used by `ptyx-mcq-corrector` to reinitialize the review operation.
        """
        rmtree(path := self.paths.dirs.fix, ignore_errors=True)
        self._generate_index()
        print_info(f"Folder '{path}' removed.")

    def __iter__(self) -> Iterator[Document]:
        return iter(self.used_docs_index.values())

    def sorted_by(self, attribute: str) -> list[Document]:
        """
        Return a list of the documents sorted by a document attribute.

        For example: documents.sorted_by("student_name")
        """
        return sorted(self, key=operator.attrgetter(attribute))

    @property
    def pages(self) -> Iterator[Page]:
        return iter(page for doc in self for page in doc)

    @property
    def pictures(self) -> Iterator[Picture]:
        return iter(pic for doc in self for page in doc for pic in page)

    def initialize(self, reset=False) -> None:
        """Generate dirs and reset them if needed. Save PDF hashes."""
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
        self,
        number_of_processes: int | None,
        progression: Callable[[PageData | None], None] | None = None,
        abort_event: Event | None = None,
    ) -> None:
        """Extract all pdf files' data and generate the documents tree."""
        self.input_pdf_extractor.collect_data(
            number_of_processes=number_of_processes, progression=progression, abort_event=abort_event
        )

    def analyze_pictures(
        self,
        number_of_processes: int | None,
        progression: Callable[[AnalyzeResult], None] | None = None,
        abort_event: Event | None = None,
    ) -> None:
        """Analyze all documents pictures, retrieving checkboxes states and students names and ids."""
        if progression is None:
            progression = generate_progression_callback(
                "Analyzing all documents data", len(self.all_docs_index)
            )
        if number_of_processes == 1:
            self._sequential_analyze(progression=progression, abort_event=abort_event)
        else:
            self._parallel_analyze(
                number_of_processes=number_of_processes, progression=progression, abort_event=abort_event
            )
        print("Pictures data have been successfully retrieved.")

    def run(
        self,
        number_of_processes: int | None = None,
        reset=False,
        progression: Callable[[AnalyzeResult | PageData | None], None] | None = None,
        abort_event: Event | None = None,
    ) -> None:
        """
        Main method: extract pictures and analyze them, generating the documents tree.

        abort_event is used by external tools to be able to stop the process.
        """
        self.initialize(reset=reset)
        if abort_event is None or not abort_event.is_set():
            self.extract_pictures(
                number_of_processes=number_of_processes, progression=progression, abort_event=abort_event
            )
        if abort_event is None or not abort_event.is_set():
            # Don't launch analyze_pictures() if abort_event is set, since it accesses data.
            # This would relaunch automatically the aborted pictures' extraction!
            self.analyze_pictures(
                number_of_processes=number_of_processes, progression=progression, abort_event=abort_event
            )

    def _parallel_analyze(
        self,
        number_of_processes: int | None,
        progression: Callable[[AnalyzeResult], None],
        abort_event: Event | None = None,
    ) -> None:
        pool: multiprocessing.pool.Pool
        results: dict[DocumentId, AsyncResult] = {}
        with multiprocessing.Pool(number_of_processes) as pool:
            for doc_id, doc in self.all_docs_index.items():
                results[doc_id] = pool.apply_async(
                    self.analyze_doc, (doc, self._log_file), callback=progression
                )
            for doc_id, result in results.items():
                if abort_event is not None and abort_event.is_set():
                    return
                self.all_docs_index[doc_id].update_info(*result.get())

    def _sequential_analyze(
        self,
        progression: Callable[[AnalyzeResult], None],
        abort_event: Event | None = None,
    ) -> None:
        for doc_id, doc in self.all_docs_index.items():
            if abort_event is not None and abort_event.is_set():
                return
            analyze_results = self.analyze_doc(doc, self._log_file)
            doc.update_info(*analyze_results)
            progression(analyze_results)

    @staticmethod
    def analyze_doc(doc: Document, log_file: Path) -> AnalyzeResult:
        with Silent(log_file=log_file):
            return doc.analyze()

    @property
    def all_docs_index(self) -> dict[DocumentId, Document]:
        """
        Index of all documents, included discarded ones.

        To get only the relevant documents, you should use the property `.used_docs_index` instead.
        """
        if self._index is None:
            self._generate_index()
            # Keep a track of the index, to make debugging easier.
            self.save_index()
            print("Index generated.")
        assert self._index is not None
        return self._index

    @property
    def used_docs_index(self) -> dict[DocumentId, Document]:
        """
        Index of all used documents (discarded ones are not included).

        This is generally the property you're looking for. However, if you need all
        documents, including the discarded ones, use the property `.all_docs_index` instead.
        """
        return {doc_id: doc for doc_id, doc in self.all_docs_index.items() if doc.use}

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
                    doc_id := identification_data.doc_id,
                    doc := Document(self, doc_id, {}),
                ).pages_index.setdefault(
                    page_num := identification_data.page_num,
                    page := Page(doc, page_num, []),
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
            doc.pages_index = {page_num: doc.pages_index[page_num] for page_num in sorted(doc.pages_index)}

    def _generate_questions_tree(
        self,
        doc_id: DocumentId,
        page_num: PageNum,
        calibration_data: CalibrationData,
        pic_path: Path,
    ) -> dict[OriginalQuestionNumber, Question]:
        """
        Generate the tree of all the questions and answers of the given document, using configuration file.

        This is used when initializing the data structure.
        """
        answers_per_question: dict[OriginalQuestionNumber, dict[OriginalAnswerNumber, Answer]] = {}
        # The last page of a document may not contain any question at all, so the `.get(page_num, {})`.
        try:
            latex_positions = self.config.boxes[doc_id].get(page_num, {})
        except KeyError:
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
                answer_num=a,
                position=position,
                is_correct=is_answer_correct(q, a, self.config, doc_id),
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

    def students(self) -> list[Student]:
        """
        List all the currently detected students.

        :return: a list of students.
        """
        return [student for doc in self if (student := doc.student) is not None]

    def synchronize_students_names(self) -> None:
        """
        Synchronize the students' names using their ID and the configuration file.

        This is useful when the configuration's file have been updated with a new list of students.
        """
        for doc in self:
            name = self.config.students_ids.get(student_id := doc.student_id)
            if name is not None:
                doc.student = Student(id=student_id, name=name)

    def get_student_doc(self, student: Student) -> Document | None:
        """
        Find the document associated with the given student.

        The scan process must have been done before, else `None` is returned.
        If no document is associated with this student, `None` is returned as well.
        """
        for doc in self.used_docs_index.values():
            if doc.student == student:
                return doc
        return None
