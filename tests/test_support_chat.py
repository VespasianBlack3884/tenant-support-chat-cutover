from typing import Any

from support_chat import InfraiClient, SupportChat, VisitorDeparture


class RecordingClient(InfraiClient):
    def __init__(self) -> None:
        super().__init__(api_key="test-key")
        object.__setattr__(self, "calls", [])

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.calls.append((method, path, json, idempotency_key))
        return {"message_id": "message-42"} if path == "/v1/email/send" else {}


def test_visitor_departure_publishes_state_then_emails_transcript() -> None:
    client = RecordingClient()
    receipt = SupportChat(client).close_and_email(
        VisitorDeparture(
            tenant_id="tenant-a",
            visitor_id="visitor-7",
            account_id="account-9",
            support_email="help@example.com",
            transcript=["Visitor: Reset an administrator.", "Agent: Request recorded."],
        )
    )

    assert [call[1] for call in client.calls] == [
        "/v1/realtime/publish",
        "/v1/email/send",
    ]
    assert client.calls[0][2] == {
        "channel": "support:tenant-a:visitor-7",
        "event": "visitor_left",
        "data": {"visitor_id": "visitor-7"},
        "account_id": "account-9",
    }
    assert client.calls[1][2]["body"] == (
        "Visitor: Reset an administrator.\nAgent: Request recorded."
    )
    assert receipt.transcript_message_id == "message-42"
