import z3
import typing
import string

from typing import Protocol, NamedTuple, Callable, Iterable, Type

from util import Z3BoolExpression
from while_parsing import Instruction, InstructionType, Operator


# We only support the 26 lowercase letters as variable names in the WHILE program
# the formulas short, but this can exteneded here:
WhileIdentifiers = string.ascii_lowercase


# This protocol (a way of doing interfaces in python) represents a way of encoding integer variables
# in our encoding. in the case of SMT encoding, this is z3.Int, whereas for SAT we implemented our own
# type based on list[z3.Bool]. To extened the code with more encodings, you need this type as well as
# the apply_bool_operator and apply_value_operator functions.


# CRTP in python :D https://en.wikipedia.org/wiki/Curiously_recurring_template_pattern
class IntEncoding[T](Protocol):
    # The == operator should return a z3 formula. z3.Int already conforms to
    # this protocol. This is for comparing values while creating the
    # encoding. The encoding of the == operator in WHILE code is defined
    # elsewhere
    @typing.overload
    def __eq__(self, other: T) -> Z3BoolExpression: ...

    @classmethod
    def create_variable(cls, name: str) -> T: ...

    @classmethod
    def create_literal(cls, value: int) -> T: ...


# variable in our created formula that represents a single variable in the WHILE
# code, in the case of SMT, value is of type z3.Int
class Variable[T](NamedTuple):
    value: T
    is_known: z3.BoolRef


# Variable in the created formula that represents a state in the transition system.
# The created formula should encode a relation between such states
class StateVariable[T: IntEncoding](NamedTuple):
    location: T  # needs to support addition with integers
    variables: dict[str, Variable[T]]

    @classmethod
    def init(cls, prefix: str, create_variable: Callable[[str], T]) -> "StateVariable[T]":
        variables = {
            name: Variable[T](create_variable(f"{prefix}_{name}_value"), z3.Bool(f"{prefix}_{name}_is_known"))
            for name in WhileIdentifiers
        }
        location = create_variable(f"{prefix}_location")
        return cls(location, variables)

    def get(self, var: str | int, create_literal: Callable[[int], T]) -> Variable[T]:
        if isinstance(var, int):
            return Variable[T](create_literal(var), z3.BoolVal(True))
        if var not in WhileIdentifiers:
            raise ValueError(f"Indentifier {var} is not supported for model checking")
        return self.variables[var]

    def variables_equal(self, other: "StateVariable[T]") -> Z3BoolExpression:
        var_conditions = []
        for indentifier in WhileIdentifiers:
            self_value, self_is_known = self.variables[indentifier]
            other_value, other_is_known = other.variables[indentifier]
            var_conditions.append(self_value == other_value)
            var_conditions.append(self_is_known == other_is_known)
        return z3.And(var_conditions)

    def variables_equal_except(self, other: "StateVariable[T]", excluded_varname: str) -> Z3BoolExpression:
        var_conditions = []
        for indentifier in WhileIdentifiers:
            if indentifier == excluded_varname:
                continue
            self_value, self_is_known = self.variables[indentifier]
            other_value, other_is_known = other.variables[indentifier]
            var_conditions.append(self_value == other_value)
            var_conditions.append(self_is_known == other_is_known)
        return z3.And(var_conditions)


class OperatorRestrictionGetter[T](Protocol):
    def __call__(self, op_name: str, *args: T, other: None | T = None) -> Z3BoolExpression: ...


