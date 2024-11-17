import io
from hashlib import blake2b
from pathlib import Path
from shutil import rmtree
from multiprocessing import Pool
from typing import TYPE_CHECKING

import fitz
import numpy as np
from PIL import Image
from numpy import ndarray
from fitz import Pixmap

from ptyx_mcq.parameters import IMAGE_FORMAT
from ptyx_mcq.scan.data_gestion.document_data import PicData
from ptyx_mcq.scan.data_gestion.paths_handler import PathsHandler
from ptyx_mcq.scan.picture_analyze.calibration import calibrate, CalibrationData, adjust_contrast
from ptyx_mcq.scan.picture_analyze.scan_pic import scan_picture
from ptyx_mcq.tools.config_parser import DocumentId
from ptyx_mcq.scan.pdf.utilities import number_of_pages
from ptyx_mcq.tools.extend_literal_eval import extended_literal_eval
from ptyx_mcq.tools.pic import array_to_image, image_to_array

if TYPE_CHECKING:
    from ptyx_mcq.scan.data_gestion.data_handler import DataHandler


class PdfCollection:
    """Manage all input pdf, and extract its content."""

    def __init__(self, data_handler: "DataHandler"):
        self.data_handler = data_handler

    @property
    def paths(self) -> PathsHandler:
        return self.data_handler.paths

    def _generate_current_pdf_hashes(self) -> dict[str, Path]:
        """Return the hashes of all the pdf files found in `scan/` directory.

        Return: {hash: pdf path}
        """
        hashes = dict()
        for path in self.paths.input_dir.glob("**/*.pdf"):
            with open(path, "rb") as pdf_file:
                hashes[blake2b(pdf_file.read(), digest_size=20).hexdigest()] = path
        return hashes

    def _parallel_run(self, hash2pdf: dict[str, Path]):
        # For each new pdf files, extract all pictures
        to_extract: list[tuple[Path, Path, int]] = []
        # TODO: use ThreadPool instead?
        with Pool() as pool:
            for pdfhash, pdfpath in hash2pdf.items():
                folder = self.paths.dirs.pic / pdfhash
                # Only append a page if the corresponding .pic-data file is not found.
                # (Resume an interrupted scan without extracting again previously extracted pages).
                to_extract.extend(
                    [
                        (pdfpath, folder, page_num)
                        for page_num in range(number_of_pages(pdfpath))
                        if not (folder / f"{page_num}.pic-data").is_file()
                    ]
                )
            if to_extract:
                print("Extracting pictures from pdf...")
                pool.starmap(extract_pdf_page, to_extract)

    def _sequential_run(self, hash2pdf: dict[str, Path]):
        for pdfhash, pdfpath in hash2pdf.items():
            folder = self.paths.dirs.pic / pdfhash
            for page_num in range(number_of_pages(pdfpath)):
                # Only extract a page if the corresponding .pic-data file is not found.
                # (Resume an interrupted scan without extracting again previously extracted pages).
                if not (folder / f"{page_num}.pic-data").is_file():
                    print(f"Extracting pictures from pdf '{pdfpath}'...")
                    extract_pdf_page(pdfpath, folder, page_num)

    def prepare_input_data(self, parallelism=False) -> None:
        """Test if input data has changed, and update information if needed.

        Data are stored on disk, to avoid saturating memory.
        """
        hash2pdf: dict[str, Path] = self._generate_current_pdf_hashes()
        self._remove_obsolete_files(hash2pdf)
        if parallelism:
            self._parallel_run(hash2pdf)
        else:
            self._sequential_run(hash2pdf)

    @staticmethod
    def load_pic_data(path: Path) -> PicData:
        return extended_literal_eval(path.read_text(), {"PicData": PicData})

    def _get_corresponding_doc_ids(self, pdfhash: str) -> list[DocumentId]:
        """Get all the documents id corresponding to the pdf with the given hash.

        Note that:
        - The same document may appear in several pdf (some pages in one pdf, other pages in another pdf).
        - This method() relies on the generated `.pic-data` files, so the list may be incomplete
          (the `.pic-data` may not have been generated yet, or be generated during a previous process which was
          abruptly interrupted).
        """
        return [
            self.load_pic_data(pic_data_file).doc_id
            for pic_data_file in (self.paths.dirs["pic"] / pdfhash).glob("*.pic-data")
        ]

    def _remove_obsolete_files(self, hash2pdf: dict[str, Path]) -> None:
        """For each removed pdf files, remove corresponding pictures and data."""
        for path in self.paths.dirs.pic.iterdir():
            # No file should be found, only directories!
            if not path.is_dir():
                raise RuntimeError(
                    f'Folder "{path.parent}" should only contain folders.\n'
                    "You may clean it manually, or remove it with the following command:\n"
                    f'rm -r "{path.parent}"'
                )
            # Remove any directory whose name don't match any existing pdf file, and all corresponding data.
            if path.name not in hash2pdf:
                for doc_id in self._get_corresponding_doc_ids(path.name):
                    self.data_handler.remove_doc_files(DocumentId(int(doc_id)))
                rmtree(path)


