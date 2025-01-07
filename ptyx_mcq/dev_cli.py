#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
"""
ptyx MCQ Specific command line interface for development

@author: Nicolas Pourcelot
"""
import datetime
import tarfile
from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from numpy import array, ndarray  # , concatenate
import argcomplete
from argcomplete import FilesCompleter

from ptyx.shell import print_success

from ptyx_mcq.scan.data.analyze.checkboxes import export_checkboxes as export_checkboxes_


# noinspection PyTypeHints
def main(args: list[str] | None = None) -> None:
    """Main entry point, called whenever `mcq` command is executed."""
    parser = ArgumentParser(description="Development tools for pTyX-MCQ.")
    subparsers = parser.add_subparsers()
    add_parser = subparsers.add_parser

    # ------------------------------------------
    #     $ mcq-dev  export-checkboxes
    # ------------------------------------------
    # create the parser for the "export-checkboxes" command
    export_checkboxes_parser = add_parser(
        "export-checkboxes", help="Export all checkboxes. This is used to create tests."
    )
    export_checkboxes_parser.add_argument(  # type: ignore[attr-defined]
        "path", nargs="?", metavar="PATH", type=Path, default="."
    ).completer = FilesCompleter("ptyx")

    export_checkboxes_parser.set_defaults(func=export_checkboxes)

    # ------------------------------------------
    #     $ mcq-dev scan-picture
    # ------------------------------------------
    # create the parser for the "make" command
    review_picture_parser = add_parser("review", help="Review one picture for debugging.")
    review_picture_parser.add_argument(
        "picture", metavar="PIC", type=Path
    )  # .completer = FilesCompleter("ptyx")
    review_picture_parser.add_argument(  # type: ignore[attr-defined]
        "path", nargs="?", metavar="PATH", type=Path, default="."
    ).completer = FilesCompleter("ptyx")
    review_picture_parser.set_defaults(func=review)

    # ------------------------------------------
    #     $ mcq-dev calibration
    # ------------------------------------------
    # create the parser for the "make" command
    calibration_picture_parser = add_parser(
        "calibration", help="Display the picture calibration information."
    )
    calibration_picture_parser.add_argument(
        "picture", metavar="PIC", type=Path
    )  # .completer = FilesCompleter("ptyx")
    calibration_picture_parser.add_argument(  # type: ignore[attr-defined]
        "path", nargs="?", metavar="PATH", type=Path, default="."
    ).completer = FilesCompleter("ptyx")
    calibration_picture_parser.set_defaults(func=calibration)

    # ------------------------------------------
    argcomplete.autocomplete(parser, always_complete_options=False)
    parsed_args = parser.parse_args(args)
    try:
        # Launch the function corresponding to the given subcommand.
        kwargs = vars(parsed_args)
        func = kwargs.pop("func")
    except KeyError:
        # No subcommand passed.
        parser.print_help()
        return
    func(**kwargs)


def calibration(
    picture: Path,
    path: Path | str = ".",
) -> None:
    """Implement `mcq-dev calibration` command."""
    from .scan.scan_doc import MCQPictureParser

    MCQPictureParser(path).display_picture_calibration(picture)
    print_success(f"Picture '{picture}' displayed.")


def review(
    picture: Path,
    path: Path | str = ".",
) -> None:
    """Implement `mcq review` command."""
    from .scan.scan_doc import MCQPictureParser

    MCQPictureParser(path).scan_single_picture(picture)
    print_success(f"Picture '{picture}' scanned.")


def export_checkboxes(path: Path | str = ".", debug=False):
    from ptyx_mcq.scan.data import ScanData

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


def load_webp(webp: Path) -> ndarray:
    return array(Image.open(str(webp)).convert("L")) / 255


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


if __name__ == "__main__":
    main()
