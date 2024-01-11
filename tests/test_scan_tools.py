from ptyx_mcq.scan.types_declaration import CORNER_NAMES, Corner


def test_corners():
    for name in CORNER_NAMES:
        assert Corner.from_string(name).to_string() == name
