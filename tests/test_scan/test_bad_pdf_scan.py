import shutil

from ptyx_mcq.scan import scan
from tests import ASSETS_DIR



def test_bad_pdf(tmp_path):
    shutil.copytree(original := (ASSETS_DIR / "bad-pdf-scan"), target := (tmp_path / "bad-pdf-scan"))
    scan(target)
    assert (target / "out/scores.csv").read_text("utf8") == (original/"scores.csv").read_text("utf8")