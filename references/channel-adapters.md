# Channel Adapters

## Default: Owned Landing Page

Use this adapter for the fully automated path:

```text
public content/profile CTA
  -> owned form on HTTPS
  -> SQLite capture
  -> score/route
  -> transactional email
  -> consented nurture
```

Use a unique `src` code on every link. Place the CTA in the bio, pinned post,
article footer, and end-screen copy. Tell people exactly what they will receive
and how often they may hear from you.

## Email

The built-in sender uses SMTP over TLS. Configure credentials through
environment variables:

```text
CREATOR_LEAD_SMTP_HOST
CREATOR_LEAD_SMTP_PORT
CREATOR_LEAD_SMTP_USER
CREATOR_LEAD_SMTP_PASSWORD
CREATOR_LEAD_SMTP_FROM
```

Use a transactional or reputable bulk provider for production volume; keep its
API key in environment variables. Include a working opt-out route in every
marketing message. The bundled templates demonstrate the delivery message and
follow-up shape; they are not legal advice.

## Private Webhook / CRM

The generic webhook can notify Feishu/WeCom/DingTalk bots, an automation
platform, or a CRM endpoint. Store the URL in:

```text
CREATOR_LEAD_WEBHOOK_URL
```

Send only the minimum fields needed for alerting and routing. Protect webhook
URLs as secrets. Verify with a test event and confirm idempotency on the
receiving side.

Recommended routing:

- `high`: immediate private alert to the owner and a CRM task;
- `medium`: add to consented nurture and weekly review;
- `low`: deliver the promised asset and leave the lead unassigned;
- `unsubscribed`: cancellation event and permanent suppression.

## WeChat Official Account

Keyword auto-replies and customer messages are allowed only through an official
account API and server configuration the user controls. Before implementation:

1. Confirm the account type and current platform capability.
2. Verify the message is triggered by a user action or prior opt-in.
3. Implement signature verification, replay protection, rate limits, and
   unsubscribe/stop handling.
4. Do not automate personal WeChat accounts, unofficial clients, or web UI
   sessions.

If the official integration is not available, direct followers to the owned
form and process replies manually.

## Douyin and X

Use platform-native analytics, official lead forms, or documented enterprise
APIs where available and authorized. Keep public-content publishing and
comment review in the platform's normal workflow. Do not use browser
automation, shared cookies, bulk follow/unfollow, scraped profiles, comment
mass-messaging, or unsolicited DM tools.

If the user has an approved API, add a provider adapter that:

- uses OAuth or scoped credentials;
- checks explicit user consent and platform policy;
- enforces idempotency and conservative rate limits;
- routes failures to a queue for human review;
- records exactly what was sent and why.

## Mini-Program or Quiz

A quiz can qualify rather than merely collect contact details. Ask only
job-relevant, first-party questions. Avoid sensitive inferences. At submission:

1. show the result immediately;
2. offer the lead magnet;
3. request separate consent for follow-up;
4. post the same normalized schema into the capture endpoint.
