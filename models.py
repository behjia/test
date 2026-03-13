"""Pydantic models for the EDA pipeline's hardware specification schema."""
from pydantic import BaseModel, Field
class PortSpec(BaseModel):
    """A single I/O port on a hardware module."""
    name: str = Field(..., description="Port name (lowercase_with_underscores)")
    width: int = Field(default=1, ge=1, description="Bit-width of the port")
class ParameterSpec(BaseModel):
    """A compile-time parameter for a hardware module."""
    name: str = Field(..., description="Parameter name")
    default_value: int | str = Field(..., description="Default value for the parameter")
class HardwareSpec(BaseModel):
    """Validated architecture specification produced by the LLM.
    This is the single source of truth that the rest of the pipeline
    (RTL generation, testbench rendering, verification) consumes.
    """
    module_name: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Module name in lowercase_with_underscores",
    )
    description: str = Field(..., description="Brief behavioral description")
    parameters: list[ParameterSpec] = Field(
        default_factory=list,
        description="Compile-time parameters (may be empty)",
    )
    inputs: list[PortSpec] = Field(
        ..., min_length=1, description="Input ports (at least one required)"
    )
    outputs: list[PortSpec] = Field(
        ..., min_length=1, description="Output ports (at least one required)"
    )
