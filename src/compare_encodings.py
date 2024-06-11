import z3
import argparse
from transition_relation import OperatorRestrictionGetter, IntEncoding
from typing import Type
import transition_relation
import while_parsing
import smt
import sat


def count_ast_nodes(expr: z3.ExprRef) -> int:
    return 1 + sum(map(count_ast_nodes, expr.children()))


def to_smt2_benchmark(f, status="unknown", name="benchmark", logic=""):
    v = (z3.Ast * 0)()
    return z3.Z3_benchmark_to_smtlib_string(f.ctx_ref(), name, logic, status, "", 0, v, f.as_ast())


def handle_encoding[
    T: IntEncoding
](
    name: str,
    int_encoding: Type[T],
    operater_func: OperatorRestrictionGetter[T],
    while_filename: str,
    smtlib_filename: str | None = None,
):

    with open(while_filename) as file:
        source = file.read().splitlines()
    program = list(while_parsing.parse_program(source))

    print(f"Generating {name} encoding for 1 step.")
    print("=" * 80)
    T = transition_relation.get_transition_relation(program, int_encoding, operater_func)
    one_step = T(0, 1)
    print(one_step)
    print(f"AST nodes: {count_ast_nodes(one_step)}")

    if smtlib_filename:
        with open(smtlib_filename, "w") as smtlib_file:
            smtlib_file.write(to_smt2_benchmark(one_step))


def main():
    parser = argparse.ArgumentParser(description="Generate encodings for a given WHILE program.")
    parser.add_argument("input_file", help="The input file containing the WHILE program.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--smt", action="store_true", help="Generate SMT encoding.")
    group.add_argument("--sat", action="store_true", help="Generate SAT encoding.")
    parser.add_argument(
        "--smtlib", type=str, help="Write the resulting formula in SMT-LIB2 format to a file."
    )

    args = parser.parse_args()
    if args.smt:
        handle_encoding("SMT", smt.Z3Int, smt.get_operator_restriction, args.input_file, args.smtlib)
    if args.sat:
        handle_encoding("SAT", sat.BitVector, sat.get_operator_restriction, args.input_file, args.smtlib)


if __name__ == "__main__":
    main()
