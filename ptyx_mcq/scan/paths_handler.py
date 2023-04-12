from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree
from time import strftime

from ptyx_mcq.tools.io_tools import get_file_or_sysexit


@dataclass
class FilesPaths:
    verified: Path
    skipped: Path
    more_infos: Path
    csv_scores: Path
    xlsx_scores: Path
    infos: Path


@dataclass
class DirsPaths:
    root: Path
    data: Path
    cfg: Path
    pic: Path
    log: Path
    pdf: Path


class PathsHandler:
    """Handles the different files and directories used by the scanner.

    The most import file for scanning is the configuration file, with extension ".ptyx.mcq.config.json".
    """

    configfile: Path
    input_dir: Path
    output_dir: Path

    def __init__(self, config_path: Path, input_dir: Path = None, output_dir: Path = None):
        self.configfile = get_file_or_sysexit(config_path, extension=".ptyx.mcq.config.json")

        root = self.configfile.parent

        if input_dir is None:
            input_dir = root / "scan"
        self.input_dir = input_dir

        if output_dir is None:
            output_dir = root / ".scan"
        self.output_dir = output_dir
        # `.scan` directory is used to write intermediate files.
        # Directory tree:
        # .scan/
        # .scan/pic -> pictures extracted from the pdf
        # .scan/cfg/more_infos.csv -> missing students names.
        # .scan/cfg/verified.csv -> pages already verified.
        # .scan/cfg/skipped.csv -> pages to skip.
        # .scan/scores.csv
        # .scan/data -> data stored as .scandata files (used to resume interrupted scan).

        cfg = output_dir / "cfg"
        log = output_dir / "log"
        self.dirs = DirsPaths(
            root=root,
            cfg=cfg,
            data=output_dir / "data",
            pic=output_dir / "pic",
            pdf=output_dir / "pdf",
            log=log,
        )
        self.files = FilesPaths(
            verified=cfg / "verified.txt",
            skipped=cfg / "skipped.txt",
            more_infos=cfg / "more_infos.csv",
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
