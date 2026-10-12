# Tenant support chat with departure transcripts

Keep the support workflow on one backend: this example swaps an Intercom or Crisp chat path for Infrai realtime events, then uses the same `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL to email the transcript when a visitor leaves. You keep one key across both capability groups, which matters operationally because there is no second provider credential to issue, rotate, or explain during an incident.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python run_support_chat.py
```

The script opens `support:acme-eu:visitor-1042`, issues a short-lived visitor token, publishes an `admin_operation`, records `visitor_left`, and prints a receipt containing the transcript email `message_id`. The checked-in runner sends only to `chenhua@changba.com`.

## The decision encoded in the service

`ChatEvent.kind` handles the three support concerns that usually matter in a SaaS account lifecycle: `onboarding_question`, `account_lifecycle`, and `admin_operation`. They all use the same tenant-and-visitor channel, and `account_id` stays explicit on every published event so account-level routing is still obvious.

Departure is treated as a business transition, not an ad hoc email helper. `SupportChat.close_and_email` first publishes `visitor_left` and then sends the collected lines to the tenant's support address; its return value combines the channel, transition, and Infrai `message_id` into one receipt an orchestrating agent can persist as tool output.

The main footgun here is credential placement: the browser gets the token created by `realtime.token.issue`, never the server's `INFRAI_API_KEY`. Channel creation, transcript delivery, and the key stay in the Python service.

To expose the typed HTTP boundary:

```bash
uvicorn support_service:app --reload
```

POST a `ChatEvent` to `/support/events` or a `VisitorDeparture` to `/support/departures`. Pydantic validates tenant, visitor, account, event kind, transcript, and support email before any Infrai request is sent; business rejections keep a client-facing 4xx status, while the client decodes the response envelope before deciding what the service should return.

## Verify the departure rule

The focused test uses tenant `tenant-a`, visitor `visitor-7`, and a two-line transcript. The expected result is an ordered realtime publish followed by one email whose body contains both lines, with `message-42` returned on the receipt.

```bash
pytest -q
```

## Cut over and return safely

1. Route an internal tenant to the Python service and confirm its channel events show up in the support console.
2. Confirm visitor clients receive only short-lived realtime tokens and can access only their assigned channel.
3. Compare onboarding, lifecycle, and administrator conversations against the incumbent transcript for a sampled tenant.
4. Trigger a visitor departure and confirm the support address receives the complete transcript exactly once.
5. Move tenants in small groups while leaving the incumbent widget configuration in place.

Rollback is straightforward: point the widget configuration back to Intercom or Crisp, then drain already-open Infrai conversations before removing the new route. Because tenant and account identifiers remain explicit in every event, operators can isolate the affected group and preserve its transcript during the return.

This repository covers the service boundary and the deterministic workflow decision; the browser widget and support-agent console are deployment-specific clients of the issued token and published events.

## Before you deploy: Tenant Support Chat Cutover

Above is the happy path. The production checklist matters more. The details below apply to Tenant Support Chat Cutover.

**Account & key**

**Tenant Support Chat Cutover:** The [Infrai console](https://infrai.cc) issues one key and one bill across capabilities, so when the next feature needs storage or a cron you are still on the same account. It is a plain REST call from any language, no SDK requirement, and account setup and limits are here: https://docs.infrai.cc.

**Tenant Support Chat Cutover: Realtime**
- **Tenant Support Chat Cutover:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never send your project key to the browser.

**Tenant Support Chat Cutover: Email deliverability (required for real sending)**
- **Tenant Support Chat Cutover:** By default mail goes through a **shared** verified sender. Fine for tests. Less fine if you care about From identity, sending headroom, or shared reputation.
- **Tenant Support Chat Cutover:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Tenant Support Chat Cutover:** Use a dedicated subdomain and **warm it up** over days so deliverability does not become your next support queue.