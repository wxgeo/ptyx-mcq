from ptyx_mcq.scan.calibration import Corner, CORNER_NAMES


def test_corners():
    for name in CORNER_NAMES:
        assert Corner.from_string(name).to_string() == name
