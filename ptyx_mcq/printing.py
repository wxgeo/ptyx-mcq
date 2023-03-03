import sys

shell_colors = {
    "red": 1,
    "green": 2,
    "yellow": 3,
    "blue": 4,
}


def custom_print(msg: str, color: str, label: str, bold=False, **kw) -> None:
    n = shell_colors[color]
    print(f"\33[3{n}m[\33[9{n}{';1' if bold else ''}m{label}\33[0m\33[3{n}m]\33[0m " + msg)

def print_error(msg: str) -> None:
    custom_print(msg, 'red', 'Error', bold=True, file=sys.stderr)


def print_warning(msg: str) -> None:
    custom_print(msg, 'yellow', 'Warning', bold=False)


def print_success(msg: str) -> None:
    custom_print(msg, 'green', 'OK', bold=True)


def print_info(msg: str) -> None:
    custom_print(msg, 'blue', 'Info', bold=False)
