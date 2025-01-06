import shutil
import subprocess

import pytest
from numpy import ndarray, array

from ptyx_mcq.scan.data import ScanData
from ptyx_mcq.scan.data.conflict_gestion import ConflictSolver
from tests.test_conflict_solver import ASSETS_DIR


@pytest.fixture
def no_display(monkeypatch):
    # noinspection PyUnusedLocal
    def display(self, wait: bool = True) -> subprocess.CompletedProcess | subprocess.Popen:
        print("\033[3;37m[Image displayed here...]\033[0m")
        if wait:
            return subprocess.run(["sleep", "0"])
        else:
            return subprocess.Popen(["sleep", "0"], stdin=subprocess.DEVNULL)

    monkeypatch.setattr("ptyx_mcq.scan.picture_analyze.image_viewer.ImageViewer.display", display)


@pytest.fixture
def patched_conflict_solver(monkeypatch, tmp_path, no_display):
    shutil.copytree(ASSETS_DIR / "no-conflict-v2", tmp_path / "no-conflict-v2")
    scan_data = ScanData(config_path=tmp_path / "no-conflict-v2")
    conflict_solver = ConflictSolver(scan_data)
    conflict_solver.scan_data.run()

    # noinspection PyUnusedLocal
    def get_matrix(self) -> ndarray:
        return array([[0, 0], [0, 0]])  # Array must be at least 2x2 for tests to pass.

    monkeypatch.setattr("ptyx_mcq.scan.data.pictures.Picture.as_matrix", get_matrix)
    return conflict_solver
