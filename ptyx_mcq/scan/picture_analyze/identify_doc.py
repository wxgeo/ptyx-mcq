from dataclasses import dataclass

from numpy import ndarray

from ptyx_mcq.scan.picture_analyze.calibration import CalibrationData
from ptyx_mcq.scan.picture_analyze.square_detection import test_square_color
from ptyx_mcq.scan.picture_analyze.types_declaration import Pixel, Shape, Rectangle, Col
from ptyx_mcq.tools.colors import Color

from ptyx_mcq.tools.config_parser import DocumentId, Page


@dataclass
class IdentificationData:
    # ID of the document:
    doc_id: DocumentId
    # page number:
    page: Page


DebugInfo = list[Shape]


def read_doc_id_and_page(
    m: ndarray, calibration_data: CalibrationData
) -> tuple[IdentificationData, DebugInfo]:
    """Read the document ID and the page number.

    The document ID is encoded using a homemade barcode.
    This code is made of a band of 16 black or white squares.
    (Note that the first one is always black and is only used to detect the band).
    Example: ■■□■□■□■■□□□■□□■ = 0b100100011010101 =  21897
    It allows for 2**15 = 32 768 different values.
    """

    debug_info: DebugInfo = []
    f_square_size = calibration_data.f_square_size
    square_size = round(f_square_size)
    i, j = calibration_data.id_band_position

    doc_id = 0

    # Test the color of the 15 following squares, and interpret it as a binary number.
    for k in range(24):
        j_ = Col(round(j + (k + 1) * f_square_size))
        if test_square_color(m, i, j_, square_size, proportion=0.5, gray_level=0.5):
            doc_id += 2**k
        debug_info.append(Rectangle((i, j_), square_size, color=(Color.red if k % 2 else Color.blue)))

    # Nota: If necessary (although this is highly unlikely !), one may extend protocol
    # by adding a second band (or more !), starting with a black square.
    # This function will test if a black square is present below the first one ;
    # if so, the second band will be joined with the first
    # (allowing 2**30 = 1073741824 different values), and so on.

    page = doc_id % 256
    print("Page read: %s" % page)
    doc_id = doc_id // 256
    print("Test ID read: %s" % doc_id)

    return IdentificationData(DocumentId(doc_id), Page(page)), debug_info
