from dataclasses import dataclass
from typing import Iterator, TYPE_CHECKING

from numpy import ndarray
from ptyx_mcq.scan.data.questions import Question

from ptyx_mcq.scan.data.analyze.checkboxes import analyze_checkboxes, CheckboxAnalyzeResult
from ptyx_mcq.scan.data.pictures import Picture
from ptyx_mcq.scan.data.students import Student
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    StudentName,
    OriginalQuestionNumber,
    PageNum,
    StudentId,
    OriginalAnswerNumber,
)

if TYPE_CHECKING:
    from ptyx_mcq.scan.data import ScanData, Picture


@dataclass
class Page:
    doc: "Document"
    page_num: PageNum
    _pictures: list[Picture]

    @property
    def has_conflicts(self) -> bool:
        """Test whether there are several (undiscarded) pictures associated with this page."""
        return len(self.used_pictures) >= 2

    @property
    def all_pictures(self) -> Iterator[Picture]:
        return iter(self._pictures)

    @property
    def used_pictures(self) -> list[Picture]:
        """
        Return the page pictures, except for the discarded one.

        While there should be only one picture associated with one page, they may be conflicts
        resulting in several pictures (aka. versions) for the same page.
        (Most of the time, this indicates that the same page as been scanned twice by the user).
        """
        return [pic for pic in self.all_pictures if pic.use]

    # @property
    # def _conflicting_versions(self) -> list[Picture]:
    #     return list({pic.as_hashable_tuple(): pic for pic in self.pictures}.values())

    @property
    def pic(self) -> Picture:
        pictures = self.used_pictures
        assert pictures
        if len(pictures) >= 2:
            raise ValueError(f"Only one picture expected, but {len(pictures)} conflicting versions found.")
        return pictures[0]

    def disable_duplicates(self) -> None:
        """Remove pictures which contain the same information, keeping only conflicting versions."""
        seen = set()
        for pic in self.used_pictures:
            t = pic.as_hashable_tuple()
            if t in seen:
                pic.use = False
            else:
                seen.add(t)

    def __iter__(self) -> Iterator[Picture]:
        return iter(self.used_pictures)


@dataclass
class Document:
    scan_data: "ScanData"
    doc_id: DocumentId
    pages: dict[PageNum, Page]
    score_per_question: dict[OriginalQuestionNumber, float] | None = None

    @property
    def score(self) -> float | None:
        score = 0.0
        for question in self.questions.values():
            if (q_score := question.score) is None:
                return None
            score += q_score
        return score

    @property
    def first_page(self) -> Page | None:
        return self.pages.get(PageNum(1))

    @property
    def all_pictures(self) -> Iterator[Picture]:
        """Return all the pictures associated with this document, even discarded ones."""
        return iter(pic for page in self.pages.values() for pic in page.all_pictures)

    @property
    def used_pictures(self) -> list[Picture]:
        """
        Return the pictures associated with this document, except for discarded ones.

        Discarded pictures have their attribute `.use` set to False.
        (Pictures may be discarded during the conflict resolution process.)
        """
        return [pic for page in self.pages.values() for pic in page.used_pictures]

    # @property
    # def answered(self) -> ChainMap[OriginalQuestionNumber, set[OriginalAnswerNumber]]:
    #     """Answers checked by the student for each question."""
    #     return ChainMap(*(page.pic.answered for page in self.pages.values()))

    def __iter__(self) -> Iterator[Page]:
        return iter(self.pages.values())

    @property
    def questions(self) -> dict[OriginalQuestionNumber, Question]:
        """All the (original) question numbers found in the picture."""
        return {q: question for page in self for q, question in page.pic.questions.items()}

    @property
    def student(self) -> Student | None:
        return self.pages[PageNum(1)].pic.student

    @student.setter
    def student(self, value: Student) -> None:
        if self.first_page is None:
            raise ValueError(f"No first page found for document {self.doc_id}!")
        self.first_page.pic.student = value

    @property
    def student_name(self) -> StudentName:
        return StudentName("") if self.student is None else self.student.name

    @property
    def student_id(self) -> StudentId:
        return StudentId("") if self.student is None else self.student.id

    @property
    def missing_checkboxes_states(self) -> bool:
        return any(
            answer.state is None for pic in self.used_pictures for question in pic for answer in question
        )

    @property
    def checkboxes_need_review(self) -> bool:
        return any(picture.checkboxes_need_review for picture in self.used_pictures)

    def _as_str(self):
        return "\n".join(
            f"{page.page_num}: " + ", ".join(pic.short_path for pic in page.all_pictures) for page in self
        )

    def save_index(self):
        """
        Save an index of all the document pages and the corresponding pictures.

        The generated file is only used for debugging.
        """
        (self.scan_data.dirs.index / str(self.doc_id)).write_text(self._as_str() + "\n", encoding="utf8")

    def analyze(self) -> tuple[Student | None, list[CheckboxAnalyzeResult] | None]:
        """Retrieve the state of each checkbox (checked or not) and the student id and name.

        Attempt to load it from disk.
        If not found, generate the info by evaluating the blackness of each checkbox.
        """
        matrices: dict[str, ndarray] = {}
        pictures = self.all_pictures

        # Step 1: evaluate checkboxes state if needed.
        cbx_states: list[CheckboxAnalyzeResult] | None = None
        if not all(pic.checkboxes_analyzed for pic in pictures):
            # No corresponding data on the disk, generate the data, and write it on the disk.
            print(f"Analyzing checkboxes in document: {self.doc_id}")
            # Put pictures arrays in cache (there are not so much of them for a single document),
            # since they will be used both to analyze the answers and to read the student id.
            matrices = {pic.short_path: pic.as_matrix() for pic in pictures}
            cbx = [pic.get_checkboxes(matrices[pic.short_path]) for pic in pictures]
            # Analyze each checkbox.
            # All the checkboxes of the same document must be inspected together
            # to improve the checkboxes' states review, since a given student will probably
            # check all its document boxes in a consistent way.
            cbx_states = analyze_checkboxes(cbx)

        # Step 2: retrieve student name and ID if needed.
        student: Student | None = None
        for pic in pictures:
            if pic.page_num == 1:
                if pic.student is None:
                    student = pic.retrieve_student(matrices.get(pic.short_path, pic.as_matrix()))
        return student, cbx_states

    def update_info(self, student: Student | None, cbx_states: list[CheckboxAnalyzeResult] | None) -> None:
        """Update the state of each checkbox (checked or not) and the student id and name.

        Save those changes on disk, to be able to interrupt and resume the scan if needed."""
        if cbx_states is not None:
            for pic, pic_cbx_states in zip(self.all_pictures, cbx_states):
                for (q, a), state in pic_cbx_states.items():
                    pic.questions[q].answers[a].state = state
                pic.save_checkboxes_state()
        if student is not None:
            self.student = student

    @property
    def detection_status(self):
        return {
            (q, a): answer.initial_state
            for q, question in self.questions.items()
            for a, answer in question.answers.items()
        }

    @property
    def revision_status(self):
        return {
            (q, a): answer.amended_state
            for q, question in self.questions.items()
            for a, answer in question.answers.items()
        }

    @property
    def answered(self) -> dict[OriginalQuestionNumber, set[OriginalAnswerNumber]]:
        """Answers checked by the student for each question."""
        return {question: answers for page in self for question, answers in page.pic.answered.items()}
