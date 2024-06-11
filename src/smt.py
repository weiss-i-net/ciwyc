import z3
import functools as fun

from util import *


# conforms to the IntEncoding Protocol
class Z3Int(z3.ArithRef):
    @classmethod
    def create_variable(cls, name: str) -> z3.ArithRef:
        return z3.Int(name)

    @classmethod
    def create_literal(cls, value: int) -> z3.ArithRef:
        return z3.IntVal(value)


# In principle the WHILE language only knows integers, but to avoid conversions with z3, the operatos ar split up into
# int and bool operators here
SMT_INT_OPERATORS: dict[str, OperatorFunction[Z3Int, Z3Expression]] = {
    "--": lambda n: -n,
    "ID": lambda n: n,
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda _, __: z3.FreshInt(prefix="/"),
    "%": lambda _, __: z3.FreshInt(prefix="%"),
    "SUM": lambda *args: sum(args, start=z3.IntVal(0)),
    "PRODUCT": lambda *args: fun.reduce(lambda a, b: a * b, args, z3.IntVal(1)),
}

SMT_BOOL_OPERATORS: dict[str, OperatorFunction[Z3Int, Z3BoolExpression]] = {
    "TRUE": lambda: z3.BoolVal(1),
    "FALSE": lambda: z3.BoolVal(0),
    "NOT": lambda n: n == z3.IntVal(0),
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "!=": lambda a, b: a != b,
    "AND": lambda a, b: z3.And(a != 0, b != 0),
    "OR": lambda a, b: z3.Or(a != 0, b != 0),
    "ALL": lambda *args: z3.And([a != 0 for a in args]),
    "ANY": lambda *args: z3.Or([a != 0 for a in args]),
}


def get_operator_restriction(op_name: str, *args: Z3Int, other: None | Z3Int = None) -> Z3BoolExpression:
    if (op := SMT_INT_OPERATORS.get(op_name)) is not None:
        return to_z3_bool(op(*args)) if other is None else op(*args) == other

    if (op := SMT_BOOL_OPERATORS.get(op_name)) is not None:
        return op(*args) if other is None else to_z3_int(op(*args)) == other

    raise ValueError(f"{op_name} is not supported for SMT encoding")
