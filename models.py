from pydantic import BaseModel, Field

class PortSpec(BaseModel):
    name: str = Field(..., description="Port name (lowercase_with_underscores)")
    width: int = Field(default=1, ge=1, description="Bit-width of the port")

class ParameterSpec(BaseModel):
    name: str = Field(..., description="Parameter name")
    default_value: int | str = Field(..., description="Default value")

class HardwareSpec(BaseModel):
    module_name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(..., description="Brief behavioral description")
    is_sequential: bool = Field(..., description="True if requires clk/rst_n. False if combinational.")
    parameters: list[ParameterSpec] = Field(default_factory=list)
    inputs: list[PortSpec] = Field(..., min_length=1)
    outputs: list[PortSpec] = Field(..., min_length=1)
    dse_strategies: list[str] = Field(
        ..., min_length=3, max_length=3,
        description="List exactly 3 distinct microarchitecture implementation strategies."
    )
