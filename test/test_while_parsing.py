from hypothesis import given, assume, strategies as st, example
import inspect
import pytest
from while_parsing import *

ID = OPERATORS["ID"]


def test_parse_program():
    source = ["INPUT X", "IF X >= 0 THEN", "Y := X", "ELSE", "Z := -1", "Y := Z * X", "END IF", "OUTPUT Y"]
    expected = [
        Instruction(InstructionType[t], args)
        for t, args in (
            ("INPUT", ("X",)),
            ("JUMP_IF_NOT", (OPERATORS[">="], "X", 0, 3)),
            ("SET_VAR", ("Y", ID, "X")),
            ("JUMP", (3,)),
            ("SET_VAR", ("Z", ID, -1)),
            ("SET_VAR", ("Y", OPERATORS["*"], "Z", "X")),
            ("OUTPUT", ("Y",)),
        )
    ]

    assert list(parse_program(source)) == expected


def test_lazy_parsing():
    source = ["INPUT X"]

    def source_it():
        for i in it.count():
            yield source[i]

    program = parse_program(source_it())
    assert next(program) == Instruction(InstructionType.INPUT, ("X",))
    source.append("INPUT Y")
    assert next(program) == Instruction(InstructionType.INPUT, ("Y",))


@given(...)
def test_interactive_shell(x: int):
    inputs = iter([
        "INPUT X",
        str(x),
        "IF X >= 0 THEN",
        "Y := X",
        "ELSE",
        "Z := -1",
        "Y := Z * X",
        "END IF",
        "OUTPUT Y",
        "EXIT",
    ])

    def input_func(_):
        return next(inputs)

    outputs = []

    def output_func(x):
        outputs.append(x)

    run_interactive_shell(None, input_func, output_func)
    assert outputs[1:] == [str(abs(x))]


def test_comment():
    source = ["// this should output 0", "", "OUTPUT Y"]
    expected = [Instruction(InstructionType["OUTPUT"], ("Y",))]
    assert list(parse_program(source)) == expected


@given(op_name=st.sampled_from(list(OPERATORS)), args=..., use_infix=...)
def test_operators(op_name: str, args: list[int], use_infix: bool):
    arg_names = list(map(str, args))
    op = OPERATORS[op_name]
    if not args:
        use_infix = False
    if use_infix:
        first, *rest = arg_names
        source = [f"out := {first} {op_name} {' '.join(rest)}"]
    else:
        source = [f"out := {op_name} {' '.join(map(str, arg_names))}"]

    params = inspect.signature(op.f).parameters
    is_variadic = [param.kind for param in params.values()] == [inspect.Parameter.VAR_POSITIONAL]

    if op.is_infix != use_infix or (not is_variadic and len(params) != len(args)):
        with pytest.raises(ValueError):
            next(parse_program(source))
        return

    program = list(parse_program(source))
    if op_name == "/" and args[1] == 0:
        with pytest.raises(ZeroDivisionError):
            run_program(program)
    else:
        assert run_program(program) == {"out": op.f(*args)}


@given(...)
def test_run_program(x_value: int):
    program = (
        Instruction(InstructionType[t], args)
        for t, args in (
            ("SET_VAR", ("X", ID, x_value)),
            ("JUMP_IF_NOT", (OPERATORS[">="], "X", 0, 3)),
            ("SET_VAR", ("Y", ID, "X")),
            ("JUMP", (3,)),
            ("SET_VAR", ("Z", ID, -1)),
            ("SET_VAR", ("Y", OPERATORS["*"], "Z", "X")),
            ("OUTPUT", ("Y",)),
        )
    )
    if x_value >= 0:
        assert run_program(program) == {"X": x_value, "Y": abs(x_value)}
    else:
        assert run_program(program) == {"X": x_value, "Y": abs(x_value), "Z": -1}


def test_while():
    program = (
        Instruction(InstructionType[t], args)
        for t, args in (
            ("SET_VAR", ("X", ID, 0)),
            ("JUMP_IF_NOT", (OPERATORS["<"], "X", 100, 3)),
            ("SET_VAR", ("X", OPERATORS["+"], "X", 1)),
            ("JUMP", (-2,)),
        )
    )
    assert run_program(program) == {"X": 100}
