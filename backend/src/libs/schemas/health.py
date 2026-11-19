"""Response schemas of the info and health endpoints."""

from typing import Literal

from pydantic import BaseModel


class AppHealthResponse(BaseModel):
    app_name: str


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["ok", "failed"]]
