"""Data unpacking and decompression for decoding."""

import csv
import struct
import zstandard
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from ..common.schema import ColumnSchema, SCHEMA as DEFAULT_SCHEMA


class BitReader:
    """Legacy row-major bit reader. No longer used; kept for reference.
    Current implementation uses columnar bit-plane unpacking instead.
    """
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


def unpack_columnar_bitplanes(
    data: bytes, bits: int, num_rows: int, offset: int
) -> Tuple[List[int], int]:
    """Inverse of pack_columnar_bitplanes for a single column.
    
    Args:
        data: Packed byte data.
        bits: Number of bits per value in this column.
        num_rows: Total number of rows.
        offset: Current byte offset in data.
    
    Returns:
        Tuple of (unpacked values list, new offset).
    """
    vals = [0] * num_rows
    bytes_per_plane = (num_rows + 7) // 8
    mv = memoryview(data)
    for _b in range(bits - 1, -1, -1):
        plane = mv[offset : offset + bytes_per_plane]
        offset += bytes_per_plane
        idx = 0
        for byte in plane.tobytes():
            for shift in range(7, -1, -1):
                if idx >= num_rows:
                    break
                bit = (byte >> shift) & 1
                vals[idx] = (vals[idx] << 1) | bit
                idx += 1
    return vals, offset


def decode(
    in_path: Path, schema: Optional[List[ColumnSchema]] = None
) -> tuple[List[str], List[List[str]]]:
    """Decode packed binary format back to CSV data.

    Args:
        in_path: Path to packed file.
        schema: Optional schema to use. If None, uses default SCHEMA.

    Returns:
        Tuple of (headers, rows).
    """
    schema_to_use = schema if schema is not None else DEFAULT_SCHEMA

    data = in_path.read_bytes()

    if len(data) < 12:
        raise ValueError("File too short")

    magic = data[:8]
    if magic != b"SCOUTPK5":
        raise ValueError(f"Invalid magic: {magic}")

    (num_rows,) = struct.unpack(">I", data[8:12])
    compressed_data = data[12:]

    decompressor = zstandard.ZstdDecompressor()
    data_bytes = decompressor.decompress(compressed_data, max_output_size=1024*1024)

    bytes_per_plane = (num_rows + 7) // 8
    expected = sum(s.bits for s in schema_to_use if s.bits > 0) * bytes_per_plane
    if len(data_bytes) != expected:
        raise ValueError(
            f"Corrupt data length: {len(data_bytes)} (expected {expected})"
        )

    col_values: Dict[int, List[int]] = {}
    offset = 0
    for col_idx, s in enumerate(schema_to_use):
        if s.bits == 0:
            continue
        vals, offset = unpack_columnar_bitplanes(
            data_bytes, s.bits, num_rows, offset
        )
        col_values[col_idx] = vals

    rows: List[List[str]] = []
    for r in range(num_rows):
        row: List[str] = []
        for col_idx, s in enumerate(schema_to_use):
            if s.bits == 0:
                if s.kind == "int":
                    v_str = "0"
                else:
                    assert s.values is not None
                    v_str = s.values[0]
                row.append(v_str)
                continue
            value = col_values[col_idx][r]
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

    headers = [s.name for s in schema_to_use]
    return headers, rows


def write_csv(headers: List[str], rows: List[List[str]], out_path: Path) -> None:
    """Write CSV data to file.

    Args:
        headers: CSV column headers.
        rows: CSV data rows.
        out_path: Output path for CSV file.
    """
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

