from typing import Any, Protocol


class EventHandler(Protocol):
    """Handles one event record. Must be idempotent: a record can be delivered twice."""

    async def handle(self, record: dict[str, Any]) -> None:
        """Process the record. Raise to make the consumer retry the message."""
        raise NotImplementedError
