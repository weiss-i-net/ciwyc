# Parser and runtime for the WHILE programing language (adapted from a ECS 189C homework)
#
# The only variable type is integer, variables evaluate to false iff they are 0.
#
# Syntax (EBNF):
#   var = (* any string without whitespace that does not start with a number, keyword or operator *);
#
#   op = (* see below *);
#
#   infix_op = (* see below *);
#
#   expression = op, " ", {var | int}
#              | (var | int), " ", infix_op, " ", (var | int);
#
#   comment = "\n"
#           | "//", {char - "\n"}, "\n";
#
#   statement = var, " := ", expression, "\n"
#             | "IF ", expression, " THEN\n", while_program, ["ELSE\n", while_program], "END IF\n"
#             | "WHILE ", expression, " DO\n", while_program, "END WHILE\n"
#             | "INPUT ", var
#             | "OUTPUT ", expression
#             | comment;
#
#   while_program = {statement};
#
# TODO: add ASSERT statement

from collections.abc import Sequence, Callable, Iterator, Iterable
from typing import NamedTuple, Protocol
from enum import Enum
import argparse
import itertools as it
import math
import inspect
import collections


class Variadic[Arg, Ret](Protocol):  # new python 3.12 generic type syntax
    def __call__(self, *args: Arg) -> Ret: ...


type OperatorFunction[Arg, Ret] = (  # new python 3.12 type alias syntax
    Callable[[], Ret]
    | Callable[[Arg], Ret]
    | Callable[[Arg, Arg], Ret]
    | Variadic[Arg, Ret]
)


class Operator(NamedTuple):
    name: str
    is_infix: bool
    f: OperatorFunction[int, int]


