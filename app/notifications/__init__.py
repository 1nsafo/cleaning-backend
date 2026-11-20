import logging
from collections.abc import Sequence
from typing import Protocol


logger = logging.getLogger(__name__)


class NotificationSender(Protocol):
    async def send(self, message: str) -> None: ...


class NotificationDeliveryError(Exception):
    """A delivery failure with a message safe to write to logs."""


class NotificationDispatcher:
    def __init__(self, senders: Sequence[NotificationSender]):
        self._senders = tuple(senders)

    async def send(self, message: str) -> None:
        for sender in self._senders:
            try:
                await sender.send(message)
            except NotificationDeliveryError as exc:
                logger.warning("Notification delivery via %s failed: %s", type(sender).__name__, exc)
            except Exception as exc:
                logger.error("Notification delivery via %s failed: %s", type(sender).__name__, type(exc).__name__)
