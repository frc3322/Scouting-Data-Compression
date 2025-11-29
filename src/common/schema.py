"""Schema loading and validation for data encoding/decoding."""

import json
import math
import importlib.util
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..encoder.data_packer import ColumnSchema, SCHEMA as DEFAULT_SCHEMA


class SchemaLoader:
    """Load and validate schemas from JSON or Python files."""

    @staticmethod
    def load_from_json(path: Path) -> List[ColumnSchema]:
        """Load schema from JSON file.

        Args:
            path: Path to JSON schema file.

        Returns:
            List of ColumnSchema objects.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If JSON is invalid or schema structure is incorrect.
        """
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")

        with path.open("r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in schema file: {e}")

        if not isinstance(data, list):
            raise ValueError("Schema JSON must be a list of column definitions")

        schema = []
        for idx, col_data in enumerate(data):
            try:
                col_schema = SchemaLoader._dict_to_column_schema(col_data)
                schema.append(col_schema)
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(
                    f"Invalid column definition at index {idx}: {e}"
                ) from e

        SchemaLoader.validate_schema(schema)
        return schema

    @staticmethod
    def load_from_python(path: Path) -> List[ColumnSchema]:
        """Load schema from Python file.

        Args:
            path: Path to Python schema file.

        Returns:
            List of ColumnSchema objects.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If Python file doesn't define SCHEMA or schema is invalid.
        """
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")

        spec = importlib.util.spec_from_file_location("schema_module", path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load Python schema file: {path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "SCHEMA"):
            raise ValueError(
                f"Python schema file must define SCHEMA variable: {path}"
            )

        schema = module.SCHEMA
        if not isinstance(schema, list):
            raise ValueError("SCHEMA must be a list of ColumnSchema objects")

        for idx, col_schema in enumerate(schema):
            if not isinstance(col_schema, ColumnSchema):
                raise ValueError(
                    f"Schema item at index {idx} is not a ColumnSchema instance"
                )

        SchemaLoader.validate_schema(schema)
        return schema

    @staticmethod
    def load_schema(path: Optional[Path]) -> List[ColumnSchema]:
        """Load schema from file, auto-detecting format from extension.

        Args:
            path: Path to schema file (JSON or Python). If None, returns default schema.

        Returns:
            List of ColumnSchema objects.
        """
        if path is None:
            return SchemaLoader.get_default_schema()

        path = Path(path)
        if path.suffix.lower() == ".json":
            return SchemaLoader.load_from_json(path)
        elif path.suffix.lower() == ".py":
            return SchemaLoader.load_from_python(path)
        else:
            raise ValueError(
                f"Unsupported schema file format: {path.suffix}. "
                "Use .json or .py files"
            )

    @staticmethod
    def get_default_schema() -> List[ColumnSchema]:
        """Get the default hardcoded schema for backward compatibility.

        Returns:
            List of ColumnSchema objects (default schema).
        """
        return DEFAULT_SCHEMA

    @staticmethod
    def validate_schema(schema: List[ColumnSchema]) -> None:
        """Validate schema structure and constraints.

        Args:
            schema: List of ColumnSchema objects to validate.

        Raises:
            ValueError: If schema is invalid.
        """
        if not schema:
            raise ValueError("Schema cannot be empty")

        seen_names = set()
        for s in schema:
            if not isinstance(s, ColumnSchema):
                raise ValueError(f"Schema contains non-ColumnSchema item: {s}")

            if s.name in seen_names:
                raise ValueError(f"Duplicate column name in schema: {s.name}")
            seen_names.add(s.name)

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
            else:
                raise ValueError(f"Unknown column kind: {s.kind}")

    @staticmethod
    def _dict_to_column_schema(data: Dict[str, Any]) -> ColumnSchema:
        """Convert dictionary to ColumnSchema object.

        Args:
            data: Dictionary with column schema data.

        Returns:
            ColumnSchema object.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If data is invalid.
        """
        if "name" not in data:
            raise KeyError("Missing required field: name")
        if "kind" not in data:
            raise KeyError("Missing required field: kind")
        if "bits" not in data:
            raise KeyError("Missing required field: bits")

        name = str(data["name"])
        kind = str(data["kind"])
        bits = int(data["bits"])

        if kind not in ("int", "enum"):
            raise ValueError(f"Invalid kind: {kind}. Must be 'int' or 'enum'")

        int_max = None
        if "int_max" in data and data["int_max"] is not None:
            int_max = int(data["int_max"])

        values = None
        if "values" in data and data["values"] is not None:
            values = [str(v) for v in data["values"]]

        return ColumnSchema(
            name=name,
            kind=kind,
            bits=bits,
            int_max=int_max,
            values=values,
        )

    @staticmethod
    def schema_to_dict(schema: List[ColumnSchema]) -> List[Dict[str, Any]]:
        """Convert schema to dictionary format for JSON serialization.

        Args:
            schema: List of ColumnSchema objects.

        Returns:
            List of dictionaries representing the schema.
        """
        result = []
        for col in schema:
            col_dict: Dict[str, Any] = {
                "name": col.name,
                "kind": col.kind,
                "bits": col.bits,
            }
            if col.int_max is not None:
                col_dict["int_max"] = col.int_max
            if col.values is not None:
                col_dict["values"] = col.values
            result.append(col_dict)
        return result

    @staticmethod
    def save_schema_to_json(schema: List[ColumnSchema], path: Path) -> None:
        """Save schema to JSON file.

        Args:
            schema: List of ColumnSchema objects to save.
            path: Path to output JSON file.
        """
        SchemaLoader.validate_schema(schema)
        schema_dict = SchemaLoader.schema_to_dict(schema)
        with path.open("w") as f:
            json.dump(schema_dict, f, indent=2)
