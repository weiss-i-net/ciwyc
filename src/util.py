import z3

from typing import Literal, Callable, Protocol

type Z3Expression = z3.ExprRef | z3.Tactic
type Z3BoolExpression = z3.BoolRef | Literal[True] | Literal[False] | z3.Probe


class Variadic[Arg, Ret](Protocol):  # new python 3.12 generic type syntax
    def __call__(self, *args: Arg) -> Ret: ...


type OperatorFunction[Arg, Ret] = (  # new python 3.12 type alias syntax
    Callable[[], Ret] | Callable[[Arg], Ret] | Callable[[Arg, Arg], Ret] | Variadic[Arg, Ret]
)


def to_z3_bool(z3_var: Z3Expression) -> Z3BoolExpression:
    return z3_var != z3.IntVal(0)


def to_z3_int(z3_bool: Z3BoolExpression) -> Z3Expression:
    return z3.If(z3_bool, z3.IntVal(1), z3.IntVal(0))
