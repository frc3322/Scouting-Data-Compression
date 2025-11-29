# Schema Documentation

This guide explains how to create and use custom schemas for encoding and decoding CSV data with the AprilTag encoding system.

## Table of Contents

- [Overview](#overview)
- [Schema Structure](#schema-structure)
- [Column Types](#column-types)
- [Schema Formats](#schema-formats)
- [Bit Width Calculation](#bit-width-calculation)
- [Best Practices](#best-practices)
- [Usage Examples](#usage-examples)
- [Migration Guide](#migration-guide)
- [Troubleshooting](#troubleshooting)

## Overview

A schema defines the structure of your CSV data, specifying:
- Column names and order
- Data types (integer or enumeration)
- Bit widths for efficient compression
- Value constraints and valid options

Schemas can be defined in either JSON or Python format and are used during both encoding and decoding to ensure data integrity and optimal compression.

## Schema Structure

Each column in a schema is defined by a `ColumnSchema` object with the following fields:

### Required Fields

- **`name`** (string): The column name that must match your CSV header
- **`kind`** (string): Either `"int"` for integers or `"enum"` for enumerations
- **`bits`** (integer): Number of bits to allocate for this column (0-64)

### Optional Fields

- **`int_max`** (integer, required for `"int"` kind): Maximum value this column can hold
- **`values`** (list of strings, required for `"enum"` kind): List of possible enum values

### Special Cases

- **`bits=0`**: Columns with 0 bits are not encoded but still appear in the output CSV with default values
  - For `int` columns: defaults to `"0"`
  - For `enum` columns: defaults to the first value in the `values` list

## Column Types

### Integer Columns (`kind: "int"`)

Integer columns store numeric values within a specified range.

**Required fields:**
- `name`: Column name
- `kind`: `"int"`
- `bits`: Number of bits (must be sufficient for `int_max`)
- `int_max`: Maximum value the column can hold

**Example:**
```json
{
  "name": "TeamNumber",
  "kind": "int",
  "bits": 14,
  "int_max": 16383
}
```

**Bit width requirements:**
- `bits` must be large enough to represent values from 0 to `int_max`
- Formula: `bits >= ceil(log2(int_max + 1))`
- Maximum representable value: `(1 << bits) - 1`

### Enumeration Columns (`kind: "enum"`)

Enumeration columns store one of a fixed set of string values.

**Required fields:**
- `name`: Column name
- `kind`: `"enum"`
- `bits`: Number of bits (must be sufficient for number of values)
- `values`: List of possible string values

**Example:**
```json
{
  "name": "Climb",
  "kind": "enum",
  "bits": 2,
  "values": ["None", "Shallow", "Deep", "Park"]
}
```

**Bit width requirements:**
- `bits` must be sufficient to represent all values
- Formula: `bits >= ceil(log2(len(values)))`
- Values are indexed starting from 0
- Empty strings are valid enum values

## Schema Formats

### JSON Format

JSON schemas are simple, portable, and easy to edit. Save with `.json` extension.

**Example (`schema.json`):**
```json
[
  {
    "name": "TeamNumber",
    "kind": "int",
    "bits": 10,
    "int_max": 9999
  },
  {
    "name": "Result",
    "kind": "enum",
    "bits": 2,
    "values": ["Win", "Loss", "Tie"]
  }
]
```

**Advantages:**
- Easy to read and edit
- Portable across systems
- Can be generated programmatically
- No Python dependencies

### Python Format

Python schemas allow for comments, logic, and dynamic generation. Save with `.py` extension.

**Example (`schema.py`):**
```python
from src.common.schema import ColumnSchema

SCHEMA = [
    ColumnSchema(name="TeamNumber", kind="int", bits=10, int_max=9999),
    ColumnSchema(
        name="Result",
        kind="enum",
        bits=2,
        values=["Win", "Loss", "Tie"]
    ),
]
```

**Advantages:**
- Can include comments and documentation
- Supports dynamic generation
- Can use Python logic for complex schemas
- Type checking with IDE support

**Requirements:**
- Must define a variable named `SCHEMA`
- Must be a list of `ColumnSchema` objects
- Can import from `src.encoder.data_packer`

## Bit Width Calculation

### Calculating Bits for Integers

For integer columns, calculate the minimum bits needed:

```python
import math

int_max = 200
bits_needed = math.ceil(math.log2(int_max + 1))
# Result: 8 bits (can represent 0-255)
```

**Common ranges:**
- 0-1: 1 bit
- 0-3: 2 bits
- 0-7: 3 bits
- 0-15: 4 bits
- 0-31: 5 bits
- 0-63: 6 bits
- 0-127: 7 bits
- 0-255: 8 bits
- 0-511: 9 bits
- 0-1023: 10 bits
- 0-16383: 14 bits

### Calculating Bits for Enums

For enumeration columns, calculate based on number of values:

```python
import math

values = ["None", "Shallow", "Deep", "Park"]
bits_needed = math.ceil(math.log2(len(values)))
# Result: 2 bits (can represent 4 values: 0-3)
```

**Common counts:**
- 1 value: 0 bits (or 1 bit minimum)
- 2 values: 1 bit
- 3-4 values: 2 bits
- 5-8 values: 3 bits
- 9-16 values: 4 bits

### Optimization Tips

1. **Use the minimum bits needed**: More bits = larger file size
2. **Round up for future growth**: If you might need 100 values, use 7 bits (supports 0-127) instead of 6 (supports 0-63)
3. **Consider padding**: Powers of 2 are more efficient (1, 2, 4, 8, 16 bits)
4. **Zero-bit columns**: Use `bits=0` for columns you don't need to encode but want in output

## Best Practices

### 1. Column Order

- Order columns by frequency of use (most common first)
- Group related columns together
- Place zero-bit columns at the end

### 2. Naming Conventions

- Use descriptive, consistent names
- Match CSV headers exactly (case-sensitive)
- Avoid special characters

### 3. Value Constraints

- Set `int_max` to the actual maximum value you'll encounter
- Include all possible enum values, even if rarely used
- Use empty string `""` as first enum value for "no value" cases

### 4. Bit Allocation

- Start with minimum bits needed
- Add 1-2 bits buffer for future growth if needed
- Use zero bits for columns you don't need to encode
- Test with real data to verify bit widths

### 5. Schema Validation

Always validate your schema before use:

```python
from src.common.schema import SchemaLoader

schema = SchemaLoader.load_from_json("my_schema.json")
SchemaLoader.validate_schema(schema)
```

## Usage Examples

### Command-Line Usage

**Encoding with custom schema:**
```bash
python encode_csv_to_image.py data.csv --schema examples/schema.json
```

**Decoding with custom schema:**
```bash
python decode_image_to_csv.py encoded.png --schema examples/schema.json
```

### Programmatic Usage

**Encoding:**
```python
from pathlib import Path
from src.common.schema import SchemaLoader
from encode_csv_to_image import encode_csv_to_image

schema_path = Path("examples/schema.json")
encode_csv_to_image(
    csv_path="data.csv",
    schema_path=schema_path
)
```

**Decoding:**
```python
from pathlib import Path
from src.common.schema import SchemaLoader
from decode_image_to_csv import decode_image_to_csv

schema_path = Path("examples/schema.json")
decode_image_to_csv(
    image_path="encoded.png",
    schema_path=schema_path
)
```

### Loading Schema Directly

```python
from pathlib import Path
from src.common.schema import SchemaLoader

schema = SchemaLoader.load_schema(Path("schema.json"))
schema = SchemaLoader.load_schema(Path("schema.py"))
schema = SchemaLoader.get_default_schema()
```

## Common Patterns for FRC Scouting Data

### Match Data Schema

```json
[
  {
    "name": "MatchNumber",
    "kind": "int",
    "bits": 8,
    "int_max": 200
  },
  {
    "name": "TeamNumber",
    "kind": "int",
    "bits": 14,
    "int_max": 16383
  },
  {
    "name": "Alliance",
    "kind": "enum",
    "bits": 1,
    "values": ["Red", "Blue"]
  }
]
```

### Scoring Data Schema

```json
[
  {
    "name": "AutonScore",
    "kind": "int",
    "bits": 6,
    "int_max": 63
  },
  {
    "name": "TeleopScore",
    "kind": "int",
    "bits": 8,
    "int_max": 255
  },
  {
    "name": "EndgameStatus",
    "kind": "enum",
    "bits": 2,
    "values": ["None", "Parked", "Climbed"]
  }
]
```

### Boolean Fields

Use enum with 1 bit:
```json
{
  "name": "Mobility",
  "kind": "enum",
  "bits": 1,
  "values": ["False", "True"]
}
```

Or use int with 1 bit:
```json
{
  "name": "Mobility",
  "kind": "int",
  "bits": 1,
  "int_max": 1
}
```

### Flexible Column Matching

The system supports flexible schema usage:
- **Extra CSV columns**: Columns in CSV but not in schema are ignored during encoding
- **Missing CSV columns**: Columns in schema but not in CSV will cause an error
- **Column order**: CSV columns can be in any order; schema defines the output order

## Troubleshooting

### Common Errors

**"CSV missing required columns from schema"**
- **Cause**: CSV doesn't have all columns defined in schema
- **Solution**: Add missing columns to CSV or remove from schema

**"Value X exceeds int_max Y for column Z"**
- **Cause**: CSV contains value larger than `int_max`
- **Solution**: Increase `int_max` or reduce `bits` if appropriate

**"Value 'X' not in enum values for column Y"**
- **Cause**: CSV contains enum value not in schema
- **Solution**: Add the value to the `values` list in schema

**"bits=X insufficient for Y enum values"**
- **Cause**: Not enough bits to represent all enum values
- **Solution**: Increase `bits` to at least `ceil(log2(len(values)))`

**"int_max X exceeds Y-bit capacity"**
- **Cause**: `int_max` is too large for the number of bits
- **Solution**: Increase `bits` or decrease `int_max`

**"Invalid magic: b'...'"**
- **Cause**: Wrong schema used for decoding, or corrupted file
- **Solution**: Use the same schema that was used for encoding

**"Corrupt data length"**
- **Cause**: Schema mismatch between encoding and decoding
- **Solution**: Use the exact same schema file for both encoding and decoding

### Validation Checklist

Before using a schema:

- [ ] All required fields present for each column
- [ ] `int_max` specified for all `int` columns
- [ ] `values` specified for all `enum` columns
- [ ] Bit widths sufficient for `int_max` and enum counts
- [ ] No duplicate column names
- [ ] Column names match CSV headers exactly
- [ ] Schema tested with sample data
- [ ] Same schema used for encoding and decoding

### Debugging Tips

1. **Validate schema first:**
   ```python
   from src.common.schema import SchemaLoader
   SchemaLoader.validate_schema(schema)
   ```

2. **Check CSV headers:**
   ```python
   from src.encoder.data_packer import read_csv
   headers, rows = read_csv(Path("data.csv"))
   print(headers)
   ```

3. **Test with minimal schema:**
   Start with a small schema and gradually add columns

4. **Compare with default:**
   Use the default schema as a reference for structure

5. **Verify bit calculations:**
   Use the formulas in this guide to verify bit widths

## Additional Resources

- See `examples/schema.json` for a complete FRC scouting schema
- See `examples/schema.py` for Python format example
- See `examples/minimal_schema.json` for a simple learning example
- Check `src/encoder/data_packer.py` for the default schema implementation

