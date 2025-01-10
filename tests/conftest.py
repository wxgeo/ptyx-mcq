# https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tests-according-to-command-line-option
import pytest


@pytest.fixture
def custom_input(monkeypatch):
    monkeypatch.setattr("builtins.input", custom_input := CustomInput())
    return custom_input


class CustomInput:
    """Class used to simulate user input.

    This class should not be called directly.
    Instead, use `custom_input()` fixture, to instantiate it.

    Before using it, one should add a scenario, using `set_scenario()`.
    A scenario is a list of expected questions and the corresponding user answers to provide.
    Each question/answer couple must be a couple of strings.
    Example:

        custom_input.set_scenario([("Overwrite file (y/N) ?", "Y"),
                                   ("Are you sure (y/N) ?", "N")])


    In addition to question/answer couples, scenario may contain comments (simple strings):

        custom_input.set_scenario(["Existing file detected.",
                                   ("Overwrite file (y/N) ?", "N")])

    Those comments will be just printed and are only useful to help debugging.
    """

    def __init__(self) -> None:
        self.scenario: list[tuple[str, str]] = []
        self.index = 0

    def set_scenario(self, scenario: list[tuple[str, str]]) -> None:
        self.scenario = scenario
        self.index = 0

    def __call__(self, text: str = "") -> str:
        while self.index < len(self.scenario) and isinstance(comment := self.scenario[self.index], str):
            assert isinstance(comment, str)  # stupid Pycharm!
            # This is only comments.
            print(f"\033[3;34m# {comment}\033[0m")
            self.index += 1
        print("\033[2;96mQ:", text, "\033[0m")
        try:
            question, answer = self.scenario[self.index]
        except IndexError as e:
            print("\033[1;33mSTOP: Unexpected input request!\033[0m")
            raise ValueError(f"Unexpected input request: {text!r}") from e
        assert text == question, (question, answer)
        print("\033[2;95mA:", answer, "\033[0m")
        self.index += 1
        return answer

    def remaining(self):
        return self.scenario[self.index :]

    def is_empty(self) -> bool:
        return self.index == len(self.scenario)


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False, help="run slow tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
