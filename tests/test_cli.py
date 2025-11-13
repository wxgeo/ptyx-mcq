"""
Test mcq command line interface.

Test new, make and scan subcommands.
"""

import csv
import shutil
from functools import partial
from os import listdir
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
import pymupdf  # type: ignore


from ptyx.pretty_print import print_info

from ptyx_mcq.cli import main as main_, Handlers, get_handler
from ptyx_mcq.dev_cli import DevHandlers
from ptyx_mcq.parameters import CELL_SIZE_IN_CM, DEFAULT_TEMPLATE_NAME
from ptyx_mcq.tools.colors import Color, RGB
from ptyx_mcq.tools.math import round
from ptyx_mcq.tools.config_parser import (
    Configuration,
    is_answer_correct,
    StudentId,
    StudentName,
)
from ptyx_mcq.tools.pdf import similar_pdfs

from tests import ASSETS_DIR

main = partial(main_, _restart_process_if_needed=False)

DPI = 200
PX_PER_CM = DPI / 2.54
PX_PER_MM = PX_PER_CM / 10
CELL_SIZE_IN_PX = CELL_SIZE_IN_CM * PX_PER_CM

STUDENTS = {
    StudentId("12345678"): StudentName("Jean Dupond"),
    StudentId("34567890"): StudentName("Martin De La Tour"),
}

MAX_ID_LEN = max(len(student_id) for student_id in STUDENTS)


def convert_from_path(pdf_path: Path, dpi: int) -> list[Image.Image]:
    # noinspection PyTypeChecker
    return [
        Image.frombytes(
            mode="RGB", size=((pix := page.get_pixmap(dpi=dpi)).width, pix.height), data=pix.samples
        )
        for page in pymupdf.Document(pdf_path).pages()
    ]


def xy2ij(x: float, y: float) -> tuple[int, int]:
    """Convert (x, y) position (mm) to pixels (i,j).

    (x, y) is the position from the bottom left of the page in mm,
    as given by LaTeX.
    (i, j) is the position in pixels, where i is the line and j the
    column, starting from the top left of the image.
    """
    # Top left square is printed at 1 cm from the left and the top of the sheet.
    i = (297 - y) * PX_PER_MM  # 29.7 cm - 1 cm = 28.7 cm (A4 sheet format = 21 cm x 29.7 cm)
    j = x * PX_PER_MM
    return round(i), round(j)


def _fill_checkbox(draw: ImageDraw.ImageDraw, pos: tuple, size: float, color: RGB = Color.red) -> None:
    i, j = xy2ij(*pos)
    # Draw a blue square around the box (for debugging purpose).
    draw.rectangle((j, i, j + size, i + size), fill=color)


def write_student_id(draw: ImageDraw.ImageDraw, student_id: str, config: Configuration) -> None:
    assert config.id_table_pos is not None
    x0, y0 = config.id_table_pos
    for i, digit in enumerate(student_id.zfill(MAX_ID_LEN)):
        x_shift = 10 + 10 * int(digit)
        y_shift = 10 * i
        _fill_checkbox(
            draw,
            (x0 + x_shift * CELL_SIZE_IN_CM, y0 - y_shift * CELL_SIZE_IN_CM),
            CELL_SIZE_IN_PX,
            color=Color.blue,
        )


def simulate_answer(pics: list, config: Configuration):
    """Amend answer sheet with scores and correct answers.

    `data` is the dict generated when the answer sheet is scanned.
    `ID` is the ID of answer sheet.
    """
    # Convert cell size from cm to pixels
    students_ids = list(STUDENTS)
    boxes = config.boxes
    for i, (doc_id, data) in enumerate(boxes.items()):
        if i >= len(students_ids):
            print(f"Warning: {len(boxes)} documents but only {len(students_ids)} students.")
            break
        for page, page_data in data.items():
            # Each document has 2 pages, but page 2 should be empty as there are only 2 questions.
            # So we must skip the empty page.
            pic = pics[2 * i]
            # Drawing context
            draw = ImageDraw.Draw(pic)
            write_student_id(draw, students_ids[i], config)
            for (q, a), pos in page_data.items():
                if is_answer_correct(q, a, config, doc_id):
                    _fill_checkbox(draw, pos, CELL_SIZE_IN_PX)
    return pics[: 2 * len(students_ids)]


def write_students_id_to_csv(path: Path, students: dict[StudentId, StudentName]) -> Path:
    with open(csv_path := path / "students.csv", "w", newline="") as csvfile:
        csv.writer(csvfile).writerows(students.items())
    return csv_path


def read_students_scores(path: Path) -> dict[tuple[StudentId, StudentName], str]:
    students: dict[tuple[StudentId, StudentName], str] = {}
    # TODO : store scores outside of .scan folder, in a RESULTS folder !
    with open(score_path := path / "out/scores.csv") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            match row:
                case ["ID", "Name", _, "Score/20", "Score/100"]:
                    pass  # Header row
                case [id_, name, score, _, _]:
                    students[StudentId(id_), StudentName(name)] = score
                case _:
                    raise ValueError(f"Invalid format in '{score_path}': {row!r}.")
    return students


