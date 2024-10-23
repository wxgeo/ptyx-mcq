import string
import subprocess
from pathlib import Path

from numpy import ndarray

from ptyx.shell import print_warning, print_info

from ptyx_mcq.scan.data_gestion.conflict_handling.data_check.base import (
    Action,
    AbstractNamesReviewer,
    AbstractAnswersReviewer,
)
from ptyx_mcq.tools.misc import copy_docstring
from ptyx_mcq.tools.rgb import Color, RGB
from ptyx_mcq.scan.data_gestion.document_data import (
    Page,
    DetectionStatus,
    RevisionStatus,
    PicData,
)
from ptyx_mcq.scan.picture_analyze.image_viewer import ImageViewer
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    ApparentQuestionNumber,
    apparent2real,
    ApparentAnswerNumber,
    StudentName,
    StudentId,
)


# --------------------------
#       Review names
# ==========================


class ClNamesReviewer(AbstractNamesReviewer):
    """Command line names' reviewer.

    Fix missing names issues."""

    ASK_FOR_NAME = "Name, ID or command: "
    PRESS_ENTER = "-- Press ENTER --"
    CORRECT_Y_N = "Is it correct? (Y/n)"

    @copy_docstring(AbstractNamesReviewer._suggest_name)
    def _suggest_name(self, incorrect_name: str) -> StudentName:
        name = super()._suggest_name(incorrect_name=incorrect_name)
        if name:
            print(f"Suggestion: {name} (write `ok` to validate it).")
        return name

    @copy_docstring(AbstractNamesReviewer.enter_name_and_id)
    def enter_name_and_id(
        self, doc_id: DocumentId, default: StudentName
    ) -> tuple[StudentName, StudentId, Action, bool]:
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
            f"   - Use {Action.NEXT} ou `ok` to go to next document, keeping current name."
        )
        suggestion = default
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
            if user_input.lower() == "ok":
                user_input = suggestion
            suggestion = StudentName("")

            if user_input == Action.DISCARD:
                # Discard this document. It will be removed later.
                print_info(f"Discarding document {doc_id}.")
                return StudentName(user_input), StudentId("-1"), Action.NEXT, True
            elif user_input == Action.BACK:
                print("Navigating back to previous document.")
                return StudentName(default), StudentId(student_id), Action.BACK, False
            elif user_input == Action.NEXT:
                print("Navigating to next document.")
                return StudentName(default), StudentId(student_id), Action.NEXT, True
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
                    suggestion = self.students_ids[self._suggest_id(user_input)]
                else:
                    print("Unknown name.")
                    suggestion = self._suggest_name(user_input)
            elif self.data_storage.config.students_list:
                if user_input in self.data_storage.config.students_list:
                    action = Action.NEXT
                else:
                    suggestion = self._suggest_name(user_input)
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
        return name, student_id, action, True


# --------------------------
#      Review answers
# ==========================


class ClAnswersReviewer(AbstractAnswersReviewer):
    """Command line answers' reviewer.

    Fix ambiguous answers issues."""

    ENTER_COMMAND = (
        f"Write {Action.BACK}, {Action.NEXT}, or just press ENTER to review current document's answers:"
    )
    IS_CORRECT = "Is this correct ? [(y)es/(N)o]"
    SELECT_QUESTION = "Write a question number, or 0 to escape:"
    EDIT_ANSWERS = "Add or remove answers (Example: +2 -1 -4 to add answer 2, and remove answers 1 et 4):"

    @copy_docstring(AbstractAnswersReviewer.review_answer)
    def review_answer(self, doc_id: DocumentId, page: Page) -> tuple[Action, bool]:
        if self.data[doc_id].name == Action.DISCARD.value:
            # Skip this document.
            return Action.NEXT, False
        else:
            pic_data = self.data[doc_id].pages[page]
            action, reviewed = self.edit_answers(doc_id, page)
            self.data_storage.store_verified_pic(Path(pic_data.pic_path))
            return action, reviewed

    def edit_answers(self, doc_id: DocumentId, page: Page) -> tuple[Action, bool]:
        """Call interactive editor to change answers.

        MCQ parser internal state `self.data` will be modified accordingly.

        Return the action to do (go to next document, go back to previous one,
        or skip document), and a boolean which indicates if the document as been
        effectively reviewed.
        """
        config = self.data_storage.config
        pic_data = self.data[doc_id].pages[page]
        answered = pic_data.answered
        revision_status = pic_data.revision_status
        print_warning(f"Ambiguous answers for student {self.data[doc_id].name} (doc {doc_id}, page: {page}).")
        print(
            f"Tip: write {Action.BACK} to go back to previous document, or {Action.NEXT} to jump directly to next document."
        )
        match input(self.ENTER_COMMAND):
            case Action.BACK:
                return Action.BACK, False
            case Action.NEXT:
                return Action.NEXT, False

        while True:
            process = self.display_page_with_detected_answers(doc_id, page)
            if input(self.IS_CORRECT).lower() in ("y", "yes"):
                break
            while (q_str := input(self.SELECT_QUESTION)) != "0":
                try:
                    q0 = ApparentQuestionNumber(int(q_str))
                    q, _ = apparent2real(q0, None, config, doc_id)
                    if q not in answered:
                        # print(f"{answered=} {page=} {doc_id=}\n")
                        raise IndexError(rf"Invalid question number: {q0}")

                    checked = answered[q]
                    a_str = input(self.EDIT_ANSWERS)
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
        return Action.NEXT, True

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
