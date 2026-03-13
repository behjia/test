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
    
    # NEW: The Planner Agent generates custom architectural strategies
    dse_strategies: list[str] = Field(
        ..., 
        min_length=3, max_length=3,
        description="List exactly 3 distinct microarchitecture implementation strategies tailored to this specific design."
    )
    
    # NEW: Tells the pipeline if we need a clock
    is_sequential: bool = Field(
        ..., 
        description="Set to True if the design requires a clock (clk) or state/memory. False if purely combinational."
    )
    
    parameters: list[ParameterSpec] = Field(default_factory=list)
    inputs: list[PortSpec] = Field(..., min_length=1)
    outputs: list[PortSpec] = Field(..., min_length=1)
# """Pydantic models for the EDA pipeline's hardware specification schema."""
# from pydantic import BaseModel, Field
# class PortSpec(BaseModel):
#     """A single I/O port on a hardware module."""
#     name: str = Field(..., description="Port name (lowercase_with_underscores)")
#     width: int = Field(default=1, ge=1, description="Bit-width of the port")
# class ParameterSpec(BaseModel):
#     """A compile-time parameter for a hardware module."""
#     name: str = Field(..., description="Parameter name")
#     default_value: int | str = Field(..., description="Default value for the parameter")
# class HardwareSpec(BaseModel):
#     """Validated architecture specification produced by the LLM.
#     This is the single source of truth that the rest of the pipeline
#     (RTL generation, testbench rendering, verification) consumes.
#     """
#     module_name: str = Field(
#         ...,
#         pattern=r"^[a-z][a-z0-9_]*$",
#         description="Module name in lowercase_with_underscores",
#     )
#     description: str = Field(..., description="Brief behavioral description")
#     parameters: list[ParameterSpec] = Field(
#         default_factory=list,
#         description="Compile-time parameters (may be empty)",
#     )
#     inputs: list[PortSpec] = Field(
#         ..., min_length=1, description="Input ports (at least one required)"
#     )
#     outputs: list[PortSpec] = Field(
#         ..., min_length=1, description="Output ports (at least one required)"
#     )
