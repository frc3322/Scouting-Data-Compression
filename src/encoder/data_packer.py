"""Data packing and compression for encoding."""

import csv
import math
import struct
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
    int_max: Optional[int] = None
    values: Optional[List[str]] = None


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
    """Legacy row-major bit writer. No longer used; kept for reference.
    Current implementation uses columnar bit-plane packing instead.
    """
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


def pack_columnar_bitplanes(
    values_by_col: List[List[int]],
    bits_by_col: List[int],
) -> bytes:
    """Pack columns as bit-planes (MSB->LSB) for better compressibility.
    
    Args:
        values_by_col: List of columns, each containing integer values for all rows.
        bits_by_col: Number of bits for each column.
        num_rows: Total number of rows.
    
    Returns:
        Packed bytes with columnar bit-plane layout.
    """
    out = bytearray()
    for vals, bits in zip(values_by_col, bits_by_col):
        if bits == 0:
            continue
        for b in range(bits - 1, -1, -1):
            acc = 0
            nbits = 0
            for v in vals:
                acc = (acc << 1) | ((v >> b) & 1)
                nbits += 1
                if nbits == 8:
                    out.append(acc)
                    acc = 0
                    nbits = 0
            if nbits:
                out.append(acc << (8 - nbits))
    return bytes(out)


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


def read_csv(path: Path) -> tuple[List[str], List[List[str]]]:
    """Read CSV file and return headers and rows.

    Args:
        path: Path to CSV file.

    Returns:
        Tuple of (headers, rows).
    """
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

    cleaned_rows = []
    for row in rows:
        cleaned_row = []
        for cell in row:
            cell = cell.strip("\n").replace("\n", " ").replace("\r", "")
            cell = "" if cell == " " else cell
            cleaned_row.append(cell)
        cleaned_rows.append(cleaned_row)

    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(cleaned_rows)


def encode(headers: List[str], rows: List[List[str]], out_path: Path) -> None:
    """Encode CSV data into packed binary format.

    Args:
        headers: CSV column headers.
        rows: CSV data rows.
        out_path: Output path for packed file.
    """
    validate_schema()

    schema_names = [s.name for s in SCHEMA]
    if headers != schema_names:
        raise ValueError(
            f"CSV headers {headers} don't match hard-coded schema {schema_names}"
        )

    num_rows = len(rows)

    enum_lookups: List[Optional[Dict[str, int]]] = []
    for s in SCHEMA:
        if s.kind == "enum":
            assert s.values is not None
            enum_lookups.append({v: i for i, v in enumerate(s.values)})
        else:
            enum_lookups.append(None)

    values_by_col: List[List[int]] = []
    bits_by_col: List[int] = []
    for col_idx, s in enumerate(SCHEMA):
        if s.bits == 0:
            continue
        col_vals: List[int] = []
        for row in rows:
            raw = row[col_idx].strip("\n")
            raw = "" if raw == " " else raw
            if s.kind == "int":
                value = int(raw)
                assert s.int_max is not None
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
            col_vals.append(value)
        values_by_col.append(col_vals)
        bits_by_col.append(s.bits)

    data_bytes = pack_columnar_bitplanes(values_by_col, bits_by_col)

    compressor = zstandard.ZstdCompressor(
        level=22,
        write_content_size=False,
        write_checksum=False,
        write_dict_id=False,
        threads=-1,
    )
    compressed_data = compressor.compress(data_bytes)

    magic = b"SCOUTPK5"
    with out_path.open("wb") as f:
        f.write(magic)
        f.write(struct.pack(">I", num_rows))
        f.write(compressed_data)

    original_size = sum(len(",".join(r)) + 1 for r in [headers] + rows)
    final_size = 8 + 4 + len(compressed_data)
    ratio = original_size / final_size if final_size > 0 else 0.0

    print(f"Original CSV size (approx):    {original_size} bytes")
    print(f"Final compressed size:         {final_size} bytes")
    print(f"Compression ratio:             {ratio:.2f}x")

