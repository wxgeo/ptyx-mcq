import io
import sys
from types import TracebackType
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def copy_docstring(src: Callable) -> Callable[[F], F]:
    """Tiny wrapper to import the docstring of a method from a parent class.

    The parent class method must have the same name.

    Note that, while it is meant to copy the docstring of a same name method of the parent class,
    this docstring can in fact be imported from any class, though it is probably not that useful.
    (Restricting import to parent classes only would imply a significant overhead).
    """

    def my_decorator(dest: F) -> F:
        dest.__doc__ = src.__doc__
        return dest

    return my_decorator


# The following class is used by ptyx-mcq-editor and ptyx-mcq-corrector.


class CaptureLog(io.StringIO):
    """Context manager used to capture a copy of stdout and stderr output.

    Both stdout and stderr are directed to stdout,
    and a copy is then kept in memory to be able to retrieve the output's content later.

    Use CaptureLog.getvalue() to retrieve the output's content *before* leaving
    this context manager."""

    def __enter__(self) -> "CaptureLog":
        self.previous_stdout = sys.stdout
        self.previous_stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        sys.stdout = self.previous_stdout
        sys.stderr = self.previous_stderr
        self.close()

    def write(self, s: str, /) -> int:
        self.previous_stdout.write(s)
        return super().write(s)
