# src/infrastructure/message_broker/provider.py
from typing import Protocol


class EventHandler(Protocol):
    """Defines an abstract base class for all event handlers.
    This enforces that each handler implements its own handle method."""

    async def handle(self, record: dict) -> None:
        raise NotImplementedError("Subclasses must implement handle method")
