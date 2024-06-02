from transition_system import *
from while_parsing import parse_program


def test_variable_set():
    s1 = VariableSet()
    s2 = s1.set("a", 1)
    assert s2.get("a") == 1
    assert s2.get("b") == 0
    assert s2.get(10) == 10
    assert hash(s1) != hash(s2)
    assert hash(s2) == hash(VariableSet().set("a", 1).set("c", 0))
    s3 = s2.set("a", 0)
    assert hash(s1) == hash(s3)


def test_get_next_states():
    source = """
    y := 1
    INPUT x
    IF x < 0 THEN
        OUTPUT x
    ELSE
        x := x * -1
        OUTPUT x
    END IF
    """
    program = list(parse_program(source.splitlines()))
    (s0,) = get_next_states(program, State(0, VariableSet()))
    assert s0 == State(1, VariableSet(_DATA={"y": 1}))
    (s1,) = get_next_states(program, s0)
    assert s1 == State(2, VariableSet(_DATA={"y": 1, "x": None}))
    s2, s3 = get_next_states(program, s1)
    if s2.location > s2.location:
        s2, s3 = s3, s2
    assert s2 == State(3, VariableSet(_DATA={"y": 1, "x": None}))
    assert s3 == State(5, VariableSet(_DATA={"y": 1, "x": None}))


def test_unroll_while_program_simple():
    source = """
    y := 1
    INPUT x
    IF x < 0 THEN
        OUTPUT x
    ELSE
        x := y * -1
        OUTPUT x
    END IF
    """
    program = list(parse_program(source.splitlines()))
    for i, stmt in enumerate(program):
        print(f"{i}: {stmt}")
    ts = unroll_while_program(program, 10)
    # fmt: off
    expected_ts = TransitionSystem(10, State(0, VariableSet()),
        {
            State.from_string("<0, >"): (State.from_string("<1, y=1>"),),
            State.from_string("<1, y=1>"): (State.from_string("<2, y=1, x=None>"),),
            State.from_string("<2, y=1, x=None>"): ( State.from_string("<3, y=1, x=None>"), State.from_string("<5, y=1, x=None>"),),
            State.from_string("<3, y=1, x=None>"): ( State.from_string("<4, y=1, x=None>"),),
            State.from_string("<5, y=1, x=None>"): ( State.from_string("<6, y=1, x=-1>"),),
            State.from_string("<4, y=1, x=None>"): ( State.from_string("<7, y=1, x=None>"),),
            State.from_string("<6, y=1, x=-1>"): (State.from_string("<7, y=1, x=-1>"),),
        },
    )
    # fmt: on
    assert ts == expected_ts


def test_unroll_while_program_loop():
    source = """
    INPUT x
    WHILE x < 10 DO
        x := x + 1
        y := y + 1
    END WHILE
    OUTPUT x
    OUTPUT y
    """
    depth = 11
    program = list(parse_program(source.splitlines()))
    ts = unroll_while_program(program, depth)
    expected_ts = TransitionSystem(
        depth,
        State(0, VariableSet()),
        {
            State.from_string(lhs): tuple(State.from_string(m) for m in rhs)
            for lhs, rhs in [
                ("<0, >", ["<1, x=None>"]),
                ("<1, x=None, y=1>", ["<2, x=None, y=1>", "<5, x=None, y=1>"]),
                ("<1, x=None, y=2>", ["<2, x=None, y=2>", "<5, x=None, y=2>"]),
                ("<1, x=None>", ["<2, x=None>", "<5, x=None>"]),
                ("<2, x=None, y=1>", ["<3, x=None, y=1>"]),
                ("<2, x=None, y=2>", ["<3, x=None, y=2>"]),
                ("<2, x=None>", ["<3, x=None>"]),
                ("<3, x=None, y=1>", ["<4, x=None, y=2>"]),
                ("<3, x=None>", ["<4, x=None, y=1>"]),
                ("<4, x=None, y=1>", ["<1, x=None, y=1>"]),
                ("<4, x=None, y=2>", ["<1, x=None, y=2>"]),
                ("<5, x=None, y=1>", ["<6, x=None, y=1>"]),
                ("<5, x=None, y=2>", ["<6, x=None, y=2>"]),
                ("<5, x=None>", ["<6, x=None>"]),
                ("<6, x=None, y=1>", ["<7, x=None, y=1>"]),
                ("<6, x=None>", ["<7, x=None>"]),
            ]
        },
    )
    assert ts == expected_ts

