"""Telegram Bot API client with fail-soft offline support."""

from __future__ import annotations

import json
from typing import Any
import urllib.request
import urllib.parse

from app.config.settings import TelegramConfig
from app.logging.setup import get_logger, log_event
from app.models.enums import SystemEventType
from app.models.time import now_ist


class TelegramClient:
    """Dispatches alerts and messages to configured Telegram chats."""

    def __init__(self, config: TelegramConfig) -> None:
        self.config = config
        self._sent_messages: list[dict[str, Any]] = []
        self._logger = get_logger("notifications.telegram")

    @property
    def sent_messages(self) -> list[dict[str, Any]]:
        return list(self._sent_messages)

    def send_message(
        self,
        text: str,
        *,
        chat_id: str | None = None,
        parse_mode: str = "Markdown",
    ) -> bool:
        """Send a message to Telegram. Fails softly on network/API errors."""
        target_chat = chat_id or self.config.chat_id
        msg_record = {
            "timestamp": now_ist().isoformat(),
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode,
        }
        self._sent_messages.append(msg_record)

        if not self.config.bot_token or not target_chat:
            self._logger.debug("Telegram offline mode (no token/chat): %s", text[:80])
            return True

        # Send via HTTP request
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status == 200:
                    log_event(
                        self._logger,
                        SystemEventType.TELEGRAM_ALERT_SENT.value.upper(),
                        "telegram alert dispatched",
                        chat_id=target_chat,
                    )
                    return True
                return False
        except Exception as exc:  # noqa: BLE001
            log_event(
                self._logger,
                "ERROR",
                "telegram dispatch failed (fail-soft; trading uninterrupted)",
                err=str(exc),
            )
            return False
