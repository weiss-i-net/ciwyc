import z3
import dataclasses
import typing

from typing import ClassVar, Any

import transition_relation
from util import Z3BoolExpression


# We could use z3s BitVec instead of implementing our own but that would miss the point of
# the project, as we want to investigate how difficult it is to do an encoding on our own.
# Also z3 BitVecs might not use bit blasting
@dataclasses.dataclass(slots=True, frozen=True)
class BitVector(transition_relation.IntEncoding):
    _num_bits: ClassVar[int] = 16  # This shouldnt really be a constant and could be done
    # better with a class factory, but it's hard to make that work with type checking and
    # the IntEncoding protocol

    _bits: tuple[z3.BoolRef, ...]

    def __eq__(self, other: "BitVector") -> Z3BoolExpression:
        return z3.And([self_bit == other_bit for self_bit, other_bit in zip(self._bits, other._bits)])

    def __ne__(self, other: "BitVector") -> Z3BoolExpression:
        return z3.Not(self == other)

    def to_bool(self):
        return z3.Or(self._bits)

    @classmethod
    def from_bool(cls, z3bool: z3.BoolRef):
        return cls((z3bool,) + tuple(z3.BoolVal(False) for _ in range(cls._num_bits - 1)))

    @classmethod
    def create_variable(cls, name: str) -> "BitVector":
        return cls(tuple(z3.Bool(f"{name}_b{i}") for i in range(cls._num_bits)))

    @classmethod
    def create_unique_variable(cls) -> "BitVector":
        return cls(tuple(typing.cast(z3.BoolRef, z3.FreshConst(z3.BoolSort())) for _ in range(cls._num_bits)))

    @classmethod
    def create_literal(cls, value: int) -> "BitVector":
        bits = bin(value)[2:].zfill(cls._num_bits)[::-1]
        return cls(tuple(z3.BoolVal(bit == "1") for bit in bits))


def bitvector_add(lhs: "BitVector", rhs: "BitVector", result: "BitVector") -> Z3BoolExpression:
    carry_bits = [z3.BoolVal(False)] + [z3.FreshConst(z3.BoolSort()) for _ in range(lhs._num_bits - 1)]
    restrictions = []
    for i, carry_bit in enumerate(carry_bits):
        if i == 0:
            continue
        restrictions.append(
            carry_bit
            == z3.Or(
                z3.And(lhs._bits[i - 1], rhs._bits[i - 1]),
                z3.And(lhs._bits[i - 1], carry_bits[i - 1]),
                z3.And(rhs._bits[i - 1], carry_bits[i - 1]),
            )
        )

    for lhs_bit, rhs_bit, carry_bit, result_bit in zip(lhs._bits, rhs._bits, carry_bits, result._bits):
        restrictions.append(result_bit == lhs_bit ^ rhs_bit ^ carry_bit)

    return z3.And(restrictions)


def bitvector_less(lhs: BitVector, rhs: BitVector) -> Z3BoolExpression:
    options = []
    for i in range(BitVector._num_bits):
        current_bit_smaller = z3.And(z3.Not(lhs._bits[i]), rhs._bits[i])
        larger_bits_equal = z3.And(
            [lhs_bit == rhs_bit for lhs_bit, rhs_bit in zip(lhs._bits[i + 1 :], rhs._bits[i + 1 :])]
        )
        options.append(z3.And(current_bit_smaller, larger_bits_equal))
    return z3.Or(options)


SAT_BITVEC_OPERATORS: dict[str, Any] = {"+": bitvector_add, "ID": lambda self, other: self == other}

SAT_BOOL_OPERATORS: dict[str, Any] = {
    "TRUE": lambda: BitVector.from_bool(z3.BoolVal(True)),
    "False": lambda: BitVector.from_bool(z3.BoolVal(False)),
    "<": bitvector_less,
    "<=": lambda a, b: z3.Or(bitvector_less(a, b), a == b),
    "==": BitVector.__eq__,
    ">=": lambda a, b: z3.Not(bitvector_less(a, b)),
    ">": lambda a, b: z3.And(z3.Not(bitvector_less(a, b)), a != b),
}


def get_operator_restriction(
    op_name: str, *args: BitVector, other: None | BitVector = None
) -> Z3BoolExpression:
    if (op := SAT_BITVEC_OPERATORS.get(op_name)) is not None:
        if other is None:
            other = BitVector.create_unique_variable()
            return z3.And(op(*args, other), other.to_bool())
        else:
            return op(*args, other)

    if (op := SAT_BOOL_OPERATORS.get(op_name)) is not None:
        if other is None:
            return op(*args)
        else:
            return BitVector.from_bool(op(*args)) == other

    raise ValueError(f"{op_name} is not supported for SAT encoding")
