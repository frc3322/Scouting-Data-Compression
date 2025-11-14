#!/usr/bin/env python3
"""
Custom bit-packing compressor with hard-coded schema.

File format (binary):
  magic: 8 bytes = b"SCOUTPK4"
  num_rows: 4-byte big-endian unsigned int
  data: Zstandard-compressed bit-packed values in row-major order
"""

import csv
import math
import struct
import sys
import zstandard
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional


ColumnKind = Literal["int", "enum"]


@dataclass
class ColumnSchema:
    name: str
    kind: ColumnKind
    bits: int
    int_max: Optional[int] = None  # for ints
    values: Optional[List[str]] = None  # for enums


# HARD-CODED SCHEMA - based on MatchData.csv format with the following fields:
# ScoutName,MatchNumber,TeamNumber,Mobility,AutonL1Attempted,AutonL1Scored,AutonL2Attempted,AutonL2Scored,AutonL3Attempted,AutonL3Scored,AutonL4Attempted,AutonL4Scored,AutonBargeAttempted,AutonBargeScored,AutonProcessorAttempted,AutonProcessorScored,AutonAlgaeRemoved,TeleopL1Attempted,TeleopL1Scored,TeleopL2Attempted,TeleopL2Scored,TeleopL3Attempted,TeleopL3Scored,TeleopL4Attempted,TeleopL4Scored,TeleopBargeAttempted,TeleopBargeScored,TeleopProcessorAttempted,TeleopProcessorScored,TeleopAlgaeRemoved,ClimbSuccessful,Climb,Breakdown,DefenseDescription,Notes
SCHEMA: List[ColumnSchema] = [
    ColumnSchema(
        name="ScoutName", kind="enum", bits=2, values=["Jude", "Dillon", "", ""]
    ),
    ColumnSchema(name="MatchNumber", kind="int", bits=8, int_max=200),
    ColumnSchema(name="TeamNumber", kind="int", bits=14, int_max=16383),
    ColumnSchema(name="Mobility", kind="int", bits=1, int_max=1),
    ColumnSchema(name="AutonL1Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL1Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL2Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL2Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL3Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL3Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL4Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL4Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonBargeAttempted", kind="int", bits=0, int_max=0),
    ColumnSchema(name="AutonBargeScored", kind="int", bits=0, int_max=0),
    ColumnSchema(name="AutonProcessorAttempted", kind="int", bits=0, int_max=0),
    ColumnSchema(name="AutonProcessorScored", kind="int", bits=0, int_max=0),
    ColumnSchema(name="AutonAlgaeRemoved", kind="int", bits=0, int_max=0),
    ColumnSchema(name="TeleopL1Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL1Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL2Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL2Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL3Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL3Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL4Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL4Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopBargeAttempted", kind="int", bits=3, int_max=7),
    ColumnSchema(name="TeleopBargeScored", kind="int", bits=3, int_max=7),
    ColumnSchema(name="TeleopProcessorAttempted", kind="int", bits=3, int_max=7),
    ColumnSchema(name="TeleopProcessorScored", kind="int", bits=3, int_max=7),
    ColumnSchema(name="TeleopAlgaeRemoved", kind="int", bits=3, int_max=7),
    ColumnSchema(name="ClimbSuccessful", kind="int", bits=1, int_max=1),
    ColumnSchema(
        name="Climb", kind="enum", bits=2, values=["None", "Shallow", "Deep", "Park"]
    ),
    ColumnSchema(name="Breakdown", kind="enum", bits=1, values=["False", "True"]),
    ColumnSchema(name="DefenseDescription", kind="enum", bits=0, values=[""]),
    ColumnSchema(name="Notes", kind="enum", bits=1, values=["", "Some note"]),
]


