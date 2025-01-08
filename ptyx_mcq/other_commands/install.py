import os
from pathlib import Path

import argcomplete
from platformdirs import PlatformDirs

from ptyx.shell import print_error, print_success, print_info

from ptyx_mcq.tools.io_tools import FatalError
from ptyx_mcq.parameters import PACKAGE_ROOT

CLI_SCRIPT = PACKAGE_ROOT / "cli.py"
DEV_CLI_SCRIPT = PACKAGE_ROOT / "dev_cli.py"

assert CLI_SCRIPT.is_file()
assert DEV_CLI_SCRIPT.is_file()


def install_shell_completion(shell: str = "bash") -> None:
    """Enable completion for the `mcq` command in the shell (bash by default)."""
    if shell != "bash":
        print_error(f"Sorry, {shell} completion not yet supported. :-(")
        raise FatalError
    if not os.access(CLI_SCRIPT, os.X_OK):
        print_error(
            f"Unable to install completion since {CLI_SCRIPT} is not executable. Fix it with:\n"
            f"chmod u+x {CLI_SCRIPT}"
        )
        raise FatalError

    done = []
    if _install_completion(f"mcq-{shell}-completion", "mcq", CLI_SCRIPT, shell):
        done.append("`mcq`")
    if _install_completion(f"mcq-dev-{shell}-completion", "mcq-dev", DEV_CLI_SCRIPT, shell):
        done.append("`mcq-dev`")

    if done:
        print_success(f"Completion enabled in {shell} for {' and '.join(done)}. Enjoy!")
    else:
        print_info(f"Completion in {shell} was already activated. Nothing done.")


def _install_completion(completion_file_name, command, python_script, shell) -> bool:
    completion_file = PlatformDirs().user_config_path / "ptyx-mcq/config" / completion_file_name
    completion_file.parent.mkdir(parents=True, exist_ok=True)
    with open(completion_file, "w") as f:
        f.write(argcomplete.shellcode([command], shell=shell, argcomplete_script=str(python_script)))
    bash_rc = Path("~/.bashrc").expanduser()
    newlines = f"\n# Enable {command} command completion\nsource {completion_file}\n"
    if not (bash_rc.is_file() and newlines in bash_rc.read_text()):
        with open(bash_rc, "a") as f:
            f.write(newlines)
        return True
    else:
        return False
