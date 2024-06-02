# Utilities for unrolling a WHILE program into a transition system with a limited
# depth

from typing import Iterable, NamedTuple, ClassVar
import typing
import dataclasses
import collections

from while_parsing import Instruction, InstructionType, Operator, OperatorFunction


@dataclasses.dataclass(slots=True, kw_only=True, frozen=True)
class VariableSet:
    _DATA: dict[str, int | None] = dataclasses.field(default_factory=dict)

    def get(self, arg: str | int) -> int | None:
        if isinstance(arg, int):
            return arg
        return self._DATA.get(arg, 0)

    def set(self, var, value) -> "VariableSet":
        new_data = self._DATA.copy()
        if value == 0:
            new_data.pop(var, None)
        else:
            new_data[var] = value
        return VariableSet(_DATA=new_data)

    def __hash__(self):
        return hash(frozenset(self._DATA.items()))

    def __str__(self):
        return ", ".join(f"{k}={v}" for k, v in self._DATA.items())


# Alternative implementaion using tuples, it might be worthwhile to test which
# is faster
#
# class VariableSet(tuple[tuple[str, int | None], ...]):
#    # I use this aa hashable, immutable map
#    def get_value(self, arg: str | int) -> int | None:
#        if isinstance(arg, int):
#            return arg
#
#        i = bisect.bisect_left(self, arg, key=lambda t: t[0])
#        if i < len(self) and self[i][0] == arg:
#            return self[i][1]
#        return 0
#
#    def replace_var(self, changed_var: str, new_value: int | None) -> "VariableSet":
#        i = bisect.bisect_left(self, changed_var, key=lambda t: t[0])
#        if i < len(self) and self[i][0] == changed_var:
#            return VariableSet(self[:i] + ((changed_var, new_value),) + self[i+1:])
#        else:
#            return VariableSet(self[:i] + ((changed_var, new_value),) + self[i:])


def p(x):
    print(x)
    return x


class State(NamedTuple):
    location: int
    variables: VariableSet

    def __str__(self):
        return f"<{self.location}, {self.variables}>"

    @classmethod
    def from_string(cls, state_str: str):
        location, *rest = state_str.strip()[1:-1].split(", ")
        if rest == [""]:
            return cls(int(location), VariableSet())

        data = {}
        for var in rest:
            k, v = var.split("=")
            data[k] = None if v == "None" else int(v)

        return cls(int(location), VariableSet(_DATA=data))


def _init_ts_successor() -> dict[State, tuple[State]]:
    return collections.defaultdict(lambda: (TransitionSystem.SINK_STATE,))


@dataclasses.dataclass(slots=True)
class TransitionSystem:
    SINK_STATE: ClassVar[State] = State(-1, VariableSet())

    depth: int
    initial_state: State = State(0, VariableSet())
    transitions: dict[State, tuple[State, ...]] = dataclasses.field(
        default_factory=_init_ts_successor
    )

    def __str__(self):
        transition_str = "\n".join(
            f"    {k} -> {' | '.join(map(str, v))}" for k, v in self.transitions.items()
        )
        return (
            f"TransitionSystem(depth={self.depth}, initial_state={self.initial_state},"
            f" transitions=\n{transition_str}\n)"
        )


def get_next_states(program: list[Instruction], state: State) -> tuple[State, ...]:
    # returns 0, 1 or 2 states
    location, variables = state
    if location not in range(len(program)):
        return ()
    instruction = program[location]

    def apply_op(op: OperatorFunction, values: Iterable[int | None]) -> int | None:
        args: list[int] = []
        for v in values:
            if v is None:
                return None
            args.append(v)
        return op(*args)

    match instruction:
        case (InstructionType.SET_VAR, (str(var), Operator(f=op), *args)):
            # i cant find a good why to type this in the case statement
            arg_values = map(variables.get, typing.cast(list[str | int], args))
            result = apply_op(op, arg_values)
            return (State(location + 1, variables.set(var, result)),)

        case (InstructionType.JUMP_IF_NOT, (Operator(f=op), *args, int(jump_distance))):
            arg_values = map(variables.get, typing.cast(list[str | int], args))
            result = apply_op(op, arg_values)

            if result is None:
                return State(location + 1, variables), State(
                    location + jump_distance, variables
                )
            if result == 0:
                return (State(location + 1, variables),)
            else:
                return (State(location + jump_distance, variables),)

        case (InstructionType.JUMP, (int(jump_distance),)):
            return (State(location + jump_distance, variables),)

        case (InstructionType.INPUT, (str(x),)):
            new_variables = variables.set(x, None)
            return (State(location + 1, new_variables),)

        case (InstructionType.OUTPUT, _):
            return (State(location + 1, variables),)

        case _:
            raise ValueError(f"Invalid instruction: {instruction}")


def unroll_while_program(program: list[Instruction], depth: int) -> TransitionSystem:
    ts = TransitionSystem(depth)
    current_states: list[State] = [ts.initial_state]

    for _ in range(ts.depth):
        next_states = []
        for state in current_states:
            successor_states = get_next_states(program, state)
            if successor_states:
                ts.transitions[state] = successor_states
            next_states.extend(s for s in successor_states if s not in ts.transitions)
        current_states = next_states

    return ts