class BitWriter:
    def __init__(self) -> None:
        self._buffer: int = 0
        self._bit_count: int = 0
        self._bytes = bytearray()

    def write(self, value: int, bits: int) -> None:
        if bits == 0:
            return
        if value < 0 or value >= (1 << bits):
            raise ValueError(f"value {value} does not fit in {bits} bits")

        remaining_bits = bits
        while remaining_bits > 0:
            free_bits = 8 - self._bit_count
            to_write = min(remaining_bits, free_bits)
            shift = remaining_bits - to_write
            chunk = (value >> shift) & ((1 << to_write) - 1)
            self._buffer = (self._buffer << to_write) | chunk
            self._bit_count += to_write
            remaining_bits -= to_write

            if self._bit_count == 8:
                self._bytes.append(self._buffer)
                self._buffer = 0
                self._bit_count = 0

    def finish(self) -> bytes:
        if self._bit_count > 0:
            self._buffer <<= 8 - self._bit_count
            self._bytes.append(self._buffer)
        return bytes(self._bytes)


class BitReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._index = 0
        self._buffer = 0
        self._bit_count = 0

    def read(self, bits: int) -> int:
        if bits == 0:
            return 0

        result = 0
        remaining_bits = bits

        while remaining_bits > 0:
            if self._bit_count == 0:
                if self._index >= len(self._data):
                    raise EOFError("Unexpected end of data")
                self._buffer = self._data[self._index]
                self._index += 1
                self._bit_count = 8

            take = min(remaining_bits, self._bit_count)
            shift = self._bit_count - take
            chunk = (self._buffer >> shift) & ((1 << take) - 1)
            self._bit_count -= take
            if self._bit_count > 0:
                self._buffer &= (1 << self._bit_count) - 1
            else:
                self._buffer = 0

            result = (result << take) | chunk
            remaining_bits -= take

        return result


def validate_schema() -> None:
    """Ensure hard-coded schema is consistent."""
    for s in SCHEMA:
        if s.kind == "int":
            if s.int_max is None:
                raise ValueError(f"int column {s.name} missing int_max")
            if s.bits > 0:
                max_representable = (1 << s.bits) - 1
                if s.int_max > max_representable:
                    raise ValueError(
                        f"Column {s.name}: int_max {s.int_max} exceeds "
                        f"{s.bits}-bit capacity ({max_representable})"
                    )
        elif s.kind == "enum":
            if s.values is None:
                raise ValueError(f"enum column {s.name} missing values")
            count = len(s.values)
            if count > 1 and s.bits < math.ceil(math.log2(count)):
                raise ValueError(
                    f"Column {s.name}: bits={s.bits} insufficient for "
                    f"{count} enum values"
                )


def encode(headers: List[str], rows: List[List[str]], out_path: Path) -> None:
    validate_schema()
    
    # Verify CSV headers match schema
    schema_names = [s.name for s in SCHEMA]
    if headers != schema_names:
        raise ValueError(
            f"CSV headers {headers} don't match hard-coded schema {schema_names}"
        )

    num_rows = len(rows)

    # Build enum lookups
    enum_lookups: List[Optional[Dict[str, int]]] = []
    for s in SCHEMA:
        if s.kind == "enum":
            assert s.values is not None
            enum_lookups.append({v: i for i, v in enumerate(s.values)})
        else:
            enum_lookups.append(None)

    # Bit-pack
    writer = BitWriter()
    for row in rows:
        for col_idx, s in enumerate(SCHEMA):
            if s.bits == 0:
                continue

            raw = row[col_idx].strip("\n")
            raw = '' if raw == ' ' else raw
            
            if s.kind == "int":
                value = int(raw)
                if value > s.int_max:
                    raise ValueError(
                        f"Value {value} exceeds int_max {s.int_max} for "
                        f"column {s.name}"
                    )
            else:
                lookup = enum_lookups[col_idx]
                assert lookup is not None
                if raw not in lookup:
                    raise ValueError(
                        f"Value {raw!r} not in enum values for column {s.name}"
                    )
                value = lookup[raw]

            writer.write(value, s.bits)

    data_bytes = writer.finish()

    # Compress
    compressor = zstandard.ZstdCompressor(level=22)
    compressed_data = compressor.compress(data_bytes)

    # Write minimal header
    magic = b"SCOUTPK4"
    with out_path.open("wb") as f:
        f.write(magic)
        f.write(struct.pack(">I", num_rows))
        f.write(compressed_data)

    original_size = sum(len(",".join(r)) + 1 for r in [headers] + rows)
    final_size = 8 + 4 + len(compressed_data)
    ratio = original_size / final_size if final_size > 0 else 0.0

    print(f"Packed to: {out_path}")
    print(f"Original CSV size (approx):    {original_size} bytes")
    print(f"Bit-packed size:               {len(data_bytes)} bytes")
    print(f"Final compressed size:         {final_size} bytes")
    print(f"  (header: 12 bytes, data: {len(compressed_data)} bytes)")
    print(f"Compression ratio:             {ratio:.2f}x")


