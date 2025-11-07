import shutil
from pathlib import Path

from ptyx.pretty_print import print_error, print_success, term_color, TermColors

from ptyx_mcq.tools.io_tools import FatalError
from ptyx_mcq.parameters import DEFAULT_TEMPLATE_NAME, DEFAULT_TEMPLATE_FULLPATH, APP_CONFIG_DIR


def create_template(name: str = "default") -> None:
    """Create default user template."""
    if name == DEFAULT_TEMPLATE_NAME:
        print_error(f"Name {name!r} is reserved, please choose another template name.")
        raise FatalError
    user_template = get_user_templates_path() / name
    if user_template.is_dir():
        print_error(f"Folder {user_template} already exist, choose a different template name.")
        raise FatalError
    default_template = DEFAULT_TEMPLATE_FULLPATH
    shutil.copytree(default_template, user_template)
    print_success(f"Template created at {user_template}. Edit the inner files to customize it.")


def list_templates() -> None:
    """List all available templates."""
    print("Default pTyX-MCQ template:")
    print(term_color(f" {DEFAULT_TEMPLATE_NAME}", TermColors.PURPLE))
    print("User-created templates:")
    for path in get_user_templates_path().glob("*"):
        if path.is_dir():
            print(term_color(f"- {path.name}", TermColors.CYAN))


def get_template_path(template_name: str = "") -> Path:
    """Return the path of the directory containing the corresponding template.

    The template is first searched in user config directory.
    If not found, a default template is applied.
    """
    # Default template:
    template_path = DEFAULT_TEMPLATE_FULLPATH
    # Directory of the eventual user templates:
    user_templates_path = get_user_templates_path()
    if template_name == "":
        # Search for a default user-defined template.
        user_default_template_path = user_templates_path / "default"
        if user_default_template_path.is_dir():
            template_path = user_default_template_path
    elif template_name != DEFAULT_TEMPLATE_NAME:
        template_path = user_templates_path / template_name
    if not template_path.is_dir():
        print_error(f"I can't use template {template_name!r}: '{template_path}' directory not found.")
        raise FatalError
    return template_path


def get_user_templates_path():
    """Return the path of the directory where the user's templates are stored."""
    return APP_CONFIG_DIR / "templates"
