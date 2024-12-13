from pathlib import Path

# The root of the package, i.e. the `ptyx_mcq` directory.
PACKAGE_ROOT = Path(__file__).resolve().parent

# Default template path
DEFAULT_TEMPLATE_DIR = "assets/templates"
DEFAULT_TEMPLATE_NAME = "original"
DEFAULT_TEMPLATE_FULLPATH = PACKAGE_ROOT / DEFAULT_TEMPLATE_DIR / DEFAULT_TEMPLATE_NAME

CONFIG_FILE_EXTENSION = ".ptyx.mcq.config.json"

# Various dimensions, given in cm.
CALIBRATION_SQUARE_POSITION = 1
CALIBRATION_SQUARE_SIZE = 0.5
SQUARE_SIZE_IN_CM = 0.25
CELL_SIZE_IN_CM = 0.5
PAPER_FORMATS = {"A4": (21, 29.7), "A5": (14.8, 21), "A3": (29.7, 42)}
PAPER_FORMAT = "A4"
MARGIN_LEFT_IN_CM = 1.5
MARGIN_RIGHT_IN_CM = 1.5
MARGIN_TOP_IN_CM = 2.5
MARGIN_BOTTOM_IN_CM = 2

# The image format used to store the pictures extracted from the input pdf files.
IMAGE_FORMAT = "webp"
