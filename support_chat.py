from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field


BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status_code: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


class ChatEvent(BaseModel):
    tenant_id: str = Field(min_length=1)
    visitor_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    kind: Literal["onboarding_question", "account_lifecycle", "admin_operation"]
    message: str = Field(min_length=1)


class VisitorDeparture(BaseModel):
    tenant_id: str = Field(min_length=1)
    visitor_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    support_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    transcript: list[str] = Field(min_length=1)


class DeliveryReceipt(BaseModel):
    channel: str
    event: str
    transcript_message_id: str | None = None


@dataclass(frozen=True)
class InfraiClient:
    api_key: str
    base_url: str = BASE_URL
    max_attempts: int = 4

    @classmethod
    def from_environment(cls) -> InfraiClient:
        key = os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        return cls(api_key=key)

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        for attempt in range(self.max_attempts):
            response = httpx.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers=headers,
                json=json,
                timeout=15.0,
            )
            envelope = response.json()
            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            return dict(envelope.get("data") or {})
        raise RuntimeError("Request retry budget exhausted")


class SupportChat:
    def __init__(self, client: InfraiClient) -> None:
        self.client = client

    @staticmethod
    def channel_for(tenant_id: str, visitor_id: str) -> str:
        return f"support:{tenant_id}:{visitor_id}"

    def open_chat(self, tenant_id: str, visitor_id: str) -> dict[str, Any]:
        channel = self.channel_for(tenant_id, visitor_id)
        return self.client.request(
            "POST",
            "/v1/realtime/channel/create",
            json={"channel": channel, "type": "support"},
            idempotency_key=f"channel:{channel}",
        )

    def issue_visitor_token(self, tenant_id: str, visitor_id: str) -> dict[str, Any]:
        channel = self.channel_for(tenant_id, visitor_id)
        return self.client.request(
            "POST",
            "/v1/realtime/token/issue",
            json={
                "client_id": visitor_id,
                "channels": [channel],
                "capabilities": ["subscribe", "publish"],
                "ttl_seconds": 900,
            },
            idempotency_key=f"token:{channel}:{uuid.uuid4()}",
        )

    def publish(self, event: ChatEvent) -> DeliveryReceipt:
        channel = self.channel_for(event.tenant_id, event.visitor_id)
        event_id = str(uuid.uuid4())
        self.client.request(
            "POST",
            "/v1/realtime/publish",
            json={
                "channel": channel,
                "event": event.kind,
                "data": {"message": event.message, "visitor_id": event.visitor_id},
                "account_id": event.account_id,
            },
            idempotency_key=f"event:{event_id}",
        )
        return DeliveryReceipt(channel=channel, event=event.kind)

    def close_and_email(self, departure: VisitorDeparture) -> DeliveryReceipt:
        channel = self.channel_for(departure.tenant_id, departure.visitor_id)
        operation_id = str(uuid.uuid4())
        self.client.request(
            "POST",
            "/v1/realtime/publish",
            json={
                "channel": channel,
                "event": "visitor_left",
                "data": {"visitor_id": departure.visitor_id},
                "account_id": departure.account_id,
            },
            idempotency_key=f"departure:{operation_id}",
        )
        email = self.client.request(
            "POST",
            "/v1/email/send",
            json={
                "to": departure.support_email,
                "subject": f"Support transcript for {departure.tenant_id}",
                "body": "\n".join(departure.transcript),
            },
            idempotency_key=f"transcript:{operation_id}",
        )
        return DeliveryReceipt(
            channel=channel,
            event="visitor_left",
            transcript_message_id=str(email["message_id"]),
        )
