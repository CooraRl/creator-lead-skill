# Acquisition Operating Model

## The Minimum Viable Loop

An acquisition system is not a library of posts. It needs one measurable path
from attention to a consented contact relationship:

| Stage | Required asset | Automation | Primary metric |
| --- | --- | --- | --- |
| Attract | platform content and profile CTA | draft generation, calendar, performance import | views, outbound clicks |
| Capture | owned form or approved official form | request validation, consent, dedupe, persistence | submissions, opt-in rate |
| Qualify | scoring rules and lead history | deterministic priority and routing | qualified leads |
| Convert | delivery, calendar, sales handoff | acknowledgement, reminders, owner alerts | booked calls, meetings, wins |
| Retain | useful follow-up and unsubscribe | scheduled consented messages | reply, unsubscribe, retention |
| Learn | source and content attribution | funnel report | qualified leads per content piece |

## Campaign Design Decisions

Before implementation, make these decisions explicit:

1. **One audience.** State the role, situation, and acute problem. Avoid mixing
   several unrelated audiences in one campaign.
2. **One promise.** A lead magnet must solve a concrete first-step problem and
   must already exist or have an owner and due date.
3. **One conversion.** Choose the next action: book a call, join a trial,
   request a quote, or buy. Secondary CTAs dilute attribution.
4. **One capture route.** Prefer an owned page or an approved official form.
   Track a unique `source_code` for every content asset.
5. **One follow-up contract.** State the message frequency and how to leave.
   Use only pre-approved message templates.
6. **One owner.** Every high-intent lead and every integration failure needs a
   named human owner.

## Attribution

Give every content asset a stable source code:

```text
{campaign}-{platform}-{format}-{sequence}
```

Examples: `ai-guide-douyin-short-003`, `ai-guide-x-thread-004`.

Put that code in the landing-page URL:

```text
https://leads.example.com/?utm_source=douyin&utm_medium=short&utm_campaign=ai-guide&src=ai-guide-douyin-short-003
```

The form must preserve the source code and campaign parameters in the lead
record. Do not rely on platform view counts as conversion evidence.

## Test Before Launch

Run this acceptance sequence in a test data directory:

1. Submit a form without consent and confirm it is rejected.
2. Submit the same consented email twice and confirm one lead plus a duplicate
   event.
3. Submit high-intent wording and confirm routing to `high`.
4. Submit a neutral download request and confirm routing to `medium`.
5. Confirm the transactional email is queued once.
6. Run the worker without `--send` and confirm no external effect.
7. Run with a test mailbox or test webhook, then verify delivery and retries.
8. Mark the lead `unsubscribed` and confirm due marketing messages are
   suppressed.
9. Confirm the report reconciles submissions, qualified leads, bookings, wins,
   and opt-outs.

Only call the system automated after all nine checks pass.
