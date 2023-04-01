import string
import subprocess
from pathlib import Path

from ptyx_mcq.scan.color import Color, RGB
from ptyx_mcq.scan.data_manager import DataStorage
from ptyx_mcq.scan.document_data import Page, DetectionStatus, RevisionStatus
from ptyx_mcq.scan.visual_debugging import ArrayViewer
from ptyx_mcq.tools.config_parser import (
    DocumentId,
    ApparentQuestionNumber,
    apparent2real,
    ApparentAnswerNumber,
    StudentName,
    StudentId,
)
from ptyx_mcq.tools.io_tools import print_framed_msg, print_warning


class ConflictSolver:
    def __init__(self, data_storage: DataStorage):
        self.data_storage = data_storage
        self.data = data_storage.data

    def resolve_conflicts(self):
        """Resolve conflicts manually: unknown student ID, ambiguous answer..."""
        print("Searching for missing names...")
        self.review_missing_names()
        print("Searching for duplicate names...")
        self.review_duplicate_names()
        print("Searching for ambiguous answers...")
        self.review_answers()

    def review_missing_names(self):
        # First, complete missing information with previous scan data, if any.
        for doc_id, (student_name, student_id) in self.data_storage.more_infos.items():
            self.data[doc_id]["name"] = student_name
            self.data[doc_id]["student_ID"] = student_id
        # Search for any missing information remaining.
        for doc_id, doc_data in self.data.items():
            if doc_data["name"] == "":
                print_warning(f"No student name for document {doc_id}.")
                student_name, student_id = self.enter_name_and_id(doc_id)
                doc_data["name"] = student_name
                doc_data["student_ID"] = student_id
                self.data_storage.more_infos[doc_id] = (student_name, student_id)

    def review_duplicate_names(self) -> None:
        name_to_doc_id: dict[StudentName, DocumentId] = {}
        for doc_id, doc_data in self.data.items():
            name = doc_data["name"]
            if name in name_to_doc_id:
                matching_doc_id = name_to_doc_id[name]
                matching_doc_data = self.data[matching_doc_id]
                print_warning(f"Same student name on documents {doc_id} and {matching_doc_id}: {name!r}.")
                self.resolve_duplicate_name_conflict(name, doc_id, name_to_doc_id)
                self.data_storage.more_infos[doc_id] = doc_data["name"], doc_data["student_ID"]
                self.data_storage.more_infos[matching_doc_id] = (
                    matching_doc_data["name"],
                    matching_doc_data["student_ID"],
                )

    def resolve_duplicate_name_conflict(
        self, name: StudentName, doc_id: DocumentId, name_to_doc_id: dict[StudentName, DocumentId]
    ) -> None:
        while name in name_to_doc_id:
            print(f"Test #{name_to_doc_id[name]}: {name}")
            print(f"Test #{doc_id}: {name}")
            print_framed_msg(
                f"Error : 2 tests for same student ({name}) !\n"
                "Please modify at least one name (enter nothing to keep a name)."
            )
            # Remove twin name from name2doc_id, and get the corresponding previous test ID.
            doc_id0 = name_to_doc_id.pop(name)
            # Ask for a new name.
            name0, student_id0 = self.enter_name_and_id(doc_id0, default=name)
            # Update all infos.
            name_to_doc_id[name0] = doc_id0
            self.data[doc_id0]["name"] = name0
            self.data[doc_id0]["student_ID"] = student_id0
            # Ask for a new name for new test too.
            name = self.enter_name_and_id(doc_id)[0]

        assert name, "Name should not be empty at this stage !"
        name_to_doc_id[name] = doc_id
        self.data[doc_id]["name"] = name

    def enter_name_and_id(self, doc_id: DocumentId, default: str = "") -> tuple[StudentName, StudentId]:
        array = self.data_storage.get_matrix(doc_id, Page(1))
        width = array.shape[1]
        viewer = ArrayViewer(array[0 : int(3 / 4 * width), :])
        student_ids = self.data_storage.config.students_ids
        student_ID = ""
        print("Name can not be read automatically.")
        print("Please read the name on the picture which will be displayed now.")
        input("-- Press enter --")
        #    subprocess.run(["display", "-resize", "1920x1080", pic_path])
        # TODO: use first letters of students name to find student.
        # (ask again if not found, or if several names match first letters)
        process = None
        name = ""
        while name == "":
            # Don't relaunch process if it is still alive.
            # (process.poll() is not None for dead processes.)
            if process is None or process.poll() is not None:
                process = viewer.display(wait=False)
            name = input("Student name or ID:").strip()
            if not name:
                name = default
            elif student_ids:
                if name in student_ids:
                    name, student_ID = student_ids[StudentId(name)], name
                elif any((digit in name) for digit in string.digits):
                    # This is not a student name !
                    print("Unknown ID.")
                    name = ""
            if name:
                print("Name: %s" % name)
                if input("Is it correct ? (Y/n)").lower() not in ("y", "yes", ""):
                    name = ""
        assert process is not None
        process.terminate()
        # Keep track of manually entered information (will be useful if the scan has to be run again later !)
        self.data_storage.store_additional_info(doc_id=doc_id, name=name, student_ID=student_ID)
        return StudentName(name), StudentId(student_ID)

    def review_answers(self):
        for doc_id, doc_data in self.data.items():
            for page, pic_data in doc_data["pages"].items():
                if pic_data.needs_review and Path(pic_data.pic_path) not in self.data_storage.verified:
                    # The answers are ambiguous and were not already manually verified in a previous scan.
                    print_warning(f"Ambiguous answers for student {doc_data['name']}.")
                    self.edit_answers(doc_id, page)
                    self.data_storage.store_verified_pic(Path(pic_data.pic_path))

    def display_picture_with_detected_answers(self, doc_id: DocumentId, page: Page) -> subprocess.Popen:
        """Display the page with its checkboxes colored following their detection status."""
        array = self.data_storage.get_matrix(doc_id, page)
        viewer = ArrayViewer(array)
        pic_data = self.data[doc_id]["pages"][page]
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
            viewer.add_square((i, j), pic_data.cell_size, color=colors[status], thickness=thicknesses[status])
        return viewer.display(wait=False)

    def edit_answers(self, doc_id: DocumentId, page: Page) -> None:
        """Interactive editor to change answers."""
        config = self.data_storage.config
        pic_data = self.data[doc_id]["pages"][page]
        # m = self.data_storage.get_matrix(doc_id, page)
        # cell_size = pic_data.cell_size
        answered = pic_data.answered
        revision_status = pic_data.revision_status
        print("Please verify answers detection:")
        input("-- Press ENTER --")

        while True:
            process = self.display_picture_with_detected_answers(doc_id, page)
            if input("Is this correct ? [(y)es/(N)o]").lower() in ("y", "yes"):
                break
            while (q_str := input("Write a question number, or 0 to escape:")) != "0":
                try:
                    q0 = ApparentQuestionNumber(int(q_str))
                    q, _ = apparent2real(q0, None, config, doc_id)
                    if q not in answered:
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
                    print("Invalid number.")
                finally:
                    process.terminate()
                    process = self.display_picture_with_detected_answers(doc_id, page)
        process.terminate()

    def display_first_page_head(self, doc_id: DocumentId) -> subprocess.CompletedProcess | subprocess.Popen:
        """Display the head of the first page, to be able to read student name manually."""
        array = self.data_storage.get_matrix(doc_id, Page(1))
        width = array.shape[1]
        viewer = ArrayViewer(array[0 : int(3 / 4 * width), :])
        return viewer.display(wait=False)