def decode(in_path: Path) -> (List[str], List[List[str]]):
    validate_schema()
    
    data = in_path.read_bytes()
    
    if len(data) < 12:
        raise ValueError("File too short")
    
    magic = data[:8]
    if magic != b"SCOUTPK4":
        raise ValueError(f"Invalid magic: {magic}")

    (num_rows,) = struct.unpack(">I", data[8:12])
    compressed_data = data[12:]

    # Decompress
    decompressor = zstandard.ZstdDecompressor()
    data_bytes = decompressor.decompress(compressed_data)

    # Decode
    reader = BitReader(data_bytes)
    rows: List[List[str]] = []
    
    for _ in range(num_rows):
        row: List[str] = []
        for s in SCHEMA:
            if s.bits == 0:
                if s.kind == "int":
                    v_str = "0"
                else:
                    assert s.values is not None
                    v_str = s.values[0]
                row.append(v_str)
                continue

            value = reader.read(s.bits)

            if s.kind == "int":
                row.append(str(value))
            else:
                assert s.values is not None
                if value >= len(s.values):
                    raise ValueError(
                        f"Enum index {value} out of range for {s.name}"
                    )
                row.append(s.values[value])
        rows.append(row)

    headers = [s.name for s in SCHEMA]
    return headers, rows


def read_csv(path: Path) -> (List[str], List[List[str]]):
    with path.open("r", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        raise ValueError("CSV is empty")
    return rows[0], rows[1:]


def clean_csv_newlines(path: Path) -> None:
    """Remove newlines from all cells in the CSV and resave the file.

    Args:
        path: Path to the CSV file to clean.
    """
    headers, rows = read_csv(path)

    # Clean newlines from all cells (same logic as encode function)
    cleaned_rows = []
    for row in rows:
        cleaned_row = []
        for cell in row:
            cell = cell.strip("\n").replace("\n", " ").replace("\r", "")
            cell = "" if cell == " " else cell
            cleaned_row.append(cell)
        cleaned_rows.append(cleaned_row)

    # Write back the cleaned data
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(cleaned_rows)


def verify_equal(
    headers1: List[str],
    rows1: List[List[str]],
    headers2: List[str],
    rows2: List[List[str]],
) -> None:
    if headers1 != headers2:
        raise AssertionError("Headers differ")
    if len(rows1) != len(rows2):
        raise AssertionError(f"Row counts differ: {len(rows1)} vs {len(rows2)}")
    for i, (r1, r2) in enumerate(zip(rows1, rows2)):
        if r1 != r2:
            raise AssertionError(f"Row {i} differs:\n  {r1}\n  {r2}")


def main(argv: List[str]) -> None:
    if len(argv) < 2:
        print(f"Usage: {argv[0]} INPUT.csv [OUTPUT.packed]", file=sys.stderr)
        raise SystemExit(1)

    input_csv = Path(argv[1])
    output_packed = (
        Path(argv[2]) if len(argv) >= 3 else input_csv.with_suffix(".packed")
    )

    print(f"Cleaning newlines from CSV: {input_csv}")
    clean_csv_newlines(input_csv)

    print(f"Reading cleaned CSV: {input_csv}")
    headers, rows = read_csv(input_csv)

    print("Encoding...")
    encode(headers, rows, output_packed)

    print("Verifying...")
    decoded_headers, decoded_rows = decode(output_packed)

    verify_equal(headers, rows, decoded_headers, decoded_rows)
    print("✓ Verification passed")


if __name__ == "__main__":
    main(sys.argv)