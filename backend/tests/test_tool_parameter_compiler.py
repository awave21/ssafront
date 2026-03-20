from __future__ import annotations

from app.schemas.tool_parameter import ToolParameterCreate
from app.services.tool_parameter_compiler import compile_parameters_to_schema


def test_compile_parameters_to_schema_basic_types() -> None:
    schema = compile_parameters_to_schema(
        [
            ToolParameterCreate(
                name="service_name",
                type="text",
                instruction="Название услуги",
                required=True,
                is_optional=False,
                order_index=1,
            ),
            ToolParameterCreate(
                name="price",
                type="number",
                instruction="Цена услуги",
                required=False,
                is_optional=True,
                default_value=0,
                order_index=2,
            ),
            ToolParameterCreate(
                name="is_vip",
                type="boolean",
                instruction="VIP клиент",
                required=False,
                is_optional=True,
                order_index=3,
            ),
        ]
    )

    assert schema["type"] == "object"
    assert schema["properties"]["service_name"]["type"] == "string"
    assert schema["properties"]["price"]["type"] == "number"
    assert schema["properties"]["is_vip"]["type"] == "boolean"
    assert "service_name" in schema["required"]
    assert "price" not in schema["required"]

