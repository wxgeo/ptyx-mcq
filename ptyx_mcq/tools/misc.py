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
