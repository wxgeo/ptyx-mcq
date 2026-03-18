import os
import shutil
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import argcomplete

from ptyx.pretty_print import print_error, print_success

from ptyx_mcq.tools.io_tools import FatalError
from ptyx_mcq.parameters import PACKAGE_ROOT, APP_CONFIG_DIR

COMPLETION_DATA_DIR = APP_CONFIG_DIR / "autocompletion"

SCRIPTS: dict[str, Path] = {
    "mcq": PACKAGE_ROOT / "cli.py",
    "mcq-dev": PACKAGE_ROOT / "dev_cli.py",
}

if TYPE_CHECKING:
    for script in SCRIPTS.values():
        assert script.is_file()


def _set_shebang(script_path: Path, new_shebang: str) -> None:
    """
    Add a shebang or modify existing one for the given script file.

    The shebang is the first line of the script file, starting with `#!`.
    It is used to set the default interpreter of the file (which must be executable).
    """
    with open(script_path, "r+", encoding="utf8") as f:
        lines = f.readlines()
        f.seek(0)
        f.write(new_shebang.strip() + "\n")
        if lines[0].startswith("#!"):
            # Remove old shebang.
            f.writelines(lines[1:])
        else:
            f.writelines(lines)
        f.truncate()


def install_shell_completion(shell: str = "bash") -> None:
    """Enable completion for the `mcq` command in the shell (bash by default)."""
    if shell != "bash":
        print_error(f"Sorry, {shell} completion not yet supported. :-(")
        raise FatalError

    # Don't use the original `cli.py` file for autocompletion:
    #   - `argcomplete` expects it to be executable, which may not be the case,
    #     and we might not be able to change its permissions.
    #   - We may also need to modify its shebang so that it’s executed with the correct
    #     Python interpreter. (It might not be the system one — in fact, it should be
    #     different if `ptyx-mcq` is installed in a virtual environment, which is
    #     the recommended practice.)

    COMPLETION_DATA_DIR.mkdir(exist_ok=True, parents=True)
    for command, src in SCRIPTS.items():
        dst = COMPLETION_DATA_DIR / src.name
        shutil.copy(src, COMPLETION_DATA_DIR)
        # Set current interpreter as the file default interpreter.
        _set_shebang(dst, f"#!{sys.executable}")
        # Make the file executable.
        os.chmod(dst, os.stat(dst).st_mode | stat.S_IEXEC)

        if _install_completion(f"{command}-{shell}-completion", command, dst, shell):
            print_success(f"Completion enabled in {shell} for `{command}`. Enjoy!")
            print("Hint: execute `source ~/.bashrc` to activate it in your current bash session.")
        else:
            print_success(f"Completion updated in {shell} for `{command}`.")


def _install_completion(completion_file_name: str, command: str, python_script: Path, shell: str) -> bool:
    completion_file_path = COMPLETION_DATA_DIR / completion_file_name
    with open(completion_file_path, "w") as f:
        f.write(argcomplete.shellcode([command], shell=shell, argcomplete_script=str(python_script)))
    bash_rc = Path("~/.bashrc").expanduser()
    newlines = f"\n# PTYX-MCQ: Enable {command} command completion\nsource {completion_file_path}\n"
    # print(newlines)
    if not (bash_rc.is_file() and newlines in bash_rc.read_text()):
        with open(bash_rc, "a") as f:
            f.write(newlines)
        return True
    return False