def get_single_transition_formulas[
    T: IntEncoding
](
    instruction: Instruction,
    location: int,
    state_a: StateVariable[T],
    state_b: StateVariable[T],
    create_literal: Callable[[int], T],
    get_operator_restriction: OperatorRestrictionGetter[T],
) -> tuple[Z3BoolExpression, ...]:
    # returns up to four subformulas

    shared_conditions: list[Z3BoolExpression] = [state_a.location == create_literal(location)]

    match instruction:
        case (InstructionType.SET_VAR, (str(var), Operator(name=op_name), *args)):
            state_a_vars = [state_a.get(typing.cast(int | str, arg), create_literal) for arg in args]

            a_vars_known = z3.And([v.is_known for v in state_a_vars])
            b_value, b_var_known = state_b.get(var, create_literal)
            op_restriction = get_operator_restriction(
                op_name, *(v.value for v in state_a_vars), other=b_value
            )

            shared_conditions.append(
                get_operator_restriction("+", state_a.location, create_literal(1), other=state_b.location)
            )
            shared_conditions.append(state_a.variables_equal_except(state_b, var))

            unknown_transition = z3.And(z3.Not(a_vars_known), z3.Not(b_var_known), *shared_conditions)
            known_transition = z3.And(a_vars_known, b_var_known, op_restriction, *shared_conditions)

            return (unknown_transition, known_transition)

        case (InstructionType.JUMP_IF_NOT, (Operator(name=op_name), *args, int(jump_distance))):
            state_a_vars = [state_a.get(typing.cast(int | str, arg), create_literal) for arg in args]
            a_vars_known = z3.And([v.is_known for v in state_a_vars])
            op_result = get_operator_restriction(op_name, *(v.value for v in state_a_vars))

            shared_conditions.append(state_a.variables_equal(state_b))
            location_restriction_nojump = get_operator_restriction(
                "+", state_a.location, create_literal(1), other=state_b.location
            )
            location_restriction_jump = get_operator_restriction(
                "+", state_a.location, create_literal(jump_distance), other=state_b.location
            )

            unknown_nojump_transition = z3.And(
                location_restriction_nojump, z3.Not(a_vars_known), *shared_conditions
            )
            unknown_jump_transition = z3.And(
                location_restriction_jump, z3.Not(a_vars_known), *shared_conditions
            )

            known_nojump_transition = z3.And(
                location_restriction_nojump, a_vars_known, z3.Not(op_result), *shared_conditions
            )
            known_jump_transition = z3.And(
                location_restriction_jump, a_vars_known, op_result, *shared_conditions
            )

            return (
                unknown_nojump_transition,
                unknown_jump_transition,
                known_nojump_transition,
                known_jump_transition,
            )

        case (InstructionType.JUMP, (int(jump_distance),)):
            transition = z3.And(
                get_operator_restriction(
                    "+", state_a.location, create_literal(jump_distance), other=state_b.location
                ),
                state_a.variables_equal(state_b),
                *shared_conditions,
            )
            return (transition,)

        case (InstructionType.OUTPUT, *_):
            transition = z3.And(
                get_operator_restriction("+", state_a.location, create_literal(1), other=state_b.location),
                state_a.variables_equal(state_b),
                *shared_conditions,
            )
            return (transition,)

        case (InstructionType.INPUT, (str(var),)):
            _, b_var_known = state_b.get(var, create_literal)

            transition = z3.And(
                get_operator_restriction("+", state_a.location, create_literal(1), other=state_b.location),
                state_a.variables_equal_except(state_b, var),
                b_var_known == z3.BoolVal(False),
                *shared_conditions,
            )
            return (transition,)

        case _:
            raise ValueError(f"Invalid instruction: {instruction}")


def get_transition_relation[
    T: IntEncoding
](
    program: Iterable[Instruction], Encoding: Type[T], get_operator_restriction: OperatorRestrictionGetter[T]
) -> Callable[[int, int], Z3BoolExpression]:
    # The original approach was to create a formula with dummy variables first and then substitute them in
    # is_successor, but this turned out to complicated. Also I'm not sure which is faster.

    def is_successor(state_a_index: int, state_b_index: int) -> Z3BoolExpression:
        state_a = StateVariable.init(str(state_a_index), Encoding.create_variable)
        state_b = StateVariable.init(str(state_b_index), Encoding.create_variable)

        transition_formulas = []
        for loc, inst in enumerate(program):
            transition_formulas.extend(
                get_single_transition_formulas(
                    inst, loc, state_a, state_b, Encoding.create_literal, get_operator_restriction
                )
            )
        return z3.Or(transition_formulas)

    return is_successor
