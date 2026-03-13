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
    
    dse_strategies: list[str] = Field(
        ..., min_length=3, max_length=3,
        description="List exactly 3 distinct microarchitecture implementation strategies."
    )
    is_sequential: bool = Field(..., description="True if requires clk/rst_n. False if combinational.")
    
    # NEW: The Python Golden Reference Model
    golden_model_python: str = Field(
        ..., 
        description="A pure Python function named 'golden_model(inputs_dict)' that mathematically calculates the expected output. Must handle bit-masking for overflows."
    )
    
    parameters: list[ParameterSpec] = Field(default_factory=list)
    inputs: list[PortSpec] = Field(..., min_length=1)
    outputs: list[PortSpec] = Field(..., min_length=1)
# from pydantic import BaseModel, Field

# class PortSpec(BaseModel):
#     name: str = Field(..., description="Port name (lowercase_with_underscores)")
#     width: int = Field(default=1, ge=1, description="Bit-width of the port")

# class ParameterSpec(BaseModel):
#     name: str = Field(..., description="Parameter name")
#     default_value: int | str = Field(..., description="Default value")

# class HardwareSpec(BaseModel):
#     module_name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
#     description: str = Field(..., description="Brief behavioral description")
    
#     # NEW: The Planner Agent generates custom architectural strategies
#     dse_strategies: list[str] = Field(
#         ..., 
#         min_length=3, max_length=3,
#         description="List exactly 3 distinct microarchitecture implementation strategies tailored to this specific design."
#     )
    
#     # NEW: Tells the pipeline if we need a clock
#     is_sequential: bool = Field(
#         ..., 
#         description="Set to True if the design requires a clock (clk) or state/memory. False if purely combinational."
#     )
    
#     parameters: list[ParameterSpec] = Field(default_factory=list)
#     inputs: list[PortSpec] = Field(..., min_length=1)
#     outputs: list[PortSpec] = Field(..., min_length=1)