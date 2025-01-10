from pathlib import Path

import pymupdf  # type: ignore
import numpy as np
from PIL import ImageChops
from PIL import Image


def number_of_pages(pdf_path: Path) -> int:
    """Return the number of pages of the pdf."""
    return len(pymupdf.Document(pdf_path))


def rasterize_pdf_page(pdf_path: Path | str, page_number: int, dpi: int = 96) -> Image.Image:
    """Rasterize a PDF page to an image."""
    with pymupdf.open(pdf_path) as pdf:
        pix = pdf[page_number].get_pixmap(dpi=dpi, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


# def rasterize_pdf(pdf_path: Path | str, dpi: int = 96) -> list[Image.Image]:
#     """Rasterize a PDF page to an image."""
#     with pymupdf.open(pdf_path) as pdf:
#         images: list[Image] = []
#         for page in pdf:
#             pix = page.get_pixmap(dpi=dpi, alpha=False)
#             img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
#             images.append(img)
#         return images


def _as_same_size_images(img1, img2) -> tuple[Image.Image, Image.Image]:
    """Resize both images to the same dimensions, using the maximal width and height of the 2 images."""
    size = max(img1.width, img2.width), max(img1.height, img2.height)
    return img1.resize(size, Image.BICUBIC), img2.resize(size, Image.BICUBIC)


def _compare_images(img1: Image.Image, img2: Image.Image, tolerance: int = 10) -> bool:
    """Compare two images with a pixel intensity difference tolerance."""
    diff: Image.Image = ImageChops.difference(img1, img2)

    # Convert difference image to NumPy array for analysis
    diff_array: np.ndarray = np.array(diff)

    # Calculate pixel-wise difference (sum of RGB channels)
    diff_intensity: np.ndarray = np.sum(diff_array, axis=2)

    # Check if differences exceed the tolerance
    significant_diff: np.ndarray = diff_intensity > (tolerance * 3)  # 3 channels (R, G, B)
    return not np.any(significant_diff)  # True if no significant differences


def similar_pdf_page(
    pdf1: Path | str, page1: int, pdf2: Path | str, page2: int = None, dpi: int = 96, tolerance: int = 10
) -> bool:
    """Test if pdf pages look similar."""
    if page2 is None:
        page2 = page1
    return _compare_images(
        rasterize_pdf_page(pdf1, page1, dpi=dpi),
        rasterize_pdf_page(pdf2, page2, dpi=dpi),
        tolerance=tolerance,
    )


def similar_pdfs(pdf1: Path | str, pdf2: Path | str, dpi: int = 96, tolerance: int = 10) -> bool:
    """Test if pdf documents look similar."""
    with pymupdf.open(pdf1) as doc1, pymupdf.open(pdf2) as doc2:
        len1, len2 = len(doc1), len(doc2)
    if len1 != len2:
        print(f"PDFs have a different number of pages ({len1} != {len2}).")
        return False

    for i in range(len1):
        if not similar_pdf_page(pdf1, i, pdf2, i, dpi=dpi, tolerance=tolerance):
            print(f"Difference found on page {i + 1}.")
            return False

    return True
