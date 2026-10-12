from fastapi import FastAPI, HTTPException

from support_chat import (
    ChatEvent,
    DeliveryReceipt,
    InfraiClient,
    InfraiError,
    SupportChat,
    VisitorDeparture,
)


app = FastAPI(title="Tenant support chat")


def chat() -> SupportChat:
    return SupportChat(InfraiClient.from_environment())


def rejected(error: InfraiError) -> HTTPException:
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return HTTPException(status_code=status, detail={"code": error.code, "error": error.detail})


@app.post("/support/events", response_model=DeliveryReceipt)
def publish_support_event(event: ChatEvent) -> DeliveryReceipt:
    try:
        return chat().publish(event)
    except InfraiError as error:
        raise rejected(error) from error


@app.post("/support/departures", response_model=DeliveryReceipt)
def record_departure(departure: VisitorDeparture) -> DeliveryReceipt:
    try:
        return chat().close_and_email(departure)
    except InfraiError as error:
        raise rejected(error) from error
