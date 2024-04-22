import string
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from numpy import ndarray

from ptyx.shell import print_error, print_warning, print_info

from ptyx_mcq.tools.rgb import Color, RGB
from ptyx_mcq.scan.data_gestion.data_handler import DataHandler
from ptyx_mcq.scan.data_gestion.document_data import (
    Page,
    DetectionStatus,
    RevisionStatus,
    PicData,
)
from ptyx_mcq.scan.picture_analyze.image_viewer import ImageViewer
from ptyx_mcq.tools.math import levenshtein_distance
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    ApparentQuestionNumber,
    apparent2real,
    ApparentAnswerNumber,
    StudentName,
    StudentId,
)


DuplicateNamesDict = dict[StudentName, list[DocumentId]]
UnnamedDocsList = list[DocumentId]
AmbiguousPagesList = list[tuple[DocumentId, Page]]


@dataclass
class DataCheckResult:
    unnamed_docs: UnnamedDocsList
    duplicate_names: DuplicateNamesDict
    ambiguous_answers: AmbiguousPagesList


def report_data_issues(check_result: DataCheckResult) -> None:
    for doc_id in check_result.unnamed_docs:
        print_warning(f"• No student name for document {doc_id}.")
    for name, doc_ids in check_result.duplicate_names.items():
        print_warning(f"• Same student name {name!r} on documents {','.join(map(str, doc_ids))}.")


class DataChecker:
    """Check for missing data."""

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = self.data_storage.data

    def run(self) -> DataCheckResult:
        # First, complete missing information with previous scan data, if any.
        for doc_id, (student_name, student_id) in self.data_storage.more_infos.items():
            self.data[doc_id].name = student_name
            self.data[doc_id].student_id = student_id
        print("Searching for unnamed documents...")
        unnamed_docs = self.get_unnamed_docs()
        print("Searching for duplicate names...")
        duplicate_names = self.find_duplicate_names()
        print("Searching for ambiguous answers...")
        ambiguous_answers = self.find_ambiguous_answers()
        return DataCheckResult(
            unnamed_docs=unnamed_docs, duplicate_names=duplicate_names, ambiguous_answers=ambiguous_answers
        )

    def get_unnamed_docs(self) -> list[DocumentId]:
        """Get the list of all unnamed documents."""
        return [doc_id for doc_id, doc_data in self.data.items() if doc_data.name == ""]

    def find_duplicate_names(self) -> DuplicateNamesDict:
        """Detect if several documents have the same student name.

        Return a dictionary associating each conflicting name with the corresponding documents.
        """
        seen_names: dict[StudentName, DocumentId] = {}
        duplicate_names: dict[StudentName, list[DocumentId]] = {}
        for doc_id, doc_data in self.data.items():
            name = doc_data.name
            if name in seen_names:
                duplicate_names.setdefault(name, [seen_names[name]]).append(doc_id)
                # matching_doc_id = seen_names[name]
                # matching_doc_data = self.data[matching_doc_id]
            else:
                seen_names[name] = doc_id
        return duplicate_names

    def find_ambiguous_answers(self) -> AmbiguousPagesList:
        # The answers are ambiguous and were not already manually verified in a previous scan.
        return [
            (doc_id, page)
            for doc_id, doc_data in self.data.items()
            for page, pic_data in doc_data.pages.items()
            if pic_data.needs_review and Path(pic_data.pic_path) not in self.data_storage.verified
        ]


@dataclass
class NameReview:
    doc: DocumentId
    # actual_name: str = ""
    reviewed: bool = False


@dataclass
class AnswerReview:
    doc: DocumentId
    page: Page
    reviewed: bool = False


class Action(StrEnum):
    NEXT = ">"
    BACK = "<"
    DISCARD = "/"


