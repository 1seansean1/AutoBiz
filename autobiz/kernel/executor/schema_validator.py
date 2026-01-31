"""SchemaValidator: JSON Schema validation for tool inputs/outputs.

Part of P1-TASK-06: Tool Registry + Schema Validation
Requirements: INV-01, P1-R01, P1-R18
Oracle: Schema (deterministic validation)
"""

from enum import Enum
from typing import Any

import jsonschema
from jsonschema import Draft7Validator


class ValidationErrorCode(str, Enum):
    """Standardized validation error codes."""

    SCHEMA_INVALID = "SCHEMA_INVALID"  # Input/output violates JSON Schema
    SCHEMA_MISSING = "SCHEMA_MISSING"  # Tool schema not defined
    SCHEMA_MALFORMED = "SCHEMA_MALFORMED"  # Schema itself is invalid


class SchemaValidationError(Exception):
    """Raised when schema validation fails.

    Attributes:
        code: Standardized error code
        message: Human-readable error description
        path: JSONPath to the invalid field (if applicable)
        schema_path: Path within the schema that was violated
    """

    def __init__(
        self,
        code: ValidationErrorCode,
        message: str,
        path: str = "",
        schema_path: str = "",
    ) -> None:
        """Initialize validation error.

        Args:
            code: Standardized error code
            message: Human-readable error description
            path: JSONPath to the invalid field
            schema_path: Path within the schema that was violated
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.schema_path = schema_path


class SchemaValidator:
    """Validates data against JSON Schema.

    Enforces INV-01: All tool calls must be schema-valid before execution.
    Uses Draft 7 JSON Schema specification.
    """

    def __init__(self) -> None:
        """Initialize schema validator."""
        pass

    def validate(self, data: Any, schema: dict[str, Any]) -> None:
        """Validate data against JSON Schema.

        Args:
            data: Data to validate (typically dict)
            schema: JSON Schema to validate against

        Raises:
            SchemaValidationError: If validation fails with code SCHEMA_INVALID

        Returns:
            None if validation succeeds
        """
        try:
            # Create validator instance
            validator = Draft7Validator(schema)

            # Validate and collect errors
            errors = list(validator.iter_errors(data))

            if errors:
                # Take the first error for reporting
                first_error = errors[0]

                # Build path from error
                path_parts = [str(p) for p in first_error.path]
                path = ".".join(path_parts) if path_parts else ""

                # Build schema path from error
                schema_path_parts = [str(p) for p in first_error.schema_path]
                schema_path = ".".join(schema_path_parts) if schema_path_parts else ""

                # Create human-readable message
                message = first_error.message

                raise SchemaValidationError(
                    code=ValidationErrorCode.SCHEMA_INVALID,
                    message=message,
                    path=path,
                    schema_path=schema_path,
                )

        except jsonschema.exceptions.SchemaError as e:
            # Schema itself is malformed
            raise SchemaValidationError(
                code=ValidationErrorCode.SCHEMA_MALFORMED,
                message=f"Schema is malformed: {str(e)}",
            )
        except SchemaValidationError:
            # Re-raise our own errors
            raise
        except Exception as e:
            # Catch-all for unexpected errors
            raise SchemaValidationError(
                code=ValidationErrorCode.SCHEMA_INVALID,
                message=f"Validation failed: {str(e)}",
            )
