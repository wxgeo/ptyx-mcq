import shutil
from pathlib import Path

from ptyx.shell import print_error, print_success

from ptyx_mcq import FatalError
from ptyx_mcq.other_commands.template import get_template_path
from ptyx_mcq.tools.io_tools import get_file_or_sysexit


def new(path: Path, include: Path = None, template="") -> None:
    """Implement `mcq new` command.

    Path `path` is the path of the new file to create.
    Path `include` must be a directory whose all .ex files will be recursively included.
    """
    # Select the template to use.
    template_path = get_template_path(template)
    # Create the new MCQ.
    if path.exists():
        print_error(f"Path {path} already exists.")
        raise FatalError
    else:
        print(f"Using template from '{template_path}'.")
        shutil.copytree(template_path, path)
        if include is not None:
            # No need to have a questions directory template,
            # since questions' files will be explicitly listed.
            shutil.rmtree(path / "questions", ignore_errors=True)
            # Edit the .ptyx file, to replace default code with the list of the questions' files.
            ptyx_path = get_file_or_sysexit(path, extension=".ptyx")
            new_lines = [f"-- DIR: {include.resolve()}"]
            for include_path in include.glob("**/*.ex"):
                new_lines.append(f"-- {include_path.relative_to(include)}")
            lines = []
            with open(ptyx_path, encoding="utf8") as f:
                include_section = False
                for line in f:
                    line = line.rstrip("\n")
                    if line.startswith("<<<<"):
                        include_section = True
                        lines.append(line)
                        lines.extend(new_lines)
                    elif line.startswith(">>>>"):
                        include_section = False
                        lines.append(line)
                    elif not include_section:
                        lines.append(line)

            with open(ptyx_path, "w", encoding="utf8") as f:
                f.write("\n".join(lines) + "\n")
        print_success(f"A new MCQ was created at {path}.")