class AllDataIssuesFixer:
    """Fix missing names and ambiguous answers issues."""

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = self.data_storage.data
        self.name_reviewer = NamesReviewer(data_storage)
        self.answers_reviewer = AnswersReviewer(data_storage)

    def run(self, check_result: DataCheckResult):
        """Resolve conflicts manually: unknown student ID, ambiguous answer..."""
        # Each operation is independent of the other ones,
        # and user should be able to navigate between them.

        names_to_review: list[NameReview] = [NameReview(doc) for doc in check_result.unnamed_docs]
        names_to_review += [
            NameReview(doc) for name, docs in check_result.duplicate_names.items() for doc in docs
        ]
        answers_to_review: list[AnswerReview] = [
            AnswerReview(doc, page) for doc, page in check_result.ambiguous_answers
        ]

        position = 0
        while position < len(names_to_review) + len(answers_to_review):
            if position < len(names_to_review):
                to_review = names_to_review[position]
                action = self.name_reviewer.review_name(to_review)
                # Verify that the new name has not induced a new conflict.
                for doc_id in self.data:
                    if doc_id != to_review.doc and self.data[doc_id].name == self.data[to_review.doc].name:
                        names_to_review.append(NameReview(doc_id))
            else:
                action = self.answers_reviewer.review_answer(
                    answers_to_review[position - len(names_to_review)]
                )
            if action == Action.NEXT:
                position += 1
            elif action == Action.BACK:
                position = max(0, position - 1)

        # Apply changes definitively.
        for review in names_to_review:
            if self.data[review.doc].name == Action.DISCARD:
                doc_data = self.data.pop(review.doc)
                # For each page of the document, add corresponding picture path
                # to skipped paths list.
                # If `mcq scan` is run again, those pictures will be skipped.
                for pic_data in doc_data.pages.values():
                    self.data_storage.store_skipped_pic(Path(pic_data.pic_path))
                # Remove also all corresponding data files.
                self.data_storage.remove_doc_files(review.doc)


