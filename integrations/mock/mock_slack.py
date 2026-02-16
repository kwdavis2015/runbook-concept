"""Mock Slack provider — implements CommunicationProvider with scenario fixtures."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.config import Settings
from core.models import Channel, Message
from integrations.base import CommunicationProvider
from integrations.mock.base import MockBase


class MockSlack(CommunicationProvider, MockBase):
    provider_key = "slack"

    def __init__(self, settings: Settings) -> None:
        MockBase.__init__(self, settings)
        self._sent_messages: list[Message] = []
        self._created_channels: list[Channel] = []

    async def send_message(self, channel: str, message: str) -> None:
        await self._simulate_delay()
        msg = Message(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            channel=channel,
            text=message,
            author="runbook-bot",
            timestamp=datetime.now(timezone.utc),
        )
        self._sent_messages.append(msg)

    async def create_channel(self, name: str, purpose: str) -> Channel:
        await self._simulate_delay()
        ch = Channel(
            id=f"C{uuid.uuid4().hex[:6].upper()}",
            name=name,
            purpose=purpose,
            created_at=datetime.now(timezone.utc),
        )
        self._created_channels.append(ch)
        return ch

    async def get_recent_messages(self, channel: str, limit: int = 50) -> list[Message]:
        await self._simulate_delay()
        # Combine fixture messages with any messages sent during this session
        raw = self._get("recent_messages", [])
        fixture_messages = [
            Message(
                id=m["id"],
                channel=m["channel"],
                text=m["text"],
                author=m["author"],
                timestamp=m.get("timestamp"),
            )
            for m in raw
            if m["channel"] == channel
        ]
        session_messages = [m for m in self._sent_messages if m.channel == channel]
        combined = fixture_messages + session_messages
        return combined[-limit:]
