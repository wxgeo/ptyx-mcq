import io
from hashlib import blake2b
from pathlib import Path
from shutil import rmtree
from multiprocessing import Pool
from typing import TYPE_CHECKING, NewType

import fitz
import numpy as np
from PIL import Image, UnidentifiedImageError
from numpy import ndarray
from fitz import Pixmap
from ptyx.shell import print_warning

from ptyx_mcq.parameters import IMAGE_FORMAT
from ptyx_mcq.scan.data.paths_manager import PathsHandler

# from ptyx_mcq.scan.data.documents import PdfHash, PicNum, PdfData
from ptyx_mcq.scan.picture_analyze.calibration import calibrate, CalibrationData, adjust_contrast
from ptyx_mcq.scan.picture_analyze.identify_doc import read_doc_id_and_page, IdentificationData
from ptyx_mcq.scan.picture_analyze.types_declaration import CalibrationError
from ptyx_mcq.scan.pdf.utilities import number_of_pages
from ptyx_mcq.tools.extend_literal_eval import extended_literal_eval
from ptyx_mcq.tools.pic import array_to_image, image_to_array

if TYPE_CHECKING:
    from ptyx_mcq.scan.data import ScanData

PdfHash = NewType("PdfHash", str)
PicNum = NewType("PicNum", int)
PdfData = dict[PdfHash, dict[PicNum, tuple[CalibrationData, IdentificationData]]]


class PdfCollection:
    """
    Manage all input pdf, and extract its content.

    The main method is `.collect_data()`, which populates
    the `.data` dictionary.
    """

    def __init__(self, data_handler: "ScanData"):
        self.data_handler = data_handler
        self._data: PdfData | None = None

    @property
    def data(self) -> PdfData:
        if self._data is None:
            self.collect_data()
            assert self._data is not None
        return self._data

    @property
    def paths(self) -> PathsHandler:
        return self.data_handler.paths

    def _generate_current_pdf_hashes(self) -> dict[PdfHash, Path]:
        """Return the hashes of all the pdf files found in `scan/` directory.

        Return: {hash: pdf path}
        """
        hashes = dict()
        for path in self.paths.input_dir.glob("**/*.pdf"):
            with open(path, "rb") as pdf_file:
                hashes[PdfHash(blake2b(pdf_file.read(), digest_size=20).hexdigest())] = path
        return hashes

    def _parallel_collect(
        self, hash2pdf: dict[PdfHash, Path], number_of_processes: int | None = PdfData
    ) -> PdfData:
        # For each new pdf files, extract all pictures
        to_extract: list[tuple[Path, Path, PicNum]] = []
        pdf_data: PdfData = {}

        # TODO: use ThreadPool instead?
        with Pool(number_of_processes) as pool:
            for pdf_hash, pdf_path in hash2pdf.items():
                folder = self.paths.dirs.cache / pdf_hash
                # Only append a page if the corresponding .pic-data file is not found.
                # (Resume an interrupted scan without extracting again previously extracted pages).
                to_extract.extend(
                    [
                        (pdf_path, folder, PicNum(page_num))
                        for page_num in range(number_of_pages(pdf_path))
                        if not (folder / f"{page_num}.pic-data").is_file()
                    ]
                )
            if to_extract:
                print("Extracting pictures from pdf...")
                result: list[tuple[CalibrationData, IdentificationData]] = pool.starmap(
                    extract_pdf_page, to_extract
                )
                for (_, folder, page_num), pic_data in zip(to_extract, result):
                    if pic_data is not None:
                        pdf_data.setdefault(PdfHash(folder.name), {})[page_num] = pic_data
        return pdf_data

    def _sequential_collect(self, hash2pdf: dict[str, Path]) -> PdfData:
        pdf_data: PdfData = {}
        for pdf_hash, pdf_path in hash2pdf.items():
            folder = self.paths.dirs.cache / pdf_hash
            for page_num in range(number_of_pages(pdf_path)):
                # Only extract a page if the corresponding .pic-data file is not found.
                # (Resume an interrupted scan without extracting again previously extracted pages).
                print(f"Extracting page {page_num + 1} from '{pdf_path}'...")
                pic_data = extract_pdf_page(pdf_path, folder, PicNum(page_num))
                if pic_data is not None:
                    pdf_data.setdefault(folder.name, {})[PicNum(page_num)] = pic_data
        return pdf_data

    def collect_data(self, number_of_processes=1) -> PdfData:
        """Test if input data has changed, and update information if needed.

        Data are stored on disk, to avoid saturating memory, and to allow resuming
        after interruption.
        """
        hash2pdf: dict[PdfHash, Path] = self._generate_current_pdf_hashes()
        # 1. Remove old data from disk if there is no corresponding pdf.
        self._remove_obsolete_files(hash2pdf)
        # 2. Extract all data from existing pdf files
        # (if not already done in a previous run).
        if number_of_processes == 1:
            self._data = self._sequential_collect(hash2pdf)
        else:
            self._data = self._parallel_collect(hash2pdf, number_of_processes=number_of_processes)
        return self._data

    def _remove_obsolete_files(self, hash2pdf: dict[str, Path]) -> None:
        """For each removed pdf files, remove corresponding pictures and data."""
        for path in self.paths.dirs.cache.iterdir():
            # No file should be found, only directories!
            if not path.is_dir():
                raise RuntimeError(
                    f'Folder "{path.parent}" should only contain folders.\n'
                    "You may clean it manually, or remove it with the following command:\n"
                    f'rm -r "{path.parent}"'
                )
            # Remove any directory whose name don't match any existing pdf file, and all corresponding data.
            if path.name not in hash2pdf:
                # for doc_id in self._get_corresponding_doc_ids(path.name):
                #     self.data_handler.remove_doc_files(DocumentId(int(doc_id)))
                rmtree(path)


