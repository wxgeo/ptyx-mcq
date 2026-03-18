import datetime
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

from ptyx.pretty_print import print_success

from ptyx_mcq.scan.data.analyze.checkboxes import export_checkboxes as export_checkboxes_
from ptyx_mcq.scan.scan_doc import MCQPictureParser
from ptyx_mcq.scan.data import ScanData


def calibration(
    picture: Path,
    path: Path | str = ".",
) -> None:
    """Implement `mcq-dev calibration` command."""
    MCQPictureParser(path).display_picture_calibration(picture)
    print_success(f"Picture '{picture}' displayed.")


def review(
    picture: Path,
    path: Path | str = ".",
) -> None:
    """Implement `mcq review` command."""
    MCQPictureParser(path).scan_single_picture(picture)
    print_success(f"Picture '{picture}' scanned.")


def export_checkboxes(path: Path | str = ".", debug=False):
    path = Path(path).expanduser().resolve()
    now = datetime.datetime.now()
    date = f"{now.year}-{now.month}-{now.day}-{now.hour}-{now.minute}-{now.second}"
    tar_name = f"checkboxes-{date}.tar"
    tmp_dir: str | Path
    with TemporaryDirectory() as tmp_dir:
        if debug:
            tmp_dir = Path("/tmp/mcq-dev-export_checkboxes")
            tmp_dir.mkdir(exist_ok=True)
        scan_data = ScanData(path)
        print("\nLoad data...")
        scan_data.run()
        print("\nExporting pictures...")
        export_checkboxes_(scan_data, export_all=True, path=Path(tmp_dir), compact=True)
        print("\nCreating archive...")
        with tarfile.open(path / tar_name, "w") as tar:
            tar.add(tmp_dir, arcname=date)
        # compact_checkboxes(Path(tmp_dir), path / (date + ".webp"))
    print_success(f"File {tar_name} created.")


# def compact_checkboxes(directory: Path, final_file: Path):
#     from ptyx_mcq.scan.data_handler import save_webp
#
#     names: list[str] = []
#     matrices = []
#     print(f"{directory=}")
#     for webp in directory.glob("1/1-*.webp"):
#         names.append(webp.parent.stem + "-" + webp.stem)
#         matrices.append(load_webp(webp))
#     save_webp(concatenate(matrices), final_file)
