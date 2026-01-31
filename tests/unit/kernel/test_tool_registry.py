"""P1-T01, P1-T02, P1-T28: Tool Registry + Schema Validation Tests

Test Coverage:
- P1-T01: Valid tool calls accepted
- P1-T02: Invalid tool calls rejected with SCHEMA_INVALID before execution
- P1-T28: Unknown tools return error
- P1-T01-NEG-*: Negative tests for schema validation

Requirements: INV-01, P1-R01, P1-R18
Oracle: Schema (deterministic validation)
"""


import pytest

from autobiz.kernel.executor.schema_validator import (
    SchemaValidationError,
    SchemaValidator,
    ValidationErrorCode,
)
from autobiz.kernel.executor.tool_contract import ToolContract
from autobiz.kernel.executor.tool_registry import ToolNotFoundError, ToolRegistry


@pytest.mark.unit
@pytest.mark.P0
@pytest.mark.oracle_schema
class TestToolRegistry:
    """P1-T28: Tool registration and lookup."""

    def test_register_and_lookup_tool(self) -> None:
        """Valid tool can be registered and looked up."""
        registry = ToolRegistry()

        tool = ToolContract(
            name="test_tool",
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {"arg1": {"type": "string"}},
                "required": ["arg1"],
            },
            output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            side_effect_level="READ",
            timeout_seconds=30,
        )

        registry.register(tool)
        retrieved = registry.lookup("test_tool", "1.0.0")

        assert retrieved.name == "test_tool"
        assert retrieved.version == "1.0.0"

    def test_lookup_unknown_tool_raises_error(self) -> None:
        """P1-T28: Unknown tool returns ToolNotFoundError."""
        registry = ToolRegistry()

        with pytest.raises(ToolNotFoundError) as exc_info:
            registry.lookup("nonexistent_tool", "1.0.0")

        assert "nonexistent_tool" in str(exc_info.value)
        assert "1.0.0" in str(exc_info.value)

    def test_lookup_unknown_version_raises_error(self) -> None:
        """Unknown version of registered tool returns ToolNotFoundError."""
        registry = ToolRegistry()

        tool = ToolContract(
            name="test_tool",
            version="1.0.0",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            side_effect_level="READ",
            timeout_seconds=30,
        )
        registry.register(tool)

        with pytest.raises(ToolNotFoundError) as exc_info:
            registry.lookup("test_tool", "2.0.0")

        assert "test_tool" in str(exc_info.value)
        assert "2.0.0" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.P0
@pytest.mark.oracle_schema
class TestSchemaValidator:
    """P1-T01, P1-T02, P1-T01-NEG-*: Schema validation tests."""

    def test_valid_input_accepted(self) -> None:
        """P1-T01: Valid tool call input passes validation."""
        validator = SchemaValidator()

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
        }

        data = {"name": "John", "age": 30}

        # Should not raise
        validator.validate(data, schema)

    def test_invalid_input_rejected_with_schema_invalid(self) -> None:
        """P1-T02: Invalid tool call rejected before execution with SCHEMA_INVALID."""
        validator = SchemaValidator()

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }

        data = {"age": 30}  # Missing required field 'name'

        with pytest.raises(SchemaValidationError) as exc_info:
            validator.validate(data, schema)

        error = exc_info.value
        assert error.code == ValidationErrorCode.SCHEMA_INVALID
        assert "name" in error.message.lower()

    def test_p1_t01_neg_missing_required_field(self) -> None:
        """P1-T01-NEG-01: Missing required field rejected."""
        validator = SchemaValidator()

        schema = {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        }

        data = {}  # Missing order_id

        with pytest.raises(SchemaValidationError) as exc_info:
            validator.validate(data, schema)

        assert exc_info.value.code == ValidationErrorCode.SCHEMA_INVALID

    def test_p1_t01_neg_wrong_type(self) -> None:
        """P1-T01-NEG-02: Wrong data type rejected."""
        validator = SchemaValidator()

        schema = {
            "type": "object",
            "properties": {"amount": {"type": "number"}},
            "required": ["amount"],
        }

        data = {"amount": "not_a_number"}  # Wrong type

        with pytest.raises(SchemaValidationError) as exc_info:
            validator.validate(data, schema)

        assert exc_info.value.code == ValidationErrorCode.SCHEMA_INVALID

    def test_p1_t01_neg_extra_fields_rejected(self) -> None:
        """P1-T01-NEG-03: Unknown fields rejected (strict validation)."""
        validator = SchemaValidator()

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,  # Strict: no extra fields
        }

        data = {"name": "John", "extra_field": "not_allowed"}

        with pytest.raises(SchemaValidationError) as exc_info:
            validator.validate(data, schema)

        assert exc_info.value.code == ValidationErrorCode.SCHEMA_INVALID
        assert (
            "extra_field" in exc_info.value.message.lower()
            or "additional" in exc_info.value.message.lower()
        )

    def test_p1_t01_neg_nested_validation_failure(self) -> None:
        """P1-T01-NEG-04: Nested object validation failures detected."""
        validator = SchemaValidator()

        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            },
            "required": ["user"],
        }

        data = {"user": {}}  # Missing nested required field

        with pytest.raises(SchemaValidationError) as exc_info:
            validator.validate(data, schema)

        assert exc_info.value.code == ValidationErrorCode.SCHEMA_INVALID


@pytest.mark.unit
@pytest.mark.P0
@pytest.mark.oracle_schema
class TestToolRegistryWithValidation:
    """Integration of ToolRegistry + SchemaValidator."""

    def test_validate_tool_input_before_execution(self) -> None:
        """Full flow: lookup tool + validate input."""
        registry = ToolRegistry()
        validator = SchemaValidator()

        tool = ToolContract(
            name="create_order",
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {"product_id": {"type": "string"}, "quantity": {"type": "integer"}},
                "required": ["product_id", "quantity"],
            },
            output_schema={"type": "object"},
            side_effect_level="HARD_WRITE",
            timeout_seconds=60,
        )

        registry.register(tool)
        retrieved_tool = registry.lookup("create_order", "1.0.0")

        # Valid input
        valid_input = {"product_id": "prod_123", "quantity": 2}
        validator.validate(valid_input, retrieved_tool.input_schema)  # Should not raise

        # Invalid input
        invalid_input = {"product_id": "prod_123"}  # Missing quantity
        with pytest.raises(SchemaValidationError):
            validator.validate(invalid_input, retrieved_tool.input_schema)
