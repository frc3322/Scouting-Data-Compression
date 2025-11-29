"""Data packing and compression for encoding."""

import csv
import struct
import zstandard
from pathlib import Path
from typing import Dict, List, Optional

from ..common.schema import ColumnSchema, SCHEMA, SchemaLoader


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


def encode(
    headers: List[str],
    rows: List[List[str]],
    out_path: Path,
    schema: Optional[List[ColumnSchema]] = None,
) -> None:
    """Encode CSV data into packed binary format.

    Args:
        headers: CSV column headers.
        rows: CSV data rows.
        out_path: Output path for packed file.
        schema: Optional schema to use. If None, uses default SCHEMA.
    """
    schema_to_use = schema if schema is not None else SCHEMA
    SchemaLoader.validate_schema(schema_to_use)

    schema_names = [s.name for s in schema_to_use]

    header_to_csv_idx: Dict[str, int] = {
        name: idx for idx, name in enumerate(headers)
    }

    missing_columns = [name for name in schema_names if name not in header_to_csv_idx]
    if missing_columns:
        raise ValueError(
            f"CSV missing required columns from schema: {missing_columns}"
        )

    num_rows = len(rows)

    enum_lookups: List[Optional[Dict[str, int]]] = []
    for s in schema_to_use:
        if s.kind == "enum":
            assert s.values is not None
            enum_lookups.append({v: i for i, v in enumerate(s.values)})
        else:
            enum_lookups.append(None)

    values_by_col: List[List[int]] = []
    bits_by_col: List[int] = []
    for col_idx, s in enumerate(schema_to_use):
        if s.bits == 0:
            continue
        col_vals: List[int] = []
        csv_col_idx = header_to_csv_idx[s.name]
        for row in rows:
            if csv_col_idx >= len(row):
                raise ValueError(
                    f"Row has fewer columns than expected. "
                    f"Column {s.name} (index {csv_col_idx}) not found in row"
                )
            raw = row[csv_col_idx].strip("\n")
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

