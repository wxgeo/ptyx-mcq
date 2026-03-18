from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree
from time import strftime

from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION, CACHE_DIR, FIX_DIR, INDEX_DIR
from ptyx_mcq.tools.io_tools import get_file_or_sysexit


@dataclass
class FilesPaths:
    csv_scores: Path
    xlsx_scores: Path
    infos: Path


@dataclass
class DirsPaths:
    root: Path
    data: Path
    cache: Path
    index: Path
    fix: Path
    log: Path
    pdf: Path
    checkboxes: Path


class PathsHandler:
    """Handles the different files and directories used by the scanner.

    The most import file for scanning is the configuration file, with extension "CONFIG_FILE_EXTENSION".
    """

    configfile: Path
    input_dir: Path
    output_dir: Path

    def __init__(self, config_path: Path, input_dir: Path = None, output_dir: Path = None):
        self.configfile = get_file_or_sysexit(config_path, extension=CONFIG_FILE_EXTENSION)

        root = self.configfile.parent

        if input_dir is None:
            input_dir = root / "scan"
        self.input_dir = input_dir

        if output_dir is None:
            output_dir = root / "out"
        self.output_dir = output_dir

        log = output_dir / "log"
        self.dirs = DirsPaths(
            root=root,
            index=output_dir / INDEX_DIR,
            data=output_dir / "data",
            cache=output_dir / CACHE_DIR,
            pdf=output_dir / "pdf",
            checkboxes=output_dir / "checkboxes",
            log=log,
            fix=output_dir / FIX_DIR,
        )
        self.files = FilesPaths(
            csv_scores=output_dir / "scores.csv",
            xlsx_scores=output_dir / "scores.xlsx",
            infos=output_dir / "infos.csv",
        )
        self.logfile_path = log / (strftime("%Y.%m.%d-%H.%M.%S") + ".log")

    def make_dirs(self, reset=False):
        """Make output directory structure. Is reset is `True`, remove all output directory content."""
        if reset and self.output_dir.is_dir():
            rmtree(self.output_dir)
        # noinspection PyUnresolvedReferences
        for dirname in self.dirs.__dataclass_fields__:
            getattr(self.dirs, dirname).mkdir(parents=True, exist_ok=True)
