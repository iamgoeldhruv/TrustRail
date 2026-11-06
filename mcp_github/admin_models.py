from pydantic import BaseModel, ConfigDict

from mcp_github.fault_injection import FaultMode


class FaultUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: FaultMode


class FaultUpdateResponse(BaseModel):
    mode: FaultMode
    updated: bool