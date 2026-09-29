from typing import Any, Protocol


class EventHandler(Protocol):
    """Defines an abstract base class for all event handlers.
    This enforces that each handler implements its own handle method."""

    async def handle(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError("Subclasses must implement handle method")
