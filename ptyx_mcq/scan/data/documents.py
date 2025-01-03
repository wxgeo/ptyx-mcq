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
    pictures: list[Picture]

    @property
    def has_conflicts(self) -> bool:
        # No conflict is the data are the same (checkboxes + names).
        return len(self.used_pictures) >= 2

    @property
    def used_pictures(self) -> list[Picture]:
        return [pic for pic in self.pictures if pic.use]

    # @property
    # def _conflicting_versions(self) -> list[Picture]:
    #     return list({pic.as_hashable_tuple(): pic for pic in self.pictures}.values())

    @property
    def pic(self) -> Picture:
        assert self.pictures
        if self.has_conflicts:
            raise ValueError(
                f"Only one picture expected, but {len(self.pictures)} conflicting versions found."
            )
        return self.pictures[0]

    def disable_duplicates(self) -> None:
        """Remove pictures which contain the same information, keeping only conflicting versions."""
        seen = set()
        for pic in self.pictures:
            if pic.use:
                t = pic.as_hashable_tuple()
                if t in seen:
                    pic.use = False
                else:
                    seen.add(t)

    def __iter__(self) -> Iterator[Picture]:
        return iter(self.pictures)


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
    def pictures(self) -> list[Picture]:
        """Return all the pictures associated with this document."""
        return [pic for page in self.pages.values() for pic in page.pictures]

    @property
    def used_pictures(self) -> list[Picture]:
        """Return all the pictures associated with this document."""
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
        return {q: question for page in self for pic in page for q, question in pic.questions.items()}

    @property
    def student(self) -> Student | None:
        return self.pages[PageNum(1)].pic.student

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

    def _as_str(self):
        return "\n".join(
            f"{page.page_num}: " + ", ".join(pic.short_path for pic in page.pictures) for page in self
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
        pictures = self.pictures

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

        config = self.scan_data.config
        pictures = self.pictures
        if cbx_states is not None:
            for pic, cbx_states in zip(pictures, cbx_states):
                for (q, a), state in cbx_states.items():
                    pic.questions[q].answers[a].state = state
                pic.save_checkboxes_state()

        if student is not None:
            for pic in pictures:
                if pic.page_num == 1:
                    if pic.student is None:
                        pic.student = student
                    elif pic.student.name == "":
                        # The ID have been read in a previous pass, but didn't match any known student at the time.
                        # In the while, the students name to ID mapping may have been updated (using `mcq fix` for example).
                        # So, let's try again to find the name corresponding to this ID.
                        name = config.students_ids.get(pic.student.id, StudentName(""))
                        if name != "":
                            pic.student = Student(name=name, id=pic.student.id)

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
