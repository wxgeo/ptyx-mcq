from ptyx_mcq.scan.picture_analyze.checkbox_analyzer import DetectionStatus

UNCHECKED = DetectionStatus.UNCHECKED
CHECKED = DetectionStatus.CHECKED
PROBABLY_CHECKED = DetectionStatus.PROBABLY_CHECKED
PROBABLY_UNCHECKED = DetectionStatus.PROBABLY_CHECKED

ANSWERED = {
    1: {4: {3}, 20: {4, 5}, 25: {3}},
    2: {3: {2, 6, 7}, 5: {5}, 24: {6}, 28: {1}},
    3: {2: {8}, 11: {6}, 13: {2}, 30: {2}},
    4: {8: {5}, 10: {1}, 21: {7}, 23: {4}, 26: {1, 5, 9}},
    5: {9: {5, 6}, 12: {1}, 17: {1, 2, 3, 5}, 22: {4}, 27: {1}, 29: {1, 4}},
    6: {},
}

ANSWERS_CHECK_DATA = {
    1: {
        (4, 1): UNCHECKED,
        (4, 2): UNCHECKED,
        (4, 3): CHECKED,
        (4, 4): UNCHECKED,
        (4, 5): UNCHECKED,
        (4, 6): UNCHECKED,
        (20, 1): UNCHECKED,
        (20, 2): UNCHECKED,
        (20, 3): UNCHECKED,
        (20, 4): CHECKED,
        (20, 5): CHECKED,
        (20, 6): UNCHECKED,
        (20, 7): UNCHECKED,
        (25, 1): UNCHECKED,
        (25, 2): UNCHECKED,
        (25, 3): CHECKED,
        (25, 4): UNCHECKED,
        (25, 5): UNCHECKED,
        (25, 6): UNCHECKED,
        (25, 7): UNCHECKED,
        (25, 8): UNCHECKED,
        (25, 9): UNCHECKED,
    },
    2: {
        (3, 1): UNCHECKED,
        (3, 2): CHECKED,
        (3, 3): UNCHECKED,
        (3, 4): UNCHECKED,
        (3, 5): UNCHECKED,
        (3, 6): CHECKED,
        (3, 7): CHECKED,
        (3, 8): UNCHECKED,
        (3, 9): UNCHECKED,
        (5, 1): UNCHECKED,
        (5, 2): UNCHECKED,
        (5, 3): UNCHECKED,
        (5, 4): UNCHECKED,
        (5, 5): CHECKED,
        (5, 6): UNCHECKED,
        (24, 1): UNCHECKED,
        (24, 2): UNCHECKED,
        (24, 3): UNCHECKED,
        (24, 4): UNCHECKED,
        (24, 5): UNCHECKED,
        (24, 6): CHECKED,
        (24, 7): UNCHECKED,
        (24, 8): UNCHECKED,
        (24, 9): UNCHECKED,
        (28, 1): CHECKED,
        (28, 2): UNCHECKED,
        (28, 3): UNCHECKED,
        (28, 4): UNCHECKED,
        (28, 5): UNCHECKED,
        (28, 6): UNCHECKED,
        (28, 7): UNCHECKED,
        (28, 8): UNCHECKED,
    },
    3: {
        (2, 1): UNCHECKED,
        (2, 2): UNCHECKED,
        (2, 3): UNCHECKED,
        (2, 4): UNCHECKED,
        (2, 5): UNCHECKED,
        (2, 6): UNCHECKED,
        (2, 7): UNCHECKED,
        (2, 8): CHECKED,
        (11, 1): UNCHECKED,
        (11, 2): UNCHECKED,
        (11, 3): UNCHECKED,
        (11, 4): UNCHECKED,
        (11, 5): UNCHECKED,
        (11, 6): CHECKED,
        (13, 1): UNCHECKED,
        (13, 2): CHECKED,
        (13, 3): UNCHECKED,
        (13, 4): UNCHECKED,
        (13, 5): UNCHECKED,
        (30, 1): UNCHECKED,
        (30, 2): CHECKED,
        (30, 3): UNCHECKED,
        (30, 4): UNCHECKED,
        (30, 5): UNCHECKED,
        (30, 6): UNCHECKED,
        (30, 7): UNCHECKED,
        (30, 8): UNCHECKED,
        (30, 9): UNCHECKED,
    },
    4: {
        (8, 1): UNCHECKED,
        (8, 2): UNCHECKED,
        (8, 3): UNCHECKED,
        (8, 4): UNCHECKED,
        (8, 5): CHECKED,
        (10, 1): CHECKED,
        (10, 2): UNCHECKED,
        (10, 3): UNCHECKED,
        (10, 4): UNCHECKED,
        (21, 1): UNCHECKED,
        (21, 2): UNCHECKED,
        (21, 3): UNCHECKED,
        (21, 4): UNCHECKED,
        (21, 5): UNCHECKED,
        (21, 6): UNCHECKED,
        (21, 7): CHECKED,
        (21, 8): UNCHECKED,
        (21, 9): UNCHECKED,
        (23, 1): UNCHECKED,
        (23, 2): UNCHECKED,
        (23, 3): UNCHECKED,
        (23, 4): CHECKED,
        (23, 5): UNCHECKED,
        (23, 6): UNCHECKED,
        (23, 7): UNCHECKED,
        (23, 8): UNCHECKED,
        (23, 9): UNCHECKED,
        (26, 1): CHECKED,
        (26, 2): UNCHECKED,
        (26, 3): UNCHECKED,
        (26, 4): UNCHECKED,
        (26, 5): CHECKED,
        (26, 6): UNCHECKED,
        (26, 7): UNCHECKED,
        (26, 8): UNCHECKED,
        (26, 9): CHECKED,
        (26, 10): UNCHECKED,
        (26, 11): UNCHECKED,
        (26, 12): UNCHECKED,
    },
    5: {
        (9, 1): UNCHECKED,
        (9, 2): UNCHECKED,
        (9, 3): UNCHECKED,
        (9, 4): UNCHECKED,
        (9, 5): CHECKED,
        (9, 6): CHECKED,
        (9, 7): UNCHECKED,
        (12, 1): CHECKED,
        (12, 2): UNCHECKED,
        (12, 3): UNCHECKED,
        (12, 4): UNCHECKED,
        (12, 5): UNCHECKED,
        (12, 6): UNCHECKED,
        (17, 1): CHECKED,
        (17, 2): CHECKED,
        (17, 3): CHECKED,
        (17, 4): UNCHECKED,
        (17, 5): CHECKED,
        (17, 6): UNCHECKED,
        (22, 1): UNCHECKED,
        (22, 2): UNCHECKED,
        (22, 3): UNCHECKED,
        (22, 4): CHECKED,
        (22, 5): UNCHECKED,
        (22, 6): UNCHECKED,
        (22, 7): UNCHECKED,
        (22, 8): UNCHECKED,
        (27, 1): CHECKED,
        (27, 2): UNCHECKED,
        (27, 3): UNCHECKED,
        (27, 4): UNCHECKED,
        (27, 5): UNCHECKED,
        (27, 6): UNCHECKED,
        (29, 1): CHECKED,
        (29, 2): UNCHECKED,
        (29, 3): UNCHECKED,
        (29, 4): CHECKED,
        (29, 5): UNCHECKED,
    },
    6: {},
}