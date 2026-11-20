"""Base class of the request bodies."""

from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    """Rejects unknown fields (422), so a client cannot slip in, for example, roles."""

    model_config = ConfigDict(extra="forbid")