# def extract_pdf_pictures(
#     pdf_file: Path, dest: Path, format=IMAGE_FORMAT, enhance_contrast=True, verbose=True
# ) -> None:
#     """Clear `dest` folder, then extract all pages of the pdf files inside."""
#     rmtree(dest, ignore_errors=True)
#     dest.mkdir()
#
#     page: fitz.Page
#     doc = fitz.Document(pdf_file)
#     if verbose:
#         print(f"Extracting pages from '{pdf_file}' as pictures...")
#     # noinspection PyTypeChecker
#     for i, page in enumerate(doc.pages(), start=1):
#         # Extract picture if the page contains only a picture (this is quite fast).
#         if _contain_only_a_single_image(page):
#             xref: int = page.get_images()[0][0]
#             img_info = doc.extract_image(xref)
#             ext = img_info["ext"].lower()
#             img_array: ndarray = np.array(Image.open(io.BytesIO((img_info["image"]))).convert("L"))
#             # if f".{ext}" in PIC_EXTS:
#             #     # This is a known format, proceed with extraction.
#             #     (dest / f"{i:03d}.{ext}").write_bytes(img_info["image"])
#         else:
#             # In all other cases, we'll have to rasterize the whole page and save it as a JPG picture
#             # (unfortunately, this is much slower than a simple extraction).
#             pix: Pixmap = page.get_pixmap(dpi=200, colorspace=fitz.Colorspace(fitz.CS_GRAY))
#             img_array = np.frombuffer(pix.samples_mv, dtype=np.uint8).reshape((pix.height, pix.width))  # type: ignore
#         # Adjust contrast: a MCQ should have black pixels and white ones, so the darkest should be black ones
#         # and the lightest should be white ones in fact.
#         if enhance_contrast:
#             img_array = adjust_contrast(img_array, filename=f"<{pdf_file} - page {i}>")
#         array_to_image(img_array).save(format=format)


def extract_pdf_page(pdf_file: Path, dest: Path, page_num: int) -> tuple[ndarray, PicData]:
    """Extract data corresponding to the given page of the pdf.

    The following actions will be successively executed:
    - get the page content as a grayscale picture array.
    - adjust the contrast of the picture.
    - calibrate the picture: find the four corners' black squares, and adjust rotation accordingly.
    - generate a `.pic-calibration` file, with calibration information.
    - save the rectified picture on disk.
    - extract the document number and page, and store them in a `.pic-data` file.
    """
    dest.mkdir(exist_ok=True)
    pic_file = dest / f"{page_num}.{IMAGE_FORMAT}"
    calibration_file = dest / f"{page_num}.pic-calibration"
    if pic_file.is_file() and calibration_file.is_file():
        # Load information from a previous scan process, if available.
        img_array = image_to_array(Image.open(pic_file))
        calibration_data = extended_literal_eval(
            calibration_file.read_text("utf8"), {"CalibrationData": CalibrationData}
        )
    else:
        # Get the page content as a grayscale picture array.
        img_array = _get_page_content_as_array(pdf_file, page_num)
        # Adjust the contrast of the picture.
        img_array = adjust_contrast(img_array, filename=f"<{pdf_file} - page {page_num + 1}>")
        # Calibrate the picture: find the four corners' black squares, and adjust rotation accordingly.
        img_array, calibration_data = calibrate(img_array)
        # Generate a `.pic-calibration` file, with calibration information.
        calibration_file.write_text(repr(calibration_data), "utf8")
        # Save the rectified picture on disk.
        array_to_image(img_array).save(pic_file, format=IMAGE_FORMAT)


def _get_page_content_as_array(pdf_file: Path, page_num: int) -> ndarray:
    doc = fitz.Document(pdf_file)
    page = doc[page_num]
    if _contain_only_a_single_image(page):
        xref: int = page.get_images()[0][0]
        img_info = doc.extract_image(xref)
        return np.array(Image.open(io.BytesIO((img_info["image"]))).convert("L"))
    else:
        # In all other cases, we'll have to rasterize the whole page and save it as a JPG picture
        # (unfortunately, this is much slower than a simple extraction).
        pix: Pixmap = page.get_pixmap(dpi=200, colorspace=fitz.Colorspace(fitz.CS_GRAY))
        return np.frombuffer(pix.samples_mv, dtype=np.uint8).reshape((pix.height, pix.width))  # type: ignore


def _contain_only_a_single_image(page: fitz.Page) -> bool:
    """Test if the page contains only a single picture."""
    return (
        len(page.get_images()) == 1
        and len(page.get_drawings()) == 0
        and len(page.get_textpage().extractBLOCKS()) == 0
    )