class NamesReviewer:
    ASK_FOR_NAME = "Name, ID or command: "
    PRESS_ENTER = "-- Press ENTER --"
    CORRECT_Y_N = "Is it correct? (Y/n)"

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = data_storage.data
        self.students_ids = self.data_storage.config.students_ids

    def review_name(self, to_review: NameReview) -> Action:
        doc_id = to_review.doc
        doc_data = self.data[doc_id]
        first_page = doc_data.pages.get(Page(1))
        if first_page is None:
            print_error(f"No first page found for document {doc_id}!")
            return Action.NEXT
        student_name, student_id, action = self.enter_name_and_id(doc_id)
        doc_data.name = student_name
        doc_data.student_id = student_id
        self.data_storage.more_infos[doc_id] = (student_name, student_id)
        to_review.reviewed = True
        return action

    def _suggest_id(self, incorrect_student_id: str) -> None:
        """Print a suggestion of student name, based on provided id.

        The name associated with the most closely matching id will be suggested.
        """

        def _proximity(id_):
            return levenshtein_distance(incorrect_student_id, id_)

        suggestion: StudentId = min(self.students_ids, key=_proximity)
        print(f"Suggestion: {suggestion} ({self.students_ids[suggestion]})")

    def _suggest_name(self, incorrect_name: str) -> None:
        """Print a suggestion of student name, based on provided name and existing ones."""
        incorrect_name = incorrect_name.lower()
        if self.students_ids:
            names = list(self.students_ids.values())
        elif self.data_storage.config.students_list:
            names = list(self.data_storage.config.students_list)
        else:
            return

        # Strategy 1: search if a name is almost the same.
        def _proximity(name_: StudentName):
            return levenshtein_distance(incorrect_name, name_)

        suggestion: StudentName = min(names, key=_proximity)

        if levenshtein_distance(incorrect_name, suggestion) <= 3:
            name = suggestion
        else:
            # Strategy 2: search if it is the start of a name.
            for name in names:
                if name.lower().startswith(incorrect_name):
                    break
            else:
                # Strategy 3: search if it is the start of any part of a name.
                for name in names:
                    if any(part.startswith(incorrect_name) for part in name.lower().split()):
                        break
                else:
                    # Strategy 4: search if it is a substring of any part of a name, or reciprocally.
                    for name in names:
                        if any(
                            (part in incorrect_name or incorrect_name in part)
                            for part in name.lower().split()
                        ):
                            break
                    else:
                        # Giving up...
                        name = StudentName("")
        if name:
            print(f"Suggestion: {name}")

    def enter_name_and_id(
        self, doc_id: DocumentId, default: str = ""
    ) -> tuple[StudentName, StudentId, Action]:
        """Ask user to read student name and id for current document."""
        array = self.data_storage.get_matrix(doc_id, Page(1))
        width = array.shape[1]
        viewer = ImageViewer(array=array[0 : int(3 / 4 * width), :])
        process = None
        name = StudentName("")
        student_id = StudentId("")
        action: Action | None = None

        print(f"[Document {doc_id}]")
        print(f"Please verify student name or ID (current name: {default!r}).")
        print("Please read the name on the picture which will be displayed now.")
        input(self.PRESS_ENTER)
        print(
            "Write below the actual student name or ID, or write one of the following commands:\n"
            f"   - Use {Action.DISCARD} to discard (remove) this document.\n"
            f"   - Use {Action.BACK} to go back to previous document.\n"
            f"   - Use {Action.NEXT} to go to next document, keeping current name."
        )
        while action is None:
            # ----------------------------------------
            # Display the top of the scanned document.
            # ----------------------------------------
            # Don't relaunch process if it is still alive.
            # (process.poll() is not None for dead processes.)
            if process is None or process.poll() is not None:
                process = viewer.display(wait=False)
            # ------------------------------
            # Ask the user to read the name.
            # ------------------------------
            user_input = input("Name, ID or command: ").strip()
            # -------------------------
            # Handle the user's answer.
            # -------------------------
            if user_input == Action.DISCARD:
                # Discard this document. It will be removed later.
                print_info(f"Discarding document {doc_id}.")
                return StudentName(user_input), StudentId("-1"), Action.NEXT
            elif user_input == Action.BACK:
                print("Navigating back to previous document.")
                return StudentName(default), StudentId(student_id), Action.BACK
            elif user_input == Action.NEXT:
                print("Navigating to next document.")
                return StudentName(default), StudentId(student_id), Action.NEXT
            elif self.students_ids:
                if user_input in self.students_ids:
                    # This is in fact not a name, but a known student id,
                    # so convert it to a name.
                    name, student_id = self.students_ids[StudentId(user_input)], StudentId(user_input)
                    action = Action.NEXT
                elif user_input in self.students_ids.values():
                    for _student_id, _name in self.students_ids.items():
                        if _name == user_input:
                            break
                    # noinspection PyUnboundLocalVariable
                    name = StudentName(_name)
                    # noinspection PyUnboundLocalVariable
                    student_id = StudentId(_student_id)
                    action = Action.NEXT
                elif any((digit in user_input) for digit in string.digits):
                    # If `name` contains a digit, this is not a student name,
                    # but probably a misspelled student id!
                    print("Unknown ID.")
                    # So, suggest the more closely related existing id.
                    self._suggest_id(user_input)
                else:
                    print("Unknown name.")
                    self._suggest_name(user_input)
            elif self.data_storage.config.students_list:
                if user_input in self.data_storage.config.students_list:
                    action = Action.NEXT
                else:
                    self._suggest_name(user_input)
            elif user_input:
                name = StudentName(user_input)

            if action is not None:
                print(f"Name: {name}")
                while (is_correct := input(self.CORRECT_Y_N).lower()) not in (
                    "y",
                    "yes",
                    "",
                    "n",
                    "no",
                ):
                    pass
                if is_correct in ("n", "no"):
                    action = None
        assert process is not None
        process.terminate()
        # Keep track of manually entered information (will be useful if the scan has to be run again later!)
        self.data_storage.store_additional_info(doc_id=doc_id, name=name, student_id=student_id)
        return name, student_id, action


