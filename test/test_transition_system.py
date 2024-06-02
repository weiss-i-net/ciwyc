from transition_system import VariableSet, get_next_states, State, unroll_while_program
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


def test_unroll_while_program():
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
    print(ts)
    print(ts.transitions[State(7, VariableSet(_DATA={"y": 1, "x": -1}))])
