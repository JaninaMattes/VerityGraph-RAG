from pydantic import BaseModel

"""The schema module provides the building blocks for the application."""


class AppHealthResponse(BaseModel):
    app_name: str
