from typing import List, Literal

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
    internal_probes: list[str] = Field(
        default_factory=list,
        description="Optional list of internal signals prefixed with probe_ for debugging."
    )


class SystemTask(BaseModel):
    module_name: str = Field(..., description="Name of the RTL module being generated.")
    prompt: str = Field(..., description="Detailed prompt to feed into the HardwareSpec generator.")
    requires_dummy_oracle: bool = Field(
        False,
        description="If True, asks the verification oracle to return a pass-through/dummy model instead of a cycle-accurate simulation."
    )
    component_class: Literal["FSM", "DATAPATH", "MEMORY", "INTERCONNECT", "TOP_LEVEL"] = Field(
        ...,
        description="Component Class used to route verification templates and tooling."
    )


class ArchitecturePlan(BaseModel):
    is_complex: bool = Field(
        ..., description="True if the overall request must be decomposed into multiple sub-modules."
    )
    tasks: List[SystemTask] = Field(
        ..., description="Ordered list of tasks from bottom-level primitives up through the top-level integration."
    )