@pytest.mark.slow
def test_many_docs(tmp_path):
    number_of_documents = 10
    path = tmp_path / "mcq"

    # Test mcq new
    main(["new", str(path), "--template", DEFAULT_TEMPLATE_NAME])
    assert "new.ptyx" in listdir(path)
    # Test mcq make
    main(["make", str(path), "-n", str(number_of_documents)])
    assert "new.pdf" in listdir(path)
    # No correction generated anymore by default.
    assert "new-corr.pdf" not in listdir(path)


def test_handlers() -> None:
    """Test that all command line handlers do still exist."""
    handler: Handlers | DevHandlers
    for handler in Handlers:
        assert callable(get_handler(handler))
    for handler in DevHandlers:
        assert callable(get_handler(handler))


def test_cli(tmp_path: Path) -> None:
    number_of_documents = 2
    # Make a temporary directory
    print("----------------")
    print_info(f"Working in: '{tmp_path}'")
    print("----------------")
    write_students_id_to_csv(tmp_path, STUDENTS)

    path = tmp_path / "mcq"

    # ----------------
    # Test `mcq new`
    # ----------------

    main(["new", str(path), "--template", DEFAULT_TEMPLATE_NAME])

    assert "new.ptyx" in listdir(path)

    with open(path / "new.ptyx") as ptyxfile:
        ptyxfile_content = ptyxfile.read()
    with open(path / "new.ptyx", "w") as ptyxfile:
        assert "\nid format" in ptyxfile_content
        ptyxfile.write(ptyxfile_content.replace("\nid format", "\nids=../students.csv\nid format"))

    # ----------------
    # Test `mcq make`
    # ----------------
    main(["make", str(path), "-n", str(number_of_documents)])

    assert "new.pdf" in listdir(path)
    # No correction generated anymore by default.
    assert "new-corr.pdf" not in listdir(path)

    config = Configuration.load(path / "new.ptyx.mcq.config.json")
    for student_id in STUDENTS:
        assert student_id in config.students_ids, (repr(student_id), repr(config.students_ids))
        assert config.students_ids[student_id] == STUDENTS[student_id]

    # -----------------------------------
    # Test `mcq new PATH -i INCLUDE_PATH`
    # -----------------------------------
    path2 = tmp_path / "mcq-2"
    main(["new", str(path2), "-i", str(path / "questions"), "-t", DEFAULT_TEMPLATE_NAME])
    assert "new.ptyx" in listdir(path)
    assert not (path2 / "questions").exists()

    # --------------------------------------
    # Test `mcq make PATH --with-correction`
    # --------------------------------------

    main(["make", str(path2), "--with-correction"])
    with open(path2 / ".compile/new/new-corr.tex", encoding="utf8") as f:
        assert f.read().count(r"\checkBox") > 10  # TODO: give a precise number.
    assert "new-corr.pdf" in listdir(path2)

    # ----------------
    # Test `mcq scan`
    # ----------------
    images = convert_from_path(path / "new.pdf", dpi=DPI)
    images = simulate_answer(images, config)
    assert len(images) / 2 == min(number_of_documents, len(STUDENTS))
    scan_path = path / "scan"
    scan_path.mkdir(exist_ok=True)
    images[0].save(scan_path / "simulate-scan.pdf", save_all=True, append_images=images[1:])
    main(["scan", str(path)])

    # TODO : store scores outside of .scan folder, in a RESULTS folder !
    students_scores: dict[tuple[StudentId, StudentName], str] = read_students_scores(path)
    for score in students_scores.values():
        assert abs(float(score) - 4.0) < 1e-10, repr(score)  # Maximal score
    assert set(students_scores) == set(STUDENTS.items()), repr(students_scores)

    assert (path / "new.scores.xlsx").exists()
    assert (output_pdf_path := path / "out/pdf").exists()
    for doc_id, (student_id, student_name) in enumerate(STUDENTS.items(), start=1):
        assert (output_pdf_path / f"{student_name}-{student_id}-{doc_id}.pdf").is_file()

    # ------------------------
    # Test `mcq update`
    # ------------------------
    STUDENTS[StudentId("12345678")] = StudentName(new_student_name := "Julien Durand")
    csv_path = write_students_id_to_csv(tmp_path, STUDENTS)
    with open(csv_path) as f:
        assert new_student_name in f.read()
    # Invert correct and incorrect answers for testing update.
    with open(path / "questions/question1.ex", encoding="utf8") as f:
        file_content = f.read()
    with open(path / "questions/question1.ex", "w", encoding="utf8") as f:
        f.write(file_content.replace("+", "§").replace("-", "+").replace("§", "-"))
    with open(path / "new.ptyx", encoding="utf8") as f:
        content = f.read()
    with open(path / "new.ptyx", "w", encoding="utf8") as f:
        f.write(content.replace("# default score =", "default score ="))

    main(["update", "config-file", str(path)])
    config = Configuration.load(path / "new.ptyx.mcq.config.json")
    assert new_student_name in config.students_ids.values(), repr(path / "new.ptyx.mcq.config.json")
    main(["scan", str(path)])
    old_students_scores = students_scores.copy()
    students_scores = read_students_scores(path)
    # Names are not updated yet, since they are stored in `.scandata` cache files.
    # Updating names requires clearing cache
    for student_id, student_name in students_scores:
        if student_name != new_student_name:
            assert float(students_scores[student_id, student_name]) < float(
                old_students_scores[student_id, student_name]
            )
        else:
            # TODO: add configuration option for default value.
            assert students_scores[student_id, student_name] == "ABI"
    # Names are  Updating names requires clearing cache,
    # through `--reset` option.
    main(["scan", "--reset", str(path)])
    students_scores = read_students_scores(path)
    assert set(students_scores) == set(STUDENTS.items()), repr(students_scores)

    # ---------------------
    # Test `mcq doc`
    # ---------------------
    main(["doc", "strategies"])
    main(["doc", "config"])

    # ----------------
    # Test `mcq clear`
    # ----------------
    paths_to_be_removed = [
        "out/.cache",
        ".compile",
        "new.pdf",
        "new.ptyx.mcq.config.json",
    ]
    paths_to_be_kept = [
        "new.ptyx",
        "scan/simulate-scan.pdf",
    ]
    for path_end in paths_to_be_removed + paths_to_be_kept:
        assert (pth := path / path_end).exists(), pth
    main(["clear", str(path)])
    for path_end in paths_to_be_removed:
        assert not (pth := path / path_end).exists(), pth
    for path_end in paths_to_be_kept:
        assert (pth := path / path_end).exists(), pth

    # --------------
    # Test `mcq fix`
    # --------------

    # todo:
    #  main(["fix", "doc"])