OPERATORS: dict[str, Operator] = {
    op.name: op
    for op in [
        Operator("TRUE", False, lambda: True),
        Operator("FALSE", False, lambda: False),
        Operator("NOT", False, lambda n: not n),
        Operator("--", False, lambda n: -n),
        Operator("ID", False, lambda n: n),
        Operator("<", True, lambda a, b: a < b),
        Operator("<=", True, lambda a, b: a <= b),
        Operator("==", True, lambda a, b: a == b),
        Operator(">=", True, lambda a, b: a >= b),
        Operator(">", True, lambda a, b: a > b),
        Operator("!=", True, lambda a, b: a != b),
        Operator("AND", True, lambda a, b: a and b),
        Operator("OR", True, lambda a, b: a or b),
        Operator("+", True, lambda a, b: a + b),
        Operator("-", True, lambda a, b: a - b),
        Operator("*", True, lambda a, b: a * b),
        Operator("/", True, lambda a, b: a // b),
        Operator("%", True, lambda a, b: a // b),
        Operator("^", True, lambda a, b: a**b),
        Operator("ALL", False, lambda *args: all(args)),
        Operator("ANY", False, lambda *args: any(args)),
        Operator("SUM", False, lambda *args: sum(args)),
        Operator("PRODUCT", False, lambda *args: math.prod(args)),
    ]
}

InstructionType = Enum(
    "InstructionType",
    ["SET_VAR", "JUMP_IF_NOT", "JUMP", "INPUT", "OUTPUT"],
    # the jump instructions use relative addresses
)

KEYWORDS = [":=", "IF", "THEN", "ELSE", "END", "INPUT", "OUTPUT", "WHILE", "DO"]


class Instruction(NamedTuple):
    instruction_type: InstructionType
    args: tuple[str | int | Operator, ...]


def parse_program(source_code: Iterable[str]) -> Iterator[Instruction]:
    """Lazily parses the the source_code line by line.

    If an if statement is encountered, the instructions are stored in a buffer,
    so the jump distance can be determined"""

    if_else_stack = []
    while_stack = []
    program_buffer = []

    def is_int(arg):
        try:
            int(arg)
            return True
        except ValueError:
            return False

    def is_valid_var(var: str) -> bool:
        return not any(
            var.startswith(s) for s in it.chain(KEYWORDS, OPERATORS, "+-01233456789")
        )

    def are_valid_args(args) -> bool:
        return all(is_int(arg) or is_valid_var(arg) for arg in args)

    def is_valid(var: str = "_", op_name: str = "ID", args: Sequence[str] = ()) -> bool:
        return is_valid_var(var) and op_name in OPERATORS and are_valid_args(args)

    def to_int(valid_args: tuple[str, ...]) -> Iterator[int | str]:
        for arg in valid_args:
            try:
                yield int(arg)
            except ValueError:
                yield arg

    def check_signature(op_name: str, num_args: int, is_infix: bool) -> None:
        if is_infix != OPERATORS[op_name].is_infix:
            raise ValueError(
                f'In "{line}":\n{op_name} is a'
                f' {"in" if OPERATORS[op_name].is_infix else "pre"}fix operator.'
            )
        sig = inspect.signature(OPERATORS[op_name].f)
        try:
            sig.bind(*(0,) * num_args)
        except TypeError:
            raise ValueError(
                f'In "{line}":\n{op_name} takes {len(sig.parameters)} arguments.'
            ) from TypeError

    def parse_set_var(var: str, op_name: str, *args: str, is_infix: bool = False):
        check_signature(op_name, len(args), is_infix)
        instruction = Instruction(
            InstructionType.SET_VAR, (var, OPERATORS[op_name], *to_int(args))
        )
        program_buffer.append(instruction)

    def parse_if(op_name: str, *args: str, is_infix: bool = False):
        check_signature(op_name, len(args), is_infix)
        if_else_stack.append(len(program_buffer))
        instruction = Instruction(
            InstructionType.JUMP_IF_NOT,
            (OPERATORS[op_name], *to_int(args), "placeholder"),
        )
        program_buffer.append(instruction)

    def parse_else():
        if_position = if_else_stack.pop()
        instruction_type, (*args, _) = program_buffer[if_position]
        program_buffer[if_position] = Instruction(
            instruction_type, (*args, len(program_buffer) - if_position + 1)
        )
        if_else_stack.append(len(program_buffer))
        program_buffer.append(Instruction(InstructionType.JUMP, ("placeholder",)))

    def parse_end_if():
        if_else_position = if_else_stack.pop()
        instruction_type, (*args, _) = program_buffer[if_else_position]
        program_buffer[if_else_position] = Instruction(
            instruction_type, (*args, len(program_buffer) - if_else_position)
        )
        # we dont need an instruction in the program for this, as it does nothing

    def parse_while(op_name: str, *args: str, is_infix: bool = False):
        check_signature(op_name, len(args), is_infix)
        while_stack.append(len(program_buffer))
        instruction = Instruction(
            InstructionType.JUMP_IF_NOT,
            (OPERATORS[op_name], *to_int(args), "placeholder"),
        )
        program_buffer.append(instruction)

    def parse_end_while():
        while_position = while_stack.pop()
        instruction_type, (*args, _) = program_buffer[while_position]
        program_buffer[while_position] = Instruction(
            instruction_type, (*args, len(program_buffer) - while_position + 1)
        )
        program_buffer.append(
            Instruction(InstructionType.JUMP, (while_position - len(program_buffer),))
        )

    for line in source_code:
        tokens = line.strip().split()
        match tokens:
            case [var, ":=", arg] if is_valid(var, args=(arg,)):
                parse_set_var(var, "ID", arg, is_infix=False)
            case [var, ":=", arg_1, op_name, arg_2] if is_valid(
                var, op_name, (arg_1, arg_2)
            ):
                parse_set_var(var, op_name, arg_1, arg_2, is_infix=True)
            case [var, ":=", op_name, *args] if is_valid(var, op_name, args):
                parse_set_var(var, op_name, *args)
            case ["IF", arg, "THEN"] if is_valid(args=(arg,)):
                parse_if("ID", arg)
            case ["IF", arg_1, op_name, arg_2, "THEN"] if is_valid(
                op_name=op_name, args=(arg_1, arg_2)
            ):
                parse_if(op_name, arg_1, arg_2, is_infix=True)
            case ["IF", op_name, *args, "THEN"] if is_valid(op_name=op_name, args=args):
                parse_if(op_name, *args)
            case ["ELSE"]:
                parse_else()
            case ["END", "IF"]:
                parse_end_if()
            case ["WHILE", arg, "DO"] if is_valid(args=(arg,)):
                parse_while("ID", arg)
            case ["WHILE", arg_1, op_name, arg_2, "DO"] if is_valid(
                op_name=op_name, args=(arg_1, arg_2)
            ):
                parse_while(op_name, arg_1, arg_2, is_infix=True)
            case ["WHILE", op_name, *args, "DO"] if is_valid(
                op_name=op_name, args=args
            ):
                parse_while(op_name, *args)
            case ["END", "WHILE"]:
                parse_end_while()
            case ["INPUT", var] if is_valid(var):
                program_buffer.append(Instruction(InstructionType.INPUT, (var,)))
            case ["OUTPUT", arg] if is_valid(args=(arg,)):
                program_buffer.append(Instruction(InstructionType.OUTPUT, (arg,)))
            case ["//", *_] | []:
                pass  # comments and empty lines
            case _:
                raise ValueError(f'Could not parse line "{line}"')

        if not if_else_stack and not while_stack:
            yield from program_buffer
            program_buffer.clear()

    if if_else_stack:
        raise ValueError(
            f'IF statement "{program_buffer[if_else_stack[-1]]}" was not closed'
        )
    if while_stack:
        raise ValueError(
            f'WHILE statement "{program_buffer[while_stack[-1]]}" was not closed'
        )


def run_program(
    program: Iterable[Instruction], input_function=input, output_function=print
) -> dict[str, int]:
    """Executes instructions provided by an iterable."""

    def get_value(arg) -> int:
        return variables[arg] if isinstance(arg, str) else arg

    def get_input(var: str):
        while True:
            try:
                return int(input_function(f"Please enter the value of {var}: "))
            except ValueError:
                output_function("Invalid input.")

    variables: dict[str, int] = collections.defaultdict(int)
    program_counter = 0
    program_it = iter(program)
    # we store the program in a buffer in order to be able to jump back
    # an improvement would be to only do this when we are in a while statement
    program_buffer = [next(program_it)]

    while True:
        instruction = program_buffer[program_counter]
        match instruction:
            case (InstructionType.SET_VAR, (str(x), Operator(f=op), *args)):
                variables[x] = op(*map(get_value, args))
            case (
                InstructionType.JUMP_IF_NOT,
                (Operator(f=op), *args, int(jump_distance)),
            ):
                if not op(*map(get_value, args)):
                    program_counter += jump_distance - 1
            case (InstructionType.JUMP, (int(jump_distance),)):
                program_counter += jump_distance - 1
            case (InstructionType.INPUT, (str(x),)):
                variables[x] = get_input(x)
            case (InstructionType.OUTPUT, (x,)):
                output_function(str(get_value(x)))
            case _:
                raise ValueError(f"Invalid instruction: {instruction}")

        program_counter += 1
        while program_counter >= len(program_buffer):
            next_instruction = next(program_it, None)
            if next_instruction is None:
                return variables
            program_buffer.append(next_instruction)


def run_interactive_shell(
    source_code: Iterable[str] | None = None,
    input_function=input,
    output_function=print,
):
    output_function(
        "Welcome to the WHILE interactive shell! " 'To exit the shell, type "EXIT"\n'
    )

    def source_code_input():
        if source_code is not None:
            output_function("Loading program...\n")
            yield from source_code
        while True:
            user_input = input_function(">>> ")
            if user_input == "EXIT":
                return
            yield user_input

    run_program(parse_program(source_code_input()), input_function, output_function)


def main():
    parser = argparse.ArgumentParser(
        description="Interpreter and optimizer for the WHILE language."
    )
    parser.add_argument(
        "inputfile",
        nargs="?",
        type=argparse.FileType("r"),
        help="Input file containing the source code to be interpreted",
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Run in interactive shell mode"
    )
    args = parser.parse_args()

    source_code = None
    if args.inputfile:
        source_code = args.inputfile.readlines()
        args.inputfile.close()

    if args.interactive:
        run_interactive_shell(source_code)
    elif source_code:
        run_program(parse_program(source_code))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
