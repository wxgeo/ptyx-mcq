from io import BytesIO
from pathlib import Path

from PIL import Image
from numpy import int8, ndarray, array


def array_to_image(matrix: ndarray) -> Image.Image:
    """Convert a grayscale array to the corresponding PIL Image instance."""
    return Image.fromarray((255 * matrix).astype(int8))


def image_to_array(image: Image) -> ndarray:
    """Convert a PIL Image to a grayscale numpy array."""
    # "L" -> Convert to grayscale picture.
    return array(image.convert("L")) / 255


def save_webp(matrix: ndarray, path_or_stream: Path | str | BytesIO, lossless=False) -> None:
    """Save image content as a WEBP image."""
    array_to_image(matrix).save(path_or_stream, format="WEBP", lossless=lossless)


def load_webp(webp: Path) -> ndarray:
    """Load a WEBP image as a grayscale numpy array."""
    return image_to_array(Image.open(str(webp)))


def convert_to_webp(src: Path, dest: Path, lossless=False) -> None:
    """Convert any PIL-supported image to WEBP."""
    Image.open(str(src)).save(dest, format="WEBP", lossless=lossless)
