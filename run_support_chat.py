from support_chat import ChatEvent, InfraiClient, SupportChat, VisitorDeparture


def main() -> None:
    support = SupportChat(InfraiClient.from_environment())
    tenant_id = "acme-eu"
    visitor_id = "visitor-1042"
    support.open_chat(tenant_id, visitor_id)
    token = support.issue_visitor_token(tenant_id, visitor_id)
    print({"visitor_token_issued": bool(token), "server_key_exposed": False})

    receipt = support.publish(
        ChatEvent(
            tenant_id=tenant_id,
            visitor_id=visitor_id,
            account_id="account-88",
            kind="admin_operation",
            message="Please add Mina as a billing administrator.",
        )
    )
    print(receipt.model_dump())

    departure = support.close_and_email(
        VisitorDeparture(
            tenant_id=tenant_id,
            visitor_id=visitor_id,
            account_id="account-88",
            support_email="chenhua@changba.com",
            transcript=[
                "Visitor: Please add Mina as a billing administrator.",
                "Agent: I have recorded the administrator change request.",
            ],
        )
    )
    print(departure.model_dump())


if __name__ == "__main__":
    main()
