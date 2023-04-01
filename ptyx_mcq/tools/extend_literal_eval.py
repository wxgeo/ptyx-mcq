from _ast import (
    Expression,
    Constant,
    UnaryOp,
    UAdd,
    USub,
    Tuple,
    List,
    Set,
    Name,
    Call,
    Dict,
    BinOp,
    Add,
    Sub,
)
from ast import parse


def extended_literal_eval(node_or_string, names: dict = None):
    """
    Safely evaluate an expression node or a string containing a Python
    expression.

    In python's `ast.literal_eval()`, the string or node provided
    may only consist of the following Python literal structures:
    strings, bytes, numbers, tuples, lists, dicts, sets, booleans, and None.

    This extends `ast.literal_eval()` by providing a `names` dictionary.
    To add support to `MyClass(...)`, you have to pass `names={"MyClass": MyClass}`.
    """
    if names is None:
        names = {}
    if isinstance(node_or_string, str):
        node_or_string = parse(node_or_string.lstrip(" \t"), mode="eval")
    if isinstance(node_or_string, Expression):
        node_or_string = node_or_string.body

    def _raise_malformed_node(node):
        msg = "malformed node or string"
        if lno := getattr(node, "lineno", None):
            msg += f" on line {lno}"
        raise ValueError(msg + f": {node!r}")

    def _convert_num(node):
        if not isinstance(node, Constant) or type(node.value) not in (int, float, complex):
            _raise_malformed_node(node)
        return node.value

    # noinspection PyTypeChecker
    def _convert_signed_num(node):
        if isinstance(node, UnaryOp) and isinstance(node.op, (UAdd, USub)):
            operand = _convert_num(node.operand)
            if isinstance(node.op, UAdd):
                return +operand
            else:
                return -operand
        return _convert_num(node)

    # noinspection PyTypeChecker
    def _convert(node):
        if isinstance(node, Constant):
            return node.value
        elif isinstance(node, Tuple):
            return tuple(map(_convert, node.elts))
        elif isinstance(node, List):
            return list(map(_convert, node.elts))
        elif isinstance(node, Set):
            return set(map(_convert, node.elts))
        elif isinstance(node, Name) and node.id in names:
            return names[node.id]
        elif (
            isinstance(node, Call)
            and isinstance(node.func, Name)
            and node.func.id == "set"
            and node.args == node.keywords == []
        ):
            return set()
        elif isinstance(node, Call) and isinstance(node.func, Name) and node.func.id in names:
            return names[node.func.id](
                *map(_convert, node.args), **{kw.arg: _convert(kw.value) for kw in node.keywords}
            )
        elif isinstance(node, Dict):
            if len(node.keys) != len(node.values):
                _raise_malformed_node(node)
            return dict(zip(map(_convert, node.keys), map(_convert, node.values)))
        elif isinstance(node, BinOp) and isinstance(node.op, (Add, Sub)):
            left = _convert_signed_num(node.left)
            right = _convert_num(node.right)
            if isinstance(left, (int, float)) and isinstance(right, complex):
                if isinstance(node.op, Add):
                    return left + right
                else:
                    return left - right
        return _convert_signed_num(node)

    return _convert(node_or_string)
