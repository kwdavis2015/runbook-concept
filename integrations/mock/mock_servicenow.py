"""Mock ServiceNow provider — implements TicketingProvider with scenario fixtures."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.config import Settings
from core.models import (
    ChangeRecord,
    CreateIncidentRequest,
    Incident,
    IncidentStatus,
    KBArticle,
    Severity,
    ProblemCategory,
)
from integrations.base import TicketingProvider
from integrations.mock.base import MockBase


class MockServiceNow(TicketingProvider, MockBase):
    provider_key = "servicenow"

    def __init__(self, settings: Settings) -> None:
        MockBase.__init__(self, settings)
        self._work_notes: dict[str, list[str]] = {}

    async def get_incident(self, incident_id: str) -> Incident:
        await self._simulate_delay()
        data = self._get("incident", {})
        return Incident(
            id=data.get("id", incident_id),
            title=data.get("short_description", data.get("title", "")),
            description=data.get("description", ""),
            status=IncidentStatus(data.get("status", "new")),
            severity=Severity(data.get("severity", "medium")),
            category=ProblemCategory(data.get("category", "unknown")),
            created_at=data.get("created_at"),
            metadata={"source": "servicenow", "number": data.get("number", "")},
        )

    async def create_incident(self, data: CreateIncidentRequest) -> Incident:
        await self._simulate_delay()
        inc_id = f"INC{uuid.uuid4().hex[:7].upper()}"
        return Incident(
            id=inc_id,
            title=data.short_description,
            description=data.description,
            status=IncidentStatus.NEW,
            severity=data.severity,
            category=data.category,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata={"source": "servicenow", "number": inc_id},
        )

    async def update_incident(self, incident_id: str, updates: dict) -> Incident:
        await self._simulate_delay()
        # Start from fixture data, apply updates on top
        incident = await self.get_incident(incident_id)
        for key, value in updates.items():
            if hasattr(incident, key):
                object.__setattr__(incident, key, value)
        return incident

    async def get_recent_changes(self, timeframe: str) -> list[ChangeRecord]:
        await self._simulate_delay()
        raw = self._get("recent_changes", [])
        return [
            ChangeRecord(
                id=c["id"],
                number=c["number"],
                description=c["description"],
                status=c.get("status", "closed"),
                created_at=c.get("created_at"),
                closed_at=c.get("closed_at"),
                requested_by=c.get("requested_by"),
                category=c.get("category"),
            )
            for c in raw
        ]

    async def add_work_note(self, incident_id: str, note: str) -> None:
        await self._simulate_delay()
        self._work_notes.setdefault(incident_id, []).append(note)

    async def search_knowledge_base(self, query: str) -> list[KBArticle]:
        await self._simulate_delay()
        raw = self._get("knowledge_base", [])
        return [
            KBArticle(
                id=kb["id"],
                title=kb["title"],
                content=kb["content"],
                category=kb.get("category"),
                relevance_score=kb.get("relevance_score", 0.0),
            )
            for kb in raw
        ]
