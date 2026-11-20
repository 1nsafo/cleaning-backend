import asyncio
import json
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from pydantic import SecretStr

from app.notifications import NotificationDeliveryError


class TelegramNotificationSender:
    def __init__(self, bot_token: SecretStr, channel_id: str):
        self._bot_token = bot_token
        self._channel_id = channel_id

    async def send(self, message: str) -> None:
        await asyncio.to_thread(self._send, message)

    def _send(self, message: str) -> None:
        token = quote(self._bot_token.get_secret_value(), safe=":")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        body = urlencode({"chat_id": self._channel_id, "text": message}).encode("ascii")

        try:
            with urlopen(url, data=body, timeout=5) as response:
                result = json.load(response)
        except HTTPError as exc:
            exc.close()
            raise NotificationDeliveryError(f"Telegram returned HTTP {exc.code}") from None
        except (OSError, ValueError) as exc:
            raise NotificationDeliveryError(f"Telegram request failed ({type(exc).__name__})") from None

        if not isinstance(result, dict) or result.get("ok") is not True:
            raise NotificationDeliveryError("Telegram did not confirm delivery")