def test_make_for_review(tmp_path):
    path = tmp_path / "new dir with non-ascii characters like éhô"
    targets = ASSETS_DIR / "cli-tests/pdf-targets"
    main(["new", str(path), "--template", DEFAULT_TEMPLATE_NAME])
    assert not (path / "new.review.pdf").is_file()
    main(["make", str(path), "--for-review"])
    assert (path / "new.review.pdf").is_file()
    assert not (path / "new.pdf").is_file()
    assert not similar_pdfs(path / "new.review.pdf", targets / "vanilla-version.pdf")
    assert similar_pdfs(path / "new.review.pdf", targets / "for-review-version.pdf")


def test_make_force(tmp_path):
    path = tmp_path / "new dir"
    targets = ASSETS_DIR / "cli-tests/pdf-targets"
    main(["new", str(path), "--template", DEFAULT_TEMPLATE_NAME])
    main(["make", str(path)])
    assert similar_pdfs(path / "new.pdf", targets / "vanilla-version.pdf")
    assert not similar_pdfs(path / "new.pdf", targets / "for-review-version.pdf")
    assert not similar_pdfs(path / "new.pdf", targets / "two-docs-version.pdf")
    # Force rebuild
    main(["make", str(path), "-n", "2", "-f"])
    assert similar_pdfs(path / "new.pdf", targets / "two-docs-version.pdf")


def test_make_without_force(tmp_path, custom_input):
    path = tmp_path / "new dir"
    targets = ASSETS_DIR / "cli-tests/pdf-targets"
    main(["new", str(path), "--template", DEFAULT_TEMPLATE_NAME])
    main(["make", str(path)])
    assert similar_pdfs(path / "new.pdf", targets / "vanilla-version.pdf")

    custom_input.set_scenario([("A previous compiled version exist, overwrite it (y∕N) ?", "")])
    with pytest.raises(SystemExit):
        main(["make", str(path), "-n", "2"])
    assert custom_input.is_empty()
    assert similar_pdfs(path / "new.pdf", targets / "vanilla-version.pdf")

    custom_input.set_scenario([("A previous compiled version exist, overwrite it (y∕N) ?", "y")])
    main(["make", str(path), "-n", "2"])
    assert similar_pdfs(path / "new.pdf", targets / "two-docs-version.pdf")


def csv2list(path: Path) -> list[str]:
    return path.read_text(encoding="utf8").split("\n")


def test_previous_scan_data_loading(tmp_path):
    """Test that previously entered data is correctly handled.

    In particular, data manually entered by user during previous scans
    is stored in `out/.fix`, and should take precedence over all other information.
    """
    copy = tmp_path / "caching_test"
    origin = ASSETS_DIR / "cli-tests/caching_test"
    shutil.copytree(origin, copy)
    assert (origin / "unpatched_scores.csv").is_file()
    main(["scan", str(copy)])
    assert sorted(csv2list(copy / "out/scores.csv")) == sorted(csv2list(origin / "patched_scores.csv"))
    shutil.rmtree(copy / "out/.fix")
    main(["scan", str(copy), "--reset"])
    assert sorted(csv2list(copy / "out/scores.csv")) == sorted(csv2list(origin / "unpatched_scores.csv"))


# if __name__ == "__main__":
#     test_cli()