def extract_pdf_page(
    pdf_file: Path, dest: Path, page_num: PicNum
) -> tuple[CalibrationData, IdentificationData] | None:
    """Extract data corresponding to the given page of the pdf.

    Cached data will be used if available and not corrupted.

    The following actions will be successively executed:
    - get the page content as a grayscale picture array.
    - adjust the contrast of the picture.
    - calibrate the picture: find the four corners' black squares, and adjust rotation accordingly.
    - generate a `.pic-calibration` file, with calibration information.
    - save the rectified picture on disk.
    - extract the document number and page, and store them in a `.pic-data` file.
    """
    if (dest / f"{page_num}.skip").is_file():
        # Skip the page (empty one for example).
        return None
    # Define paths.
    calibration = dest / "calibration"
    identification = dest / "identification"
    pic_file = dest / f"{page_num}.{IMAGE_FORMAT}"
    calibration_file = calibration / str(page_num)
    identification_file = identification / str(page_num)
    # Create folders.
    for folder in (dest, calibration, identification):
        folder.mkdir(exist_ok=True)
    # Load information from a previous scan process, if available.
    if pic_file.is_file() and calibration_file.is_file() and identification_file.is_file():
        valid_pic = True
        calibration_data: CalibrationData | None = None
        identification_data: IdentificationData | None = None
        try:
            # Test that the image is correct.
            Image.open(pic_file)
        except UnidentifiedImageError:
            valid_pic = False
        try:
            calibration_data = extended_literal_eval(
                calibration_file.read_text("utf8"), {"CalibrationData": CalibrationData}
            )
        except Exception as e:
            print(e)
            print_warning(f"Unable to load file: {calibration_file}")
        try:
            identification_data = extended_literal_eval(
                identification_file.read_text("utf8"), {"IdentificationData": IdentificationData}
            )
        except Exception as e:
            print(e)
            print_warning(f"Unable to load file: {identification_file}")
        if not valid_pic or calibration_data is None or identification_data is None:
            return _extract_pdf_page(pdf_file, page_num, pic_file, calibration_file, identification_file)
        return calibration_data, identification_data
    # Else, parse the scanned page image to retrieve info.
    else:
        return _extract_pdf_page(pdf_file, page_num, pic_file, calibration_file, identification_file)


def _extract_pdf_page(
    pdf_file: Path, page_num: PicNum, pic_file: Path, calibration_file: Path, identification_file: Path
) -> tuple[CalibrationData, IdentificationData] | None:
    """
    Extract data corresponding to the given page of the pdf.
    """
    # Get the page content as a grayscale picture array.
    img_array = _get_page_content_as_array(pdf_file, page_num)
    # Adjust the contrast of the picture.
    img_array = adjust_contrast(img_array, filename=f"<{pdf_file} - page_num {page_num + 1}>")
    # Calibrate the picture: find the four corners' black squares, and adjust rotation accordingly.
    try:
        img_array, calibration_data = calibrate(img_array)
    except CalibrationError:
        pic_file.with_suffix(".skip").touch()
        return None
    # Save the rectified picture on disk.
    array_to_image(img_array).save(pic_file, format=IMAGE_FORMAT)
    # Generate a `.pic-calibration` file, with calibration information.
    calibration_file.write_text(repr(calibration_data), "utf8")
    identification_data, _ = read_doc_id_and_page(img_array, calibration_data)
    identification_file.write_text(repr(identification_data), "utf8")
    return calibration_data, identification_data


def _get_page_content_as_array(pdf_file: Path, page_num: PicNum) -> ndarray:
    doc = fitz.Document(pdf_file)
    page = doc[page_num]
    if _contain_only_a_single_image(page):
        xref: int = page.get_images()[0][0]
        img_info = doc.extract_image(xref)
        return image_to_array(Image.open(io.BytesIO(img_info["image"])))
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
