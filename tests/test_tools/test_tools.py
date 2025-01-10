import shutil

import pytest
import numpy as np

from ptyx_mcq.tools.extend_literal_eval import extended_literal_eval
from ptyx_mcq.tools.io_tools import is_ptyx_file, get_file_with_extension
from ptyx_mcq.tools.pdf import similar_pdfs, similar_pdf_page
from ptyx_mcq.tools.pic import load_webp, save_webp, convert_to_webp
from tests import ASSETS_DIR


def calculate_rmse(image1, image2):
    """
    Calculate the Root Mean Squared Error (RMSE) between two images.
    """
    # Convert images to NumPy arrays
    array1 = np.array(image1)
    array2 = np.array(image2)

    # Ensure both images have the same dimensions
    if array1.shape != array2.shape:
        raise ValueError("Images do not have the same dimensions.")

    # Compute the mean squared error
    mse = np.mean((array1 - array2) ** 2)

    # Return the square root of the MSE (RMSE)
    return np.sqrt(mse)


def test_extend_literal_eval():
    assert extended_literal_eval("set()") == set()

    class A(list):
        def __eq__(self, other):
            return isinstance(other, A) and super().__eq__(other)

    a = extended_literal_eval("A((1, 2, inf))", {"A": A, "inf": float("inf")})
    assert type(a) is A
    assert a == A([1, 2, float("inf")])
    assert not (a == [1, 2, float("inf")])  # Do not test with !=, since it is not reimplemented.


def test_is_ptyx_file(tmp_path):
    # pTyX files must be accepted
    ptyx_file = ASSETS_DIR / "ptyx-files/minimal-working-example/minimal-working-example.ptyx"
    assert ptyx_file.is_file()
    assert is_ptyx_file(ptyx_file)
    # LateX files must be rejected
    latex_file = ptyx_file.with_suffix(".tex")
    assert latex_file.is_file()
    assert not is_ptyx_file(latex_file)
    # Non-existent files must be rejected
    nonexistent_file = ptyx_file.with_suffix(".nonexistent")
    assert not nonexistent_file.is_file()
    assert not is_ptyx_file(nonexistent_file)
    # pTyX files with incorrect extensions must yet be accepted
    incorrect_extension_file = tmp_path / "wrong-extension.extension"
    shutil.copy(ptyx_file, incorrect_extension_file)
    assert incorrect_extension_file.is_file()
    assert is_ptyx_file(incorrect_extension_file)


def test_get_file_with_extension():
    path = ASSETS_DIR / "test-conflict-solver/no-conflict-v2/ie2.ptyx.mcq.config.json"
    assert get_file_with_extension(path.parent, extension=".ptyx.mcq.config.json") == path
    assert get_file_with_extension(path, extension=".ptyx.mcq.config.json") == path
    with pytest.raises(FileNotFoundError):
        assert get_file_with_extension(path, extension=".ptyx") == path
    with pytest.raises(FileNotFoundError):
        assert get_file_with_extension(path.parent, extension=".ptyx") == path


def test_webp(tmp_path):
    """Test WEBP image manipulation:
    - loading to numpy array
    - saving from numpy array
    - conversion from other image type
    """
    tolerance = 0.01
    tmp_file = tmp_path / "tmp.webp"
    array = load_webp(ASSETS_DIR / "scan-results-samples/mcq.webp")
    array2 = load_webp(ASSETS_DIR / "scan-results-samples/mcq2.webp")
    save_webp(array, tmp_file)
    assert calculate_rmse(load_webp(tmp_file), array) < tolerance
    convert_to_webp(ASSETS_DIR / "scan-results-samples/mcq.png", tmp_file)
    assert calculate_rmse(load_webp(tmp_file), array) < tolerance
    assert calculate_rmse(array, array2) > tolerance


def test_pdf_comparison():
    folder = ASSETS_DIR / "cli-tests/pdf-targets"
    assert similar_pdfs(pdf := folder / "vanilla-version.pdf", pdf)
    assert similar_pdf_page(pdf, 0, pdf)
    assert not similar_pdfs(pdf, other_pdf := folder / "for-review-version.pdf")
    assert not similar_pdf_page(pdf, 0, other_pdf)
    folder = ASSETS_DIR / "test-conflict-solver/duplicate-files/scan"
    assert not similar_pdf_page(folder / "flat-scan-conflict.pdf", 0, folder / "flat-scan.pdf")