class AnswersReviewer:
    """Fix missing names and ambiguous answers issues."""

    def __init__(self, data_storage: DataHandler):
        self.data_storage = data_storage
        self.data = self.data_storage.data

    def review_answer(self, to_review: AnswerReview) -> Action:
        if self.data[to_review.doc].name == "/":
            # Skip this document.
            return Action.NEXT
        else:
            pic_data = self.data[to_review.doc].pages[to_review.page]
            action = self.edit_answers(to_review.doc, to_review.page)
            self.data_storage.store_verified_pic(Path(pic_data.pic_path))
            to_review.reviewed = True
            return action

    def edit_answers(self, doc_id: DocumentId, page: Page) -> Action:
        """Call interactive editor to change answers.

        `self.data` will be modified accordingly.
        """
        config = self.data_storage.config
        pic_data = self.data[doc_id].pages[page]
        answered = pic_data.answered
        revision_status = pic_data.revision_status
        print_warning(f"Ambiguous answers for student {self.data[doc_id].name}.")
        print(
            f"Just press ENTER to verify answers.\n"
            f"Additional commands:\n"
            f"    - Use {Action.BACK} to go back to previous document."
            f"    - Use {Action.NEXT} to go directly to next document."
        )
        match input():
            case Action.BACK:
                return Action.BACK
            case Action.NEXT:
                return Action.NEXT

        while True:
            process = self.display_page_with_detected_answers(doc_id, page)
            if input("Is this correct ? [(y)es/(N)o]").lower() in ("y", "yes"):
                break
            while (q_str := input("Write a question number, or 0 to escape:")) != "0":
                try:
                    q0 = ApparentQuestionNumber(int(q_str))
                    q, _ = apparent2real(q0, None, config, doc_id)
                    if q not in answered:
                        # print(f"{answered=} {page=} {doc_id=}\n")
                        raise IndexError(rf"Invalid question number: {q0}")

                    checked = answered[q]
                    a_str = input(
                        "Add or remove answers "
                        "(Example: +2 -1 -4 to add answer 2, and remove answers 1 et 4):"
                    )
                    for val in a_str.split():
                        op, a0 = val[0], ApparentAnswerNumber(int(val[1:]))
                        q, a = apparent2real(q0, a0, config, doc_id)
                        if op == "+":
                            if a in checked:
                                print(f"Warning: {a0} already in answers.")
                            else:
                                checked.add(a)
                                revision_status[(q, a)] = RevisionStatus.MARKED_AS_CHECKED
                        elif op == "-":
                            if a in checked:
                                checked.remove(a)
                                revision_status[(q, a)] = RevisionStatus.MARKED_AS_UNCHECKED
                            else:
                                print(f"Warning: {a0} not in answers.")
                        else:
                            print(f"Invalid operation: {val!r}")
                except ValueError:
                    print("Invalid value.")
                    continue
                except (KeyError, IndexError):
                    # import traceback
                    # import sys
                    # traceback.print_exc(file=sys.stdout)
                    print("Invalid number.")
                finally:
                    process.terminate()
                    process = self.display_page_with_detected_answers(doc_id, page)
        process.terminate()
        return Action.NEXT

    def display_page_with_detected_answers(self, doc_id: DocumentId, page: Page) -> subprocess.Popen:
        """Display the page with its checkboxes colored following their detection status."""
        array = self.data_storage.get_matrix(doc_id, page)
        pic_data = self.data[doc_id].pages[page]
        return self.display_picture_with_detected_answers(array, pic_data)

    @staticmethod
    def display_picture_with_detected_answers(array: ndarray, pic_data: PicData) -> subprocess.Popen:
        """Display the picture of the MCQ with its checkboxes colored following their detection status."""
        viewer = ImageViewer(array=array)
        colors: dict[DetectionStatus | RevisionStatus, RGB] = {
            DetectionStatus.CHECKED: Color.blue,
            DetectionStatus.PROBABLY_CHECKED: Color.green,
            DetectionStatus.PROBABLY_UNCHECKED: Color.magenta,
            DetectionStatus.UNCHECKED: Color.pink,
            RevisionStatus.MARKED_AS_CHECKED: Color.cyan,
            RevisionStatus.MARKED_AS_UNCHECKED: Color.red,
        }
        thicknesses: dict[DetectionStatus | RevisionStatus, int] = {
            DetectionStatus.CHECKED: 2,
            DetectionStatus.PROBABLY_CHECKED: 5,
            DetectionStatus.PROBABLY_UNCHECKED: 5,
            DetectionStatus.UNCHECKED: 2,
            RevisionStatus.MARKED_AS_CHECKED: 5,
            RevisionStatus.MARKED_AS_UNCHECKED: 5,
        }
        for (q, a), (i, j) in pic_data.positions.items():
            status = pic_data.revision_status.get((q, a), pic_data.detection_status[(q, a)])
            viewer.add_rectangle(
                (i, j), pic_data.cell_size, color=colors[status], thickness=thicknesses[status]
            )
        return viewer.display(wait=False)
